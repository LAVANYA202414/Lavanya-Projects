# from langchain_community.document_loaders import PyPDFLoader
from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_text_splitters import RecursiveTextSplitter
# from langchain_community.embeddings import OllamaEmbeddings
from langchain_ollama import OllamaEmbeddings
# from langchain_community.vectorstores import Chroma
from langchain_chroma import Chroma
import ollama

def load_pdf(file_path):
    reader = PdfReader(file_path)
    documents = []
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text()
        # Creates native LangChain Document objects
        documents.append(Document(page_content=text, metadata={"source": file_path, "page": page_num}))
    return documents

docs = load_pdf("/home/lavanya/Desktop/Lavanya/random/rag/Software Engineering.pdf")

text_splitter = RecursiveCharacterTextSplitter(chunk_size = 1000, chunk_overlap = 200)
chunks = text_splitter.split_documents(docs)

embedding_function = OllamaEmbeddings(model = "nomic-embed-text")
vector_db = Chroma(persist_directory="./chroma_db", embedding_function=embedding_function)

print(f"INGEST {len(chunks)} CHUNKS INTO DATABASE SUCCESSFULLY...")


def ask_rag_bot(user_query:str):
    embedding_function = OllamaEmbeddings(model="nomic-embed-text")
    vector_db = Chroma(persist_directory = "./chroma_db", embedding_function = embedding_function)

    results = vector_db.similarity_search(user_query, k=3)
    context = "\n\n".join([doc.page_content for doc in results])

    system_prompt = f"""
    You are a professional, helpful assistant. Answer the user's question using ONLY the provided context below.
    If you do not know the answer based on the context, state clearly that the information is not available.
    Do not use external knowledge or invent facts.
    
    CONTEXT:
    {context}
    """

    response = ollama.chat(
        model = "llama3",
        messages = [
            {"role":"system",
            "content": system_prompt},
            {"role":"user",
            "content": user_query}
        ]
    )

    return response["message"]["content"]


query = "what is software engineering"
print("AI Response:\n", ask_rag_bot(query))