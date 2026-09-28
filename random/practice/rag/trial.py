import math
import pandas as pd
from fastapi import FastAPI, Query
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
import ingest
import query

app = FastAPI(title="Product Catalog API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

df = pd.read_csv("products.csv").fillna("")
df.columns = df.columns.str.strip()
df = df.drop_duplicates(subset=["Name"], keep="first")

def normalize(text: str) -> str:
    return " > ".join([p.strip().lower() for p in text.split(">")]).strip()

@app.get("/products")
def get_products(
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    filtered_df = df
    if category:
        cat_norm = normalize(category)
        def match(cell: str) -> bool:
            paths = [normalize(p) for p in str(cell).split(",")]
            for p in paths:
                if p == cat_norm or p.startswith(cat_norm + " >"):
                    return True
            return False
        filtered_df = filtered_df[filtered_df["Categories"].apply(match)]

    total_items = len(filtered_df)
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 1
    paginated = filtered_df.iloc[(page-1)*limit : page*limit]

    return {
        "metadata": {
            "total_items": total_items,
            "total_pages": total_pages,
            "current_page": page,
            "limit": limit
        },
        "products": paginated.to_dict(orient="records")
    }

@app.get("/categories")
def get_categories():
    tree = {}
    for cell in df["Categories"]:
        for path in [p.strip() for p in str(cell).split(",") if p.strip()]:
            parts = [p.strip() for p in path.split(">")]
            node = tree
            for part in parts:
                node = node.setdefault(part, {})
    def build(node):
        return [
            {
                "name": name,
                "subcategories": [sub for sub in sorted(child.keys())] if child else [],
                "children": build(child)
            }
            for name, child in sorted(node.items())
        ]
    return build(tree)

app.include_router(ingest.router)
app.include_router(query.router)




















import re
import math
import pandas as pd
from fastapi import FastAPI, Query
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
import ingest
import query
from html import unescape


app = FastAPI(title="Product Catalog API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:8000", "https://medstore.codenomad.net"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def strip_html(text: str) -> str:
    if not text:
        return ""
    # decode &deg; &amp; etc
    text = unescape(text)
    # remove <p> <br> etc
    text = re.sub(r'<[^>]+>', ' ', text)
    # clean extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def to_slug(s):
    return re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-')


def normalize(text: str):
    return " > ".join([p.strip().lower() for p in str(text).split(">")]).strip()


def get_primary_path(categories_str: str):
    paths = [p.strip() for p in str(categories_str).split(",") if p.strip()]
    if not paths:
        return "uncategorized"
    paths = sorted(paths, key=lambda x: x.count(">"), reverse=True)
    return paths[0]


df = pd.read_csv("products.csv").fillna("")
df.columns = df.columns.str.strip()
df = df[df['Name'].astype(str).str.strip()!= ""]
df = df.drop_duplicates(subset=["Name"], keep="first").reset_index(drop=True)

all_products = []
counter = 1

for _, row in df.iterrows():
    name = str(row['Name']).strip()
    if name == "":
        continue

    primary = get_primary_path(row['Categories'])
    parts = [p.strip() for p in primary.split(">")]

    top = parts[0] if len(parts) > 0 else "uncategorized"
    sub = parts[1] if len(parts) > 1 else ""

    try:
        price = float(row['Regular price'] or row['Sale price'] or 0)
    except:
        price = 0

    short_desc = str(row['Short description']).strip()
    if not short_desc:
        short_desc = str(row['Description'])[:150].strip()

    all_products.append({
        "id": f"p{counter}",
        "name": name,
        "slug": to_slug(name),
        "description": short_desc,
        "longDescription": str(row['Description']),
        "categoryId": to_slug(top),
        "subcategoryId": to_slug(sub) if sub else "",
        "categoryName": top,
        "subcategoryName": sub,
        "price": price,
        "brand": "Generic",
        "inStock": str(row['In stock?']) == '1',
        "rating": 4.5,
        "tint": "#dceef7",
        "icon": to_slug(sub).split('-')[0] if sub else to_slug(top).split('-')[0],
        "image": str(row['Images']).split(',')[0].strip() if row['Images'] else "/products/placeholder.png",
        "tags": [t.strip() for t in str(row['Tags']).split(',') if t.strip()][:5],
        "specifications": {"Model": str(row.get('Attribute 1 value(s)', ''))},
        "_raw_categories": str(row['Categories'])
    })
    counter += 1


@app.get("/products")
def get_products(
    category: Optional[str] = Query(None),
    product: Optional[str] = Query(None, description="Product name or slug"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    # If product name/slug is mentioned -> return that product detail
    if product:
        prod_norm = product.strip().lower()
        prod_slug = to_slug(prod_norm)

        for p in all_products:
            if p["name"].lower() == prod_norm or p["slug"] == prod_slug or p["slug"] == prod_norm:
                clean = {k: v for k, v in p.items() if not k.startswith("_")}
                clean["description"] = strip_html(clean["description"])
                clean["longDescription"] = strip_html(clean["longDescription"])
                return clean

        for p in all_products:
            if prod_norm in p["name"].lower() or prod_norm in p["slug"]:
                clean = {k: v for k, v in p.items() if not k.startswith("_")}
                clean["description"] = strip_html(clean["description"])
                clean["longDescription"] = strip_html(clean["longDescription"])
                return clean

        return {"error": f"Product '{product}' not found"}

    # If product not mentioned -> filter by category
    filtered = all_products

    if category:
        cat_norm = normalize(category).lower()
        new_list = []
        for p in filtered:
            paths = [normalize(x).lower() for x in p["_raw_categories"].split(",")]
            for path in paths:
                parts = [s.strip() for s in path.split(">")]
                if cat_norm == path or cat_norm in parts or f" > {cat_norm}" in path or f"{cat_norm} >" in path:
                    new_list.append(p)
                    break
        filtered = new_list

    total_items = len(filtered)
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 1
    start = (page - 1) * limit
    paginated = filtered[start:start+limit]

    result = []
    for p in paginated:
        clean = {k: v for k, v in p.items() if not k.startswith("_")}
        # ONLY CLEAN WHILE SENDING RESPONSE
        clean["description"] = strip_html(clean["description"])
        clean["longDescription"] = strip_html(clean["longDescription"])
        result.append(clean)

    return {
        "metadata": {
            "total_items": total_items,
            "total_pages": total_pages,
            "current_page": page,
            "limit": limit
        },
        "products": result
    }


@app.get("/categories")
def get_categories():
    tree = {}
    for cell in df["Categories"]:
        for path in [p.strip() for p in str(cell).split(",") if p.strip()]:
            parts = [p.strip() for p in path.split(">")]
            node = tree
            for part in parts:
                node = node.setdefault(part, {})

    def build(node):
        out = []
        for name, child in sorted(node.items()):
            out.append({
                "id": to_slug(name),
                "name": name,
                "slug": to_slug(name),
                "subcategories": sorted(child.keys()), # simple list
                "children": build(child)
            })
        return out

    return build(tree)

app.include_router(ingest.router)
app.include_router(query.router)






























from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
import pandas as pd, ollama, re, os
from html import unescape
from fastapi import APIRouter

router = APIRouter()
BASE = os.path.dirname(__file__)
df = pd.read_csv(os.path.join(BASE, "products.csv")).fillna("")
db = Chroma(persist_directory=os.path.join(BASE, "chroma_db"),
            embedding_function=OllamaEmbeddings(model="all-minilm")) # <- stays all-minilm

def clean(t):
    if not t: return ""
    return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',unescape(str(t)).replace("\n"," "))).strip()

@router.get("/query")
def ask_rag_bot(user_query: str):
    results = db.similarity_search_with_score(user_query[:200], k=10)

    if not results or results[0][1] > 1.0: # fast check, no LLM classification
        res = ollama.chat(model="llama3.2",
            messages=[{"role":"system","content":"You are a professional medical store assistant."},
                      {"role":"user","content":user_query}],
            options={"num_predict": 80, "temperature": 0.2})
        return {"answer": clean(res["message"]["content"]), "products": []}

    products, seen = [], set()
    for doc,_ in results:
        d = df.iloc[int(doc.metadata.get("row"))].to_dict()
        norm = re.sub(r'[^a-z0-9]','',d.get("Name","").lower())
        if norm in seen: continue
        seen.add(norm)
        d["Description"] = clean(d.get("Description",""))
        products.append(d)
        if len(products)==3: break

    context = "\n".join([f"{p['Name']}: {p['Description'][:250]}" for p in products])
    res = ollama.chat(model="llama3.2",
        messages=[{"role":"user","content": f"Context:{context}\nQuery:{user_query}\nExplain as Product/Use/Features."}],
        options={"num_predict": 180, "num_ctx": 1024})
    return {"answer": clean(res["message"]["content"]), "products": products}






























from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
import pandas as pd, re, os
from html import unescape
from fastapi import APIRouter

router = APIRouter()
BASE = os.path.dirname(__file__)

# fill missing values with empty string
df = pd.read_csv(os.path.join(BASE, "products.csv")).fillna("")

# lowercase columns
df["Name_lower"] = df["Name"].str.lower().str.strip()
df["Categories_lower"] = df["Categories"].str.lower()

# connect to chroma db using ollama embeddings
db = Chroma(persist_directory=os.path.join(BASE, "chroma_db"),
            embedding_function=OllamaEmbeddings(model="all-minilm"))

# function to remove html tags, line breaks and extra spaces
def clean(t):
    if not t: return ""
    t = str(t).replace("\\n"," ").replace("\n"," ").replace("\r"," ")
    t = unescape(t)
    t = re.sub(r'<[^>]+>',' ',t)
    return re.sub(r'\s+',' ',t).strip()

# Query products
@router.get("/query")
def ask_rag_bot(user_query: str):
    q = user_query.strip()
    # lowercase and remve filler words
    q_low = q.lower().replace("show me","").replace("show","").strip()
    
    results = db.similarity_search_with_score(q[:200], k=20)

    if not results or results[0][1] > 1.2:
        return {"answer": "I can only help with products from our medical store.", "products": []}

    # EXACT PRODUCT -> 1
    exact_rows = []
    for _, r in df.iterrows():
        if len(r["Name_lower"]) > 4 and r["Name_lower"] in q.lower():
            exact_rows.append(r)
    if exact_rows:
        final_rows = sorted(exact_rows, key=lambda x: len(x["Name"]), reverse=True)[:1]
    else:
        # CATEGORY -> up to 20
        cat_match = df[df["Categories_lower"].str.contains(q_low, na=False)]
        if len(cat_match) >= 3:
            final_rows = [r for _, r in cat_match.head(20).iterrows()]
        else:
            # GENERAL -> 3
            seen=set()
            final_rows=[]
            for doc,score in results:
                if score>1.0: continue
                r = df.iloc[int(doc.metadata.get("row"))]
                key=re.sub(r'[^a-z0-9]','',r["Name"].lower())
                if key in seen: continue
                seen.add(key)
                final_rows.append(r)
                if len(final_rows)==3: break

    products=[]
    for r in final_rows:
        d = {k:v for k,v in r.to_dict().items() if not k.startswith("Unnamed") and k not in ["Name_lower","Categories_lower"]}
        products.append(d)

    # SHORT ANSWER - not large
    if len(products)==1:
        p=products[0]
        answer = f"{p['Name']}: {clean(p['Description'])[:200]}"
    elif len(products)>3:
        # Category - list names only
        names = ", ".join([p["Name"] for p in products[:10]])
        answer = f"Found {len(products)} products in '{q_low}': {names} and {len(products)-10} more. Use: {products[0]['Categories'].split(',')[0]}"
    else:
        answer = f"Found {len(products)} products for '{q}': " + ", ".join([p["Name"] for p in products])

    return {"answer": answer, "products": products}



















# ======================================================================================
# ================================== query.py ==========================================
# ======================================================================================
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
import pandas as pd, re, os, random
from html import unescape
from fastapi import APIRouter

router = APIRouter()
BASE = os.path.dirname(__file__)

df = pd.read_csv(os.path.join(BASE, "products.csv")).fillna("")
df["Name_lower"] = df["Name"].str.lower().str.strip()
df["Categories_lower"] = df["Categories"].str.lower()

db = Chroma(persist_directory=os.path.join(BASE, "chroma_db"),
            embedding_function=OllamaEmbeddings(model="all-minilm"))

llm_creative = ChatOllama(model="llama3.2:1b", temperature=0.8, num_predict=60)

def clean(t):
    t = unescape(str(t).replace("\\n"," ").replace("\n"," "))
    t = re.sub(r'<[^>]+>',' ',t)
    return re.sub(r'\s+',' ',t).strip()

# ---- FIX 1: all_cats must be defined before ask_rag_bot ----
all_cats = set()
for cats in df["Categories"].dropna():
    for part in re.split(r'[,>]', str(cats)):
        p = part.strip().lower()
        if len(p) > 3:
            all_cats.add(p)
all_cats = sorted(all_cats, key=len, reverse=True)

def varied_greeting(q):
    try:
        styles = ["friendly", "cheerful", "warm", "helpful", "casual"]
        style = random.choice(styles)
        prompt = f"""User said: "{q}"
You are Medstore medical store assistant. Reply with a {style} greeting in different words each time.
Mention you can help find medical products. Keep under 20 words."""
        ans = llm_creative.invoke(prompt).content.strip()
        if any(k in ans.lower() for k in ["can't", "cannot", "sorry"]):
            return "Hi there! How can I help you find medical products today?"
        return ans
    except:
        return "Hello! How can I help you today?"

def is_refusal(text: str):
    t = text.lower()
    return "can't assist" in t or "cannot assist" in t or "i can't" in t or "i cannot" in t or "sorry" in t

@router.get("/query")
def ask_rag_bot(user_query: str):
    q = user_query.strip()
    q_low = q.lower().strip()

    if len(q_low) <= 4 or (len(q_low.split()) <= 2 and len(q_low) < 15):
        is_product = any(len(nl)>4 and nl in q_low for nl in df["Name_lower"])
        is_cat = any(cat in q_low for cat in all_cats)
        if not is_product and not is_cat:
            return {"answer": varied_greeting(q), "products": []}

    intents = [s.strip() for s in re.split(r'\s+and\s+|\s*,\s*|\s+plus\s+', q_low) if len(s.strip())>2]
    if not intents:
        intents = [q_low]

    final_rows = []
    seen = set()
    def add_row(r):
        key = re.sub(r'[^a-z0-9]','', str(r["Name"]).lower())
        if key not in seen:
            seen.add(key)
            final_rows.append(r)

    for intent in intents:
        best = None
        # exact transit chair
        if "transit" in intent and "chair" in intent:
            cand = df[df["Name_lower"] == "transit chair"]
            if not cand.empty:
                best = cand.iloc[0]

        # blood pressure monitor
        if best is None and ("blood pressure" in intent or "bpm" in intent):
            cand = df[df["Categories_lower"].str.contains("blood pressure", na=False) | df["Name_lower"].str.contains("blood pressure|bpm")]
            # exclude manual aneroid and treatment chair if user asked digital/arm
            if "digital" in intent or "arm" in intent:
                cand = cand[~cand["Name_lower"].str.contains("aneroid|durashock|trigger|multifunctional treatment")]
            if not cand.empty:
                best = cand.iloc[0]

        # vector search fallback per intent
        if best is None:
            try:
                res = db.similarity_search_with_score(intent[:200], k=2)
                for doc, score in res:
                    if score > 1.2: continue
                    best = df.iloc[int(doc.metadata.get("row"))]
                    break
            except:
                pass

        if best is not None:
            add_row(best)

    if not final_rows:
        try:
            res = db.similarity_search_with_score(q[:200], k=3)
            for doc, score in res:
                if score > 1.2: continue
                add_row(df.iloc[int(doc.metadata.get("row"))])
        except:
            pass

    final_rows = final_rows[:3]
    products = [{k:v for k,v in r.to_dict().items() if not k.startswith("Unnamed") and k not in ["Name_lower","Categories_lower"]} for r in final_rows]

    if not products:
        return {"answer": "I can only help with products from our medical store.", "products": []}

    # ---- FIX 2: NEVER use LLM for product description, 100% refusal-proof ----
    if len(products) == 1:
        answer = clean(products[0].get("Description","") + " " + products[0].get("Short description",""))[:600]
    else:
        parts = []
        for p in products:
            d = clean(p.get("Description","") + " " + p.get("Short description",""))[:300]
            parts.append(f"{p['Name']}: {d}")
        answer = " | ".join(parts)

    if is_refusal(answer) or len(answer) < 10:
        answer = clean(products[0].get("Description",""))[:600]

    return {"answer": answer, "products": products}




























# =================================================================================================
# ===================================== claude ====================================================
# =================================================================================================

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
import pandas as pd, re, os, random, difflib, json
from html import unescape
from fastapi import APIRouter

router = APIRouter()
BASE = os.path.dirname(__file__)

df = pd.read_csv(os.path.join(BASE, "products.csv")).fillna("")
df["Name_lower"] = df["Name"].str.lower().str.strip()
df["Categories_lower"] = df["Categories"].str.lower()

try:
    db = Chroma(persist_directory=os.path.join(BASE, "chroma_db"),
                embedding_function=OllamaEmbeddings(model="all-minilm"))
except Exception:
    db = None

llm_creative = ChatOllama(model="llama3.2:1b", temperature=0.2, num_predict=120)

DROP_COLS = ["Name_lower", "Categories_lower"]

GENERIC_WORDS = {"show", "me", "some", "products", "product", "list",
                  "all", "give", "please", "want", "need", "any", "few"}

GREETING_WORDS = {"hi", "hey", "hello", "hola", "howdy"}
GOODBYE_WORDS = {
    "bye", "goodbye", "see you", "farewell", "take care", "see ya",
    "adios", "good night", "bye bye", "see you soon",
}
GREETING_PHRASES = {
    "good morning", "good afternoon", "good evening",
    "greetings", "hi there", "hello there", "hey there",
}

EXCLUSION_KEYWORDS = [
    "other than", "other then", "except", "excluding", "exclude",
    "without", "apart from", "besides", "not including", "not include",
]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def clean(t):
    t = unescape(str(t).replace("\\n", " ").replace("\n", " "))
    t = re.sub(r'<[^>]+>', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


all_cats = set()
for cats in df["Categories"].dropna():
    for part in re.split(r'[,>]', str(cats)):
        p = part.strip().lower()
        if len(p) > 3:
            all_cats.add(p)
all_cats = sorted(all_cats, key=len, reverse=True)


def _to_str(q):
    if isinstance(q, dict):
        for k in ["name", "product", "title", "value", "category"]:
            if k in q and isinstance(q[k], str):
                return q[k]
        for v in q.values():
            if isinstance(v, str):
                return v
        return str(q)
    return str(q) if q is not None else ""


def row_key(row_or_name):
    """Normalized dedup/exclusion key for a product row, dict, or plain name."""
    if isinstance(row_or_name, str):
        name_low = row_or_name.lower()
    else:
        try:
            name_low = row_or_name["Name_lower"]
        except Exception:
            name_low = str(row_or_name.get("Name", "")).lower()
    return re.sub(r'[^a-z0-9]', '', name_low)


def row_to_dict(row):
    d = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    return {k: v for k, v in d.items() if not k.startswith("Unnamed") and k not in DROP_COLS}


def rows_to_dicts(rows, excluded_keys=None):
    excluded_keys = excluded_keys or set()
    out = []
    seen = set()
    for r in rows:
        key = row_key(r)
        if key in excluded_keys or key in seen:
            continue
        seen.add(key)
        out.append(row_to_dict(r))
    return out


def extract_exclusion(q_low):
    """Split a query into (main_query, [excluded phrases]) for phrases like
    'other than X', 'except Y and Z'."""
    q_low = q_low.lower()
    for kw in sorted(EXCLUSION_KEYWORDS, key=len, reverse=True):
        if kw in q_low:
            idx = q_low.find(kw)
            main_part = q_low[:idx].strip()
            after = q_low[idx + len(kw):].strip()
            parts = re.split(r'\s+and\s+|\s*,\s*|\s+or\s+', after)
            excluded = []
            for p in parts:
                p = re.sub(r'[^\w\s\-]', '', p).strip()
                if len(p) >= 3:
                    excluded.append(p)
            return main_part, excluded
    return q_low, []


def get_excluded_keys(excluded_phrases):
    excluded_keys = set()
    for phrase in excluded_phrases:
        for r in fuzzy_find_products(phrase, limit=5):
            excluded_keys.add(row_key(r))
    return excluded_keys


def classify_intent_llm(user_query: str):
    prompt = f"""
You classify user messages for a medical store.

User: "hi" -> {{"intent":"greeting","products":[],"category":null,"detail":null}}
User: "hello there" -> {{"intent":"greeting","products":[],"category":null,"detail":null}}
User: "bye" -> {{"intent":"goodbye","products":[],"category":null,"detail":null}}
User: "goodbye" -> {{"intent":"goodbye","products":[],"category":null,"detail":null}}
User: "Transit Chair" -> {{"intent":"single_product","products":["Transit Chair"],"category":null,"detail":null}}
User: "price of transit chair" -> {{"intent":"specific_detail","products":["Transit Chair"],"category":null,"detail":"price"}}
User: "emergency" -> {{"intent":"category_search","products":[],"category":"emergency","detail":null}}
User: "suggest emergency chairs" -> {{"intent":"suggestion","products":[],"category":"emergency","detail":null}}
User: "compare Transit Chair and Tri Wheel Transit Chair" -> {{"intent":"comparison","products":["Transit Chair","Tri Wheel Transit Chair"],"category":null,"detail":null}}

Now classify:
User: "{user_query}" ->
Return ONLY JSON, no explanation.
"""
    try:
        resp = llm_creative.invoke(prompt).content.strip()
        m = re.search(r'\{.*\}', resp, re.DOTALL)
        if not m:
            return None
        return json.loads(m.group(0))
    except Exception:
        return None


def fuzzy_find_products(query_text, limit=10):
    """Find products by name, tolerant of misspellings (word overlap +
    difflib similarity + optional vector search fallback)."""
    query_text = _to_str(query_text)
    if len(query_text.strip()) < 3:
        return []
    q_low = query_text.lower()

    q_words_raw = [w for w in q_low.split() if len(w) >= 2]
    if q_words_raw and all(w in GENERIC_WORDS for w in q_words_raw):
        return []

    # Exact match first -> always wins and is returned alone.
    exact = df[df["Name_lower"] == q_low]
    if not exact.empty:
        return [exact.iloc[0]]

    q_words = [w for w in q_low.split() if len(w) >= 3]
    if not q_words:
        return []

    results = []
    seen = set()
    for _, r in df.iterrows():
        name = r["Name_lower"]
        name_words = [w for w in name.split() if len(w) >= 3]
        if not name_words:
            continue
        matched = 0
        for nw in name_words:
            for qw in q_words:
                if len(qw) < 3 or len(nw) < 3:
                    continue
                if nw == qw:
                    matched += 1
                    break
                if len(nw) >= 4 and len(qw) >= 4 and (nw in qw or qw in nw):
                    matched += 1
                    break
                if difflib.SequenceMatcher(None, nw, qw).ratio() >= 0.8:
                    matched += 1
                    break
        if name_words and matched / len(name_words) >= 0.6:
            key = row_key(name)
            if key not in seen:
                seen.add(key)
                results.append((r, matched / len(name_words)))

    close = difflib.get_close_matches(q_low, df["Name_lower"].tolist(), n=10, cutoff=0.65)
    for c in close:
        key = row_key(c)
        if key not in seen:
            row = df[df["Name_lower"] == c]
            if not row.empty:
                seen.add(key)
                results.append((row.iloc[0], 0.6))

    if db is not None and len(results) < 2:
        if not all(w in GENERIC_WORDS for w in q_words):
            try:
                res = db.similarity_search_with_score(query_text[:200], k=5)
                for doc, score in res:
                    if score > 1.0:
                        continue
                    r = df.iloc[int(doc.metadata.get("row"))]
                    key = row_key(r)
                    if key not in seen:
                        seen.add(key)
                        results.append((r, 1 - score))
            except Exception:
                pass

    results = sorted(results, key=lambda x: x[1], reverse=True)
    return [r for r, _ in results[:limit]]


def fuzzy_find_categories(query_text, limit=5):
    """Find categories by name, tolerant of misspellings, ranked by actual
    relevance to the query (not by category-name length)."""
    query_text = _to_str(query_text)
    if len(query_text.strip()) < 3:
        return []
    q_low = query_text.lower()
    q_words = [w for w in q_low.split() if len(w) >= 3 and w not in GENERIC_WORDS]
    if not q_words:
        return []

    scored = []  # (category, relevance_score, is_exact_or_substring)
    seen = set()
    for cat in all_cats:
        if cat in q_low:
            if cat not in seen:
                seen.add(cat)
                scored.append((cat, 1.0, True))
            continue
        # Split on any non-alphanumeric char (not just spaces) so compound
        # category tokens like "infection/disease" or
        # "wheelchairs/buggies/chairs" are compared word-by-word instead of
        # as one opaque blob.
        cat_words = [w for w in re.split(r'[^a-z0-9]+', cat) if len(w) >= 3]
        if not cat_words:
            continue
        match_count = 0
        exact_hit = False
        for cw in cat_words:
            for qw in q_words:
                if cw == qw:
                    match_count += 1
                    exact_hit = True
                    break
                if len(cw) >= 4 and len(qw) >= 4 and (cw in qw or qw in cw):
                    match_count += 1
                    break
                if difflib.SequenceMatcher(None, cw, qw).ratio() >= 0.8:
                    match_count += 1
                    break
        ratio = match_count / len(cat_words)
        # A category is relevant if most of its words are matched, OR if at
        # least one of its words matches the query exactly (e.g. "infection"
        # exactly hitting "infection/disease" even though "disease" wasn't
        # mentioned) — an exact keyword hit is a strong signal on its own.
        if ratio >= 0.6 or (exact_hit and match_count >= 1):
            if cat not in seen:
                seen.add(cat)
                scored.append((cat, ratio, exact_hit))

    close = difflib.get_close_matches(q_low, all_cats, n=5, cutoff=0.6)
    for c in close:
        if c not in seen:
            seen.add(c)
            scored.append((c, 0.5, False))

    # Rank by relevance (exact/substring hits first, then match ratio), NOT
    # by how long the category string happens to be.
    scored.sort(key=lambda x: (x[2], x[1]), reverse=True)

    # Only keep candidates that are genuinely close in relevance to the best
    # match. Without this, a strong exact hit (e.g. "covid section", ratio
    # 1.0) would get merged with a much weaker one (e.g. "infection/disease",
    # ratio 0.5 from a single shared word) purely because both cleared the
    # inclusion threshold — flooding the result with unrelated products.
    if scored:
        top_ratio = scored[0][1]
        scored = [s for s in scored if s[1] >= top_ratio - 0.25]

    return [c for c, _, _ in scored][:limit]


def get_products_by_categories(cats, limit=1000):
    """Return ALL products belonging to any of the given categories
    (deduplicated), capped at `limit` as a safety valve."""
    rows = []
    seen = set()
    for cat in cats:
        matches = df[df["Categories_lower"].str.contains(re.escape(cat), na=False, regex=True)]
        for _, r in matches.iterrows():
            key = row_key(r)
            if key not in seen:
                seen.add(key)
                rows.append(r)
        if len(rows) >= limit:
            break
    return rows[:limit]


def get_random_products(limit=10):
    try:
        sample_df = df.sample(n=min(limit, len(df)))
        return [r for _, r in sample_df.iterrows()]
    except Exception:
        return [r for _, r in df.head(limit).iterrows()]


def random_products_response(excluded_keys, excluded_phrases, tries=5, pool=15, show=10):
    filtered_rows = []
    for _ in range(tries):
        candidate_rows = get_random_products(limit=pool)
        filtered_rows = [r for r in candidate_rows if row_key(r) not in excluded_keys]
        if len(filtered_rows) >= 5:
            break
    prod_dicts = rows_to_dicts(filtered_rows[:show], excluded_keys)
    suffix = f" excluding {', '.join(excluded_phrases)}" if excluded_phrases else ""
    names = ', '.join(p['Name'] for p in prod_dicts[:5])
    return {"answer": f"Here are some products from Medstore{suffix}: {names}", "products": prod_dicts}


def build_detail_answer(product, detail):
    detail = _to_str(detail)
    if not detail or detail.lower() in ["null", "none", ""]:
        return clean(product.get('Description', '') + ' ' + product.get('Short description', ''))[:700]
    d = detail.lower()
    if d == "price":
        return f"{product['Name']} - Regular price: €{product.get('Regular price', 'N/A')} | Sale price: {product.get('Sale price', '') or 'N/A'}"
    if d == "stock":
        return f"{product['Name']} - In stock: {product.get('In stock?', 'N/A')}"
    if d == "images":
        return f"{product['Name']} - Images: {product.get('Images', 'N/A')}"
    if d == "description":
        return f"{product['Name']} - {clean(product.get('Description', '') + ' ' + product.get('Short description', ''))[:700]}"
    if d == "categories":
        return f"{product['Name']} - Categories: {product.get('Categories', 'N/A')}"
    if d == "model":
        return f"{product['Name']} - {product.get('Attribute 1 name', 'Model')}: {product.get('Attribute 1 value(s)', 'N/A')}"
    if d == "tags":
        return f"{product['Name']} - Tags: {product.get('Tags', 'N/A')}"
    return clean(product.get('Description', ''))[:700]


def full_product_answer(p):
    """Full detail summary for a single product (used for 'single_product' intent)."""
    return (
        f"{clean(p.get('Description', '') + ' ' + p.get('Short description', ''))[:700]} "
        f"| Price: €{p.get('Regular price', '') or 'N/A'} "
        f"| Sale price: {p.get('Sale price', '') or 'N/A'} "
        f"| Stock: {p.get('In stock?', 'N/A')} "
        f"| Category: {p.get('Categories', 'N/A')} "
        f"| {p.get('Attribute 1 name', 'Model')}: {p.get('Attribute 1 value(s)', 'N/A')}"
    )


def generate_greeting(is_goodbye=False):
    if is_goodbye:
        return random.choice([
            "Goodbye! Have a great day!",
            "Bye! Come back anytime for medical supplies.",
            "See you soon! Thanks for visiting Medstore.",
        ])
    return random.choice([
        "Hello! I'm your Medstore assistant. How can I help you find medical products today?",
        "Hi there! Looking for something at Medstore? I can help you find it.",
    ])


def is_generic_query(text):
    """True for content-free requests like 'show me some products' /
    'list all products' — with or without exclusion phrases stripped off.
    These should always fall through to a random-products response instead
    of being treated as a product/category search."""
    words = [w for w in text.strip().lower().split() if len(w) >= 2]
    return bool(words) and all(w in GENERIC_WORDS for w in words)


def validate_llm_entities(names, q_low):
    """Small local LLMs can hallucinate plausible-sounding but unrelated
    product/category names. Only trust an LLM-suggested name if at least
    one of its significant words actually appears in the user's own query
    text — otherwise it's discarded rather than used for lookup."""
    valid = []
    for n in names:
        n_low = _to_str(n).lower()
        words = [w for w in n_low.split() if len(w) >= 3]
        if words and any(w in q_low for w in words):
            valid.append(n)
    return valid


def is_greeting_or_goodbye(q_low):
    """Returns 'greeting', 'goodbye', or None. Checked BEFORE any product /
    category lookup so greetings never get treated as product queries.
    Goodbye words are checked first since some (e.g. "bye") are short
    enough to otherwise be caught by the generic short-greeting fallback."""
    if q_low in GOODBYE_WORDS:
        return "goodbye"
    if q_low in GREETING_WORDS or q_low in GREETING_PHRASES:
        return "greeting"
    if len(q_low) <= 3:
        return "greeting"
    return None


# --------------------------------------------------------------------------
# main endpoint
# --------------------------------------------------------------------------

@router.get("/query")
def ask_rag_bot(user_query: str):
    q = user_query.strip()
    q_low = q.lower().strip()
    if not q_low:
        return {"answer": generate_greeting(False), "products": []}

    # --- 1. Greeting / goodbye: never look up products for these ---
    greeting_kind = is_greeting_or_goodbye(q_low)
    if greeting_kind == "greeting":
        return {"answer": generate_greeting(False), "products": []}
    if greeting_kind == "goodbye":
        return {"answer": generate_greeting(True), "products": []}

    # --- 2. Exclusions: "other than X", "except Y", etc. ---
    main_q, excluded_phrases = extract_exclusion(q_low)
    excluded_keys = get_excluded_keys(excluded_phrases) if excluded_phrases else set()
    query_for_intent = main_q if excluded_phrases else q
    search_q = main_q if excluded_phrases else q_low

    # --- 2b. Generic requests ("show me some products [other than X]")
    # always mean "give me a random sample", regardless of what the LLM
    # classifier says (or whether it's reachable at all). Checked on the
    # exclusion-stripped query so "...other than transit chair" doesn't
    # smuggle "transit chair" back in as a search term.
    if is_generic_query(search_q):
        return random_products_response(excluded_keys, excluded_phrases)

    # --- 3. Ask the LLM to classify intent ---
    cls = classify_intent_llm(query_for_intent)
    if cls is None:
        # Fallback when the LLM call fails: try to detect a greeting typed
        # alongside other words (e.g. "hi there, need a transit chair"),
        # otherwise treat the (exclusion-stripped) query as a product/
        # category search — never the raw query, or excluded terms like
        # "transit chair" leak back in as search terms.
        if len(q_low.split()) <= 3:
            prod_exact = q_low in df["Name_lower"].values
            cat_exact = q_low in all_cats
            if not prod_exact and not cat_exact and any(w in q_low for w in ["hi", "hello", "hey", "bye", "goodbye"]):
                if not fuzzy_find_products(q_low, limit=1):
                    return {"answer": generate_greeting("bye" in q_low or "goodbye" in q_low), "products": []}
        cls = {"intent": "single_product", "products": [query_for_intent], "category": None, "detail": None}

    intent = cls.get("intent", "single_product")
    mentioned_products = validate_llm_entities(cls.get("products", []) or [], q_low)
    mentioned_category_raw = cls.get("category")
    mentioned_category = (
        mentioned_category_raw
        if mentioned_category_raw and validate_llm_entities([mentioned_category_raw], q_low)
        else None
    )
    detail = cls.get("detail")

    # The LLM can still (rarely) say "greeting"/"goodbye" mid-conversation.
    if intent == "greeting":
        return {"answer": generate_greeting(False), "products": []}
    if intent == "goodbye":
        return {"answer": generate_greeting(True), "products": []}

    # --- 4. Resolve candidate products (misspelling-tolerant) ---
    resolved_products = []
    seen = set()
    for pname in mentioned_products:
        for r in fuzzy_find_products(pname, limit=3):
            key = row_key(r)
            if key not in seen and key not in excluded_keys:
                seen.add(key)
                resolved_products.append(r)
    if not resolved_products:
        resolved_products = fuzzy_find_products(search_q, limit=10)
        resolved_products = [r for r in resolved_products if row_key(r) not in excluded_keys]

    # --- 5. Resolve candidate categories (misspelling-tolerant) ---
    resolved_cats = fuzzy_find_categories(mentioned_category) if mentioned_category else []
    if not resolved_cats:
        resolved_cats = fuzzy_find_categories(search_q)

    is_exact_product = q_low in df["Name_lower"].values
    is_exact_category = any(c == search_q.strip() for c in resolved_cats) or search_q.strip() in all_cats

    # --- 5b. EXACT PRODUCT NAME: always wins, regardless of what intent the
    # LLM guessed. A query that IS a product's exact name (e.g. "Wheelchair
    # Emergency Stretcher") must never be reinterpreted as a category search
    # just because the LLM's intent label said "category_search" — that
    # label is a guess, an exact catalog match is a fact.
    if is_exact_product and intent != "comparison" and not (intent == "specific_detail" and detail):
        exact_row = df[df["Name_lower"] == q_low].iloc[0]
        if row_key(exact_row) not in excluded_keys:
            return {
                "answer": full_product_answer(exact_row),
                "products": rows_to_dicts([exact_row], excluded_keys),
            }

    # --- 6. SPECIFIC DETAIL: "price of X", "stock of X", etc. ---
    if intent == "specific_detail" or detail:
        if resolved_products:
            prod = resolved_products[0]
            answer = build_detail_answer(prod, detail)
            prod_dicts = rows_to_dicts([prod], excluded_keys)
            if excluded_keys and not prod_dicts:
                answer = f"Excluding {', '.join(excluded_phrases)}, " + answer
                prod_dicts = [row_to_dict(prod)]
            return {"answer": answer, "products": prod_dicts}

    # --- 7. COMPARISON: "compare X and Y" ---
    if intent == "comparison" and len(resolved_products) >= 2:
        prod_dicts = rows_to_dicts(resolved_products[:3], excluded_keys)
        comp = " | ".join(f"{p['Name']} (Price: €{p.get('Regular price', 'N/A')})" for p in prod_dicts)
        return {"answer": f"Comparison: {comp}", "products": prod_dicts}

    # --- 8. CATEGORY SEARCH: show ALL products in the category ---
    # Triggers when the LLM said category_search, or a category name
    # (possibly misspelled) was recognized and there's no equally strong,
    # exact single-product match to prefer instead. Exact-product queries
    # never reach here (handled in step 5b above).
    if resolved_cats and (intent == "category_search" or not resolved_products):
        cat_prods = get_products_by_categories(resolved_cats[:2])
        prod_dicts = rows_to_dicts(cat_prods, excluded_keys)
        if prod_dicts:
            return {
                "answer": f"Found {len(prod_dicts)} products in category '{resolved_cats[0]}' for '{q}'",
                "products": prod_dicts,
            }

    # --- 9. SUGGESTION: "suggest ...", or recommend similar products ---
    if intent == "suggestion":
        if resolved_cats:
            cat_prods = get_products_by_categories(resolved_cats[:2], limit=20)
            prod_dicts = rows_to_dicts(cat_prods[:10], excluded_keys)
            if prod_dicts:
                return {
                    "answer": f"Here are suggestions in '{resolved_cats[0]}': {', '.join(p['Name'] for p in prod_dicts[:5])}",
                    "products": prod_dicts,
                }
        if resolved_products:
            base_cat = resolved_products[0]["Categories"].split(",")[0].split(">")[0].strip().lower()
            similar = get_products_by_categories([base_cat], limit=20)
            prod_dicts = rows_to_dicts(similar[:15], excluded_keys)
            if prod_dicts:
                return {
                    "answer": f"Based on '{resolved_products[0]['Name']}', you might like: {', '.join(p['Name'] for p in prod_dicts[:5])}",
                    "products": prod_dicts,
                }
        return random_products_response(excluded_keys, excluded_phrases)

    # --- 10. SINGLE PRODUCT: show full details ---
    if resolved_products:
        prod_dicts = rows_to_dicts(resolved_products[:5], excluded_keys)
        if prod_dicts:
            if len(prod_dicts) == 1 or is_exact_product:
                p = resolved_products[0]
                return {"answer": full_product_answer(p), "products": [prod_dicts[0]]}
            answer = f"Found {len(prod_dicts)} products for '{q}': " + ", ".join(p["Name"] for p in prod_dicts[:5])
            return {"answer": answer, "products": prod_dicts}

    # --- 11. Generic "show me some products" fallback ---
    if any(phrase in q_low for phrase in ["show me", "show some", "list", "some products", "all products", "products"]):
        return random_products_response(excluded_keys, excluded_phrases)

    return {"answer": "I can only help with products from our medical store.", "products": []}



















from fastapi import APIRouter
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

router = APIRouter()

@router.post("/ingest")
def ingest_csv():
    loader = CSVLoader(
        file_path="/home/lavanya/Desktop/Lavanya/med_store/products.csv",
        csv_args={'delimiter': ',', 'quotechar': '"'}
    )
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(documents)

    embedding_function = OllamaEmbeddings(model="all-minilm")

    vector_db = Chroma.from_documents(chunks, embedding_function, persist_directory="./chroma_db")

    return {"message": f"Success! Ingested {len(chunks)} chunks into './chroma_db'"}