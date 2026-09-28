# import streamlit as st
# from pypdf import PdfReader

# job_description = st.text_input("PLEASE ENTER YOUR DESCRIPTION")
# uploaded_files = st.file_uploader("Upload Multiple Documents", accept_multiple_files = True)

# if uploaded_files:
#     if len(uploaded_files) <= 50:
#         st.success(f"Successfully uploaded {len(uploaded_files)} file(s).")

#         for uploaded_file in uploaded_files:
            
#             pdf_reader = PdfReader(uploaded_file)
#             text = ""
            
#             for page in pdf_reader.pages:
#                 extracted_page = page.extract_text()
#                 if extracted_page:
#                     text += extracted_page

#             if text.strip():
#                 st.write(text)
#             else:
#                 st.warning("Could not extract text. The PDF might be scanned or empty.")
            
#             st.divider()
#     else:
#         st.error("You can only upload a maximum of 50 files.")























# import streamlit as st
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_chroma import Chroma
# from langchain_core.documents import Document
# from langchain_huggingface import HuggingFaceEmbeddings
# import ollama
# from pypdf import PdfReader
# import logging

# logging.getLogger("transformers").setLevel(logging.ERROR)

# # 1. Cache the embedding model so it only loads once into memory
# @st.cache_resource
# def load_embedding_model():
#     return HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# embedding_function = load_embedding_model()

# st.title("Resume Matcher Assistant")

# job_description = st.text_input("PLEASE ENTER YOUR DESCRIPTION")
# uploaded_files = st.file_uploader("Upload Multiple Documents", accept_multiple_files=True)

# # 2. Prevent automatic ingestion; trigger it only when clicking a button
# if uploaded_files and len(uploaded_files) <= 50:
#     if st.button("Process and Ingest Resumes"):
#         with st.spinner("Processing PDF files..."):
#             all_chunks = []

#             for uploaded_file in uploaded_files:
#                 loader = PdfReader(uploaded_file)
#                 text = ""
#                 for page in loader.pages:
#                     text += page.extract_text() or ""

#                 doc = Document(page_content=text, metadata={"source": uploaded_file.name})
#                 text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
#                 chunks = text_splitter.split_documents([doc])
#                 all_chunks.extend(chunks)

#             # 3. Create database in-memory or safely persist without reloading models
#             vector_db = Chroma.from_documents(
#                 all_chunks, 
#                 embedding_function, 
#                 persist_directory="./chroma_db"
#             )
#             st.success(f"Success! Ingested {len(all_chunks)} chunks into './chroma_db'")

# def resume_match_description(user_query: str):
#     # 4. Use the already loaded embedding function instead of creating a new one
#     vector_db = Chroma(persist_directory="./chroma_db", embedding_function=embedding_function)
    
#     results = vector_db.similarity_search(user_query, k=10)
#     context = "\n\n".join([doc.page_content for doc in results])

#     system_prompt = f"""
#     You are a professional hiring assistant. Evaluate the uploaded resumes using ONLY the provided context below.
#     Compare them against the requirements in the job description query.
#     If you do not know the answer based on the context, state clearly that the information is not available.
    
#     CONTEXT:
#     {context}
#     """

#     with st.spinner("Ollama is analyzing..."):
#         response = ollama.chat(
#             model="llama3",
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": user_query} 
#             ]
#         )
#     return response['message']['content']

# # 5. Trigger LLM generation via a dedicated action button
# if job_description:
#     if st.button("Analyze Matches"):
#         analysis_result = resume_match_description(job_description)
#         st.write(analysis_result)

































# import streamlit as st
# # from langchain_community.document_loaders import PyPDFLoader
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_chroma import Chroma
# from langchain_core.documents import Document
# from langchain_huggingface import HuggingFaceEmbeddings
# import ollama
# from pypdf import PdfReader
# import logging
# # Disables warnings from the transformers deep package scanner
# logging.getLogger("transformers").setLevel(logging.ERROR)

# @st.cache_resource
# def load_embedding_model():
#     return HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
# embedding_function = load_embedding_model()

# job_description = st.text_input("PLEASE ENTER YOUR DESCRIPTION")
# uploaded_files = st.file_uploader("Upload Multiple Documents", accept_multiple_files = True)

# if uploaded_files and len(uploaded_files) <= 50:
#     if st.button("Process and Ingest Resumes"):
#         st.success(f"Successfully uploaded {len(uploaded_files)} files.")
#         all_chunks = []

#         for uploaded_file in uploaded_files:
#         #     string_data = uploaded_file.read().decode("utf-8")
#         #     st.text(string_data)

#             loader = PdfReader(uploaded_file)
#             text = ""
#             for page in loader.pages:
#                 text += page.extract_text() or ""

#             doc = Document(page_content=text, metadata={"source": uploaded_file.name})

#             text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
#             chunks = text_splitter.split_documents([doc])
#             all_chunks.extend(chunks)
#         vector_db = Chroma.from_documents(all_chunks, embedding_function, persist_directory = "./chroma_db")
#         st.success(f"Success! Ingested {len(all_chunks)} chunks into './chroma_db'")


# def resume_match_description(user_query:str):
#     vector_db = Chroma(persist_directory = "./chroma_db", embedding_function = embedding_function)

#     results = vector_db.similarity_search(user_query, k=50)
#     # context = "\n\n".join([doc.page_content for doc in results])

#     if not results:
#         return "no matching resume found"

#     matched_resumes = {}
#     for doc in results:
#         if len(matched_resumes) >= 10:
#             break
            
#         source_name = doc.metadata.get("source", "Unknown")
#         full_text = doc.metadata.get("full_resume_text", doc.page_content)
#         matched_resumes[source_name] = full_text

#     total_found = len(matched_resumes)
#     st.info(f"Retrieved the top {total_found} unique resumes matching your criteria.")

#     context_blocks = []
#     for filename, text in matched_resumes.items():
#         context_blocks.append(f"--- START OF RESUME: {filename} ---\n{text}\n--- END OF RESUME ---")
    
#     context = "\n\n".join(context_blocks)

#     system_prompt = f"""
#     You are a professional hiring assistant. Evaluate the uploaded resumes using ONLY the provided context below.
#     Compare them against the requirements in the job description query.
#     If you do not know the answer based on the context, state clearly that the information is not available.
    
#     CONTEXT:
#     {context}
#     """

#     response = ollama.chat(
#         model="llama3",
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_query} 
#         ]
#     )
#     return response['message']['content']

# if job_description:
#     if st.button("Analyze Matches"):
#         analysis_result = resume_match_description(job_description)
#         st.write(analysis_result)












# ===============================FINAL============================



# import os
# import re
# import logging
# import streamlit as st
# import ollama
# from pypdf import PdfReader
# from docx import Document as DocxDocument
# from striprtf.striprtf import rtf_to_text
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_chroma import Chroma
# from langchain_core.documents import Document
# from langchain_huggingface import HuggingFaceEmbeddings

# logging.getLogger("transformers").setLevel(logging.ERROR)

# # Help avoid reloading the entire model
# @st.cache_resource
# def load_embedding_model():
#     return HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# embedding_function = load_embedding_model()

# st.title("Resume Matcher Assistant")

# job_description = st.text_input("PLEASE ENTER YOUR DESCRIPTION")
# uploaded_files = st.file_uploader("Upload Multiple Documents", accept_multiple_files=True)

# if uploaded_files and len(uploaded_files) <= 50:
#     if st.button("Process and Ingest Resumes"):
#         all_chunks = []
#         text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

#         for uploaded_file in uploaded_files:
#             ext = os.path.splitext(uploaded_file.name)[1].lower()
#             text = ""

#             try:
#                 # PDF
#                 if ext == ".pdf":
#                     pdf = PdfReader(uploaded_file)
#                     for page in pdf.pages:
#                         text += page.extract_text() or ""

#                 # DOCX
#                 elif ext == ".docx":
#                     doc = DocxDocument(uploaded_file)
#                     text = "\n".join(para.text for para in doc.paragraphs)

#                 # RTF
#                 elif ext == ".rtf":
#                     content = uploaded_file.read().decode("utf-8", errors="ignore")
#                     text = rtf_to_text(content)

#                 # TXT
#                 elif ext == ".txt":
#                     text = uploaded_file.read().decode("utf-8", errors="ignore")

#                 else:
#                     st.warning(f"{uploaded_file.name} is not a supported resume format.")
#                     continue

#                 # If text was successfully extracted, split it into chunks and assign metadata
#                 if text.strip():
#                     chunks = text_splitter.split_text(text)
#                     for chunk in chunks:
#                         doc_obj = Document(
#                             page_content=chunk,
#                             metadata={"source": uploaded_file.name}
#                         )
#                         all_chunks.append(doc_obj)

#             except Exception as e:
#                 st.error(f"Error processing {uploaded_file.name}: {e}")

#         if all_chunks:
#             vector_db = Chroma.from_documents(
#                 all_chunks, 
#                 embedding_function, 
#                 persist_directory="./chroma_db"
#             )
#             st.success(f"Success! Ingested {len(all_chunks)} chunks into './chroma_db'")
#         else:
#             st.warning("No text was extracted from the uploaded files.")

# # Match keyword
# def get_matching_resumes(job_description):
#     if not os.path.exists("./chroma_db"):
#         return []

#     vector_db = Chroma(
#         persist_directory="./chroma_db",
#         embedding_function=embedding_function
#     )

#     results = vector_db.similarity_search(
#         job_description,
#         k=100
#     )

#     # Search database for matching words or meaning
#     matching_files = []
#     keywords = job_description.lower().split()

#     for doc in results:
#         text = doc.page_content.lower()

#         for word in keywords:
#             if re.search(r"\b" + re.escape(word) + r"\b", text):
#                 filename = doc.metadata.get("source", "Unknown Source")

#                 if filename not in matching_files:
#                     matching_files.append(filename)
#                 break

#     return matching_files

# if job_description:
#     if st.button("Find Matching Resumes"):
#         matches = get_matching_resumes(job_description)

#         if len(matches) >= 0:
#             st.success(f"Found {len(matches)} matching resumes")
#             for file in matches:
#                 st.write(file)
#         else:
#             st.warning("No matching resumes found")
















# ==============================================================================

# import os
# import re
# import logging
# import streamlit as st
# import ollama
# from pypdf import PdfReader
# from docx import Document as DocxDocument
# from striprtf.striprtf import rtf_to_text
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_chroma import Chroma
# from langchain_core.documents import Document
# from langchain_huggingface import HuggingFaceEmbeddings
# import shutil

# logging.getLogger("transformers").setLevel(logging.ERROR)

# # Help avoid reloading the entire model
# @st.cache_resource
# def load_embedding_model():
#     return HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# embedding_function = load_embedding_model()

# st.title("Resume Matcher Assistant")

# job_description = st.text_input("PLEASE ENTER YOUR DESCRIPTION")
# uploaded_files = st.file_uploader("Upload Multiple Documents", accept_multiple_files=True)

# if uploaded_files and len(uploaded_files) <= 50:
#     if st.button("Process and Ingest Resumes"):
#         all_chunks = []
#         text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

#         for uploaded_file in uploaded_files:
#             ext = os.path.splitext(uploaded_file.name)[1].lower()
#             text = ""

#             try:
#                 # PDF
#                 if ext == ".pdf":
#                     pdf = PdfReader(uploaded_file)
#                     for page in pdf.pages:
#                         text += page.extract_text() or ""

#                 # DOCX
#                 elif ext == ".docx":
#                     doc = DocxDocument(uploaded_file)
#                     text = "\n".join(para.text for para in doc.paragraphs)

#                 # RTF
#                 elif ext == ".rtf":
#                     content = uploaded_file.read().decode("utf-8", errors="ignore")
#                     text = rtf_to_text(content)

#                 # TXT
#                 elif ext == ".txt":
#                     text = uploaded_file.read().decode("utf-8", errors="ignore")

#                 else:
#                     st.warning(f"{uploaded_file.name} is not a supported resume format.")
#                     continue

#                 # If text was successfully extracted, split it into chunks and assign metadata
#                 if text.strip():
#                     chunks = text_splitter.split_text(text)
#                     for chunk in chunks:
#                         doc_obj = Document(
#                             page_content=chunk,
#                             metadata={"source": uploaded_file.name}
#                         )
#                         all_chunks.append(doc_obj)

#             except Exception as e:
#                 st.error(f"Error processing {uploaded_file.name}: {e}")

#         if all_chunks:
#             try:
#                 db = Chroma(
#                     persist_directory = "./chroma_db",
#                     embedding_function = embedding_function
#                 )
#                 db.delete_collection()

#             except Exception:
#                 pass

#             vector_db = Chroma.from_documents(
#                 all_chunks, 
#                 embedding_function, 
#                 persist_directory="./chroma_db"
#             )
#             st.success(f"Success! Ingested {len(all_chunks)} chunks into './chroma_db'")
#         else:
#             st.warning("No text was extracted from the uploaded files.")

# # Match keyword
# def get_matching_resumes(job_description):
#     if not os.path.exists("./chroma_db"):
#         return []

#     vector_db = Chroma(
#         persist_directory="./chroma_db",
#         embedding_function=embedding_function
#     )

#     results = vector_db.similarity_search(
#         job_description,
#         k=100
#     )

#     # Search database for matching words or meaning
#     matching_files = []
#     keywords = job_description.lower().split()

#     for doc in results:
#         text = doc.page_content.lower()

#         for word in keywords:
#             if re.search(r"\b" + re.escape(word) + r"\b", text):
#                 filename = doc.metadata.get("source", "Unknown Source")

#                 if filename not in matching_files:
#                     matching_files.append(filename)
#                 break

#     return matching_files

# if job_description:
#     if st.button("Find Matching Resumes"):
#         matches = get_matching_resumes(job_description)

#         if len(matches) > 0:
#             st.success(f"Found {len(matches)} matching resumes")
#             for file in matches:
#                 st.write(file)
#         else:
#             st.warning("No matching resumes found")
















# import os
# import re
# import logging
# import streamlit as st
# from pypdf import PdfReader
# from langchain_chroma import Chroma
# from docx import Document as DocxDocument
# from striprtf.striprtf import rtf_to_text
# from langchain_core.documents import Document
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_text_splitters import RecursiveCharacterTextSplitter

# logging.getLogger("transformers").setLevel(logging.ERROR)

# # Cache embedding model to prevent reloading
# @st.cache_resource
# def load_embedding_model():
#     return HuggingFaceEmbeddings(model_name="./saved_embedding_model")

# embedding_function = load_embedding_model()

# st.title("Resume Matcher Assistant")

# # --- UI Inputs ---
# job_description = st.text_area("Enter Job Description for Keyword Matching:")
# uploaded_files = st.file_uploader("Upload Resumes (Max 50)", accept_multiple_files=True)

# # --- Logic: Core Functions ---

# def get_matching_resumes(query_text: str):
#     if not os.path.exists("./chroma_db"):
#         return []
        
#     vector_db = Chroma(
#         persist_directory="./chroma_db", 
#         embedding_function=embedding_function
#     )

#     results = vector_db.similarity_search(query_text, k=5)
#     matching_files = []
#     keywords = query_text.lower().split()

#     for doc in results:
#         text = doc.page_content.lower()
#         for word in keywords:
#             if re.search(r"\b" + re.escape(word) + r"\b", text):
#                 filename = doc.metadata.get("source", "Unknown Source")
#                 if filename not in matching_files:
#                     matching_files.append(filename)
#                 break
#     return matching_files


# def ask_ai_assistant(user_query: str):
#     if not os.path.exists("./chroma_db"):
#         return "Please upload and process resumes first."
        
#     vector_db = Chroma(
#         persist_directory="./chroma_db", 
#         embedding_function=embedding_function
#     )

#     results = vector_db.similarity_search(user_query, k=3)
#     context = "\n\n".join([doc.page_content for doc in results])

#     system_prompt = f"""
#     You are a professional, helpful assistant. Answer the user's question using ONLY the provided context below.
#     If you do not know the answer based on the context, state clearly that the information is not available.
#     Do not use external knowledge or invent facts.
    
#     CONTEXT:
#     {context}
#     """
#     try:
#         response = ollama.chat(
#             model="llama3",
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": user_query} 
#             ]
#         )
#         return response['message']['content']
#     except Exception as e:
#         return f"Ollama Error: {e}"



# # Job Description Matcher
# if job_description:
#     if st.button("Find Matching Resumes"):
#         with st.spinner("Scanning resumes..."):
#             matches = get_matching_resumes(job_description)
#             if len(matches) > 0:
#                 st.success(f"Found {len(matches)} matching resumes based on context and keywords:")
#                 for file in matches:
#                     st.write(file)
#             else:
#                 st.warning("No highly relevant resumes matched those keywords.")

# st.write("---")

# # AI Assistant Q&A
# user_question = st.text_input("Ask a question about the uploaded resumes (e.g., 'Who knows Kubernetes?'):")

# if user_question:
#     if st.button("Ask AI Assistant"):
#         with st.spinner("Analyzing resumes via Llama3..."):
#             answer = ask_ai_assistant(user_question)
#             st.info(answer)

# st.write("---")

# # File Processing & Ingestion
# if uploaded_files:
#     if len(uploaded_files) > 50:
#         st.error("Please upload a maximum of 50 files at once.")

#     elif st.button("Process and Ingest Resumes"):
#         all_chunks = []
#         text_splitter = RecursiveCharacterTextSplitter(
#             chunk_size=1000,
#             chunk_overlap=200
#         )

#         for uploaded_file in uploaded_files:
#             ext = os.path.splitext(uploaded_file.name)[1].lower()
#             text = ""

#             try:
#                 if ext == ".pdf":
#                     pdf = PdfReader(uploaded_file)
#                     for page in pdf.pages:
#                         text += page.extract_text() or ""

#                 elif ext == ".docx":
#                     doc = DocxDocument(uploaded_file)
#                     text = "\n".join(para.text for para in doc.paragraphs)

#                 elif ext == ".rtf":
#                     content = uploaded_file.read().decode(
#                         "utf-8",
#                         errors="ignore"
#                     )
#                     text = rtf_to_text(content)

#                 elif ext == ".txt":
#                     text = uploaded_file.read().decode(
#                         "utf-8",
#                         errors="ignore"
#                     )

#                 else:
#                     st.warning(
#                         f"{uploaded_file.name} is not a supported format."
#                     )
#                     continue

#                 if text.strip():
#                     chunks = text_splitter.split_text(text)

#                     for chunk in chunks:
#                         doc_obj = Document(
#                             page_content=chunk,
#                             metadata={"source": uploaded_file.name}
#                         )
#                         all_chunks.append(doc_obj)

#             except Exception as e:
#                 st.error(
#                     f"Error processing {uploaded_file.name}: {e}"
#                 )

#         if all_chunks:
#             try:
#                 # Basic cleanup before rewrite
#                 db = Chroma(
#                     persist_directory="./chroma_db",
#                     embedding_function=embedding_function
#                 )
#                 db.delete_collection()

#             except Exception:
#                 pass

#             vector_db = Chroma.from_documents(
#                 documents=all_chunks,
#                 embedding=embedding_function,
#                 persist_directory="./chroma_db"
#             )

#             st.success(
#                 f"Success! Ingested {len(all_chunks)} chunks into Chroma DB."
#             )

#         else:
#             st.warning(
#                 "No text could be extracted from the provided files."
#             )



# import os
# import re
# import streamlit as st
# from pypdf import PdfReader
# from docx import Document
# from striprtf.striprtf import rtf_to_text
# from langchain_huggingface import HuggingFaceEmbeddings
# from sklearn.metrics.pairwise import cosine_similarity
# import concurrent.futures
# import time
# import logging

# # Mute all warning logs coming from the transformers library
# logging.getLogger("transformers").setLevel(logging.ERROR)


# # ─────────────────────────────────────────────
# # PAGE CONFIG
# # ─────────────────────────────────────────────
# st.set_page_config(page_title="Resume Matcher", page_icon="📄")
# st.title("📄 Resume Matcher — 100% Local")


# # ─────────────────────────────────────────────
# # LOAD EMBEDDING MODEL (cached so it only loads once)
# #
# # Change model_name to any sentence-transformers model.
# # Fast options:
# #   - "all-MiniLM-L6-v2"        (80MB, very fast)
# #   - "all-MiniLM-L12-v2"       (120MB, slightly better)
# #   - "./saved_embedding_model"  (your local saved model)
# # ─────────────────────────────────────────────
# @st.cache_resource
# def load_model():
#     st.info("Loading embedding model (only once)...")
#     return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# embedding_model = load_model()


# # ─────────────────────────────────────────────
# # STEP 1: EXTRACT TEXT FROM FILE
# # ─────────────────────────────────────────────
# def extract_text(file) -> str:
#     ext = os.path.splitext(file.name)[1].lower()

#     if ext == ".pdf":
#         pdf = PdfReader(file)
#         return "".join(page.extract_text() or "" for page in pdf.pages)

#     if ext == ".docx":
#         doc = Document(file)
#         return "\n".join(p.text for p in doc.paragraphs)

#     if ext == ".rtf":
#         content = file.read().decode("utf-8", errors="ignore")
#         return rtf_to_text(content)

#     if ext == ".txt":
#         return file.read().decode("utf-8", errors="ignore")

#     return ""


# # ─────────────────────────────────────────────
# # STEP 2: READ ALL FILES IN PARALLEL
# #
# # Instead of reading one file at a time, we read
# # all files at the same time using threads.
# # 8 resumes at once → much faster total read time.
# # ─────────────────────────────────────────────
# def read_all_resumes(uploaded_files) -> list[dict]:
#     def read_one(file):
#         try:
#             text = extract_text(file)
#             if text.strip():
#                 return {"filename": file.name, "text": text}
#         except Exception as e:
#             st.warning(f"⚠️ Could not read {file.name}: {e}")
#         return None

#     with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
#         results = list(executor.map(read_one, uploaded_files))

#     return [r for r in results if r is not None]


# # ─────────────────────────────────────────────
# # STEP 3: EMBED AND SCORE ALL RESUMES
# #
# # Key fix from your original code:
# # - We embed ALL resumes in ONE batch call
# #   instead of one by one → much faster
# # - We only use first 1000 chars per resume
# #   (enough context, keeps embedding fast)
# # ─────────────────────────────────────────────
# def score_resumes(job_description: str, resumes: list[dict]) -> list[dict]:

#     # Embed job description (single query)
#     job_embedding = embedding_model.embed_query(job_description)

#     # Embed all resumes in ONE batch (fastest way)
#     resume_texts = [r["text"][:1000] for r in resumes]
#     resume_embeddings = embedding_model.embed_documents(resume_texts)

#     # Score each resume against the job description
#     for resume, embedding in zip(resumes, resume_embeddings):
#         score = cosine_similarity([job_embedding], [embedding])[0][0]
#         resume["score"] = float(score)

#     # Sort highest score first
#     return sorted(resumes, key=lambda x: x["score"], reverse=True)


# # ─────────────────────────────────────────────
# # STEP 4: EXTRACT KEY INFO FROM RESUME TEXT
# #
# # Simple rule-based parsing to pull out:
# # - Candidate name (first non-empty line)
# # - Email address
# # - Phone number
# # - Skills (looks for a "Skills" section)
# # - Years of experience (looks for "X years" pattern)
# #
# # This replaces the AI analysis step completely.
# # No API needed — just text parsing.
# # ─────────────────────────────────────────────
# def extract_info(text: str) -> dict:
#     lines = [l.strip() for l in text.splitlines() if l.strip()]

#     # Name: assume first non-empty line is the candidate's name
#     name = lines[0] if lines else "Not Found"

#     # Email: find anything matching email pattern
#     email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
#     email = email_match.group() if email_match else "Not Found"

#     # Phone: find 10+ digit numbers (handles spaces/dashes)
#     phone_match = re.search(r"(\+?\d[\d\s\-]{9,15})", text)
#     phone = phone_match.group().strip() if phone_match else "Not Found"

#     # Years of experience: find "X years" or "X+ years" pattern
#     exp_match = re.search(r"(\d+\+?\s+years?)", text, re.IGNORECASE)
#     experience = exp_match.group() if exp_match else "Not Found"

#     # Skills: find text after a "Skills" heading, grab next 2 lines
#     skills = "Not Found"
#     for i, line in enumerate(lines):
#         if re.search(r"\bskills?\b", line, re.IGNORECASE):
#             # Grab up to 2 lines after the "Skills" heading
#             skill_lines = lines[i+1 : i+3]
#             if skill_lines:
#                 skills = " | ".join(skill_lines)
#             break

#     return {
#         "name": name,
#         "email": email,
#         "phone": phone,
#         "experience": experience,
#         "skills": skills,
#     }


# # ─────────────────────────────────────────────
# # UI
# # ─────────────────────────────────────────────
# job_description = st.text_area(" Enter Job Description", height=180)

# uploaded_files = st.file_uploader(
#     " Upload Resumes (Max 50)",
#     accept_multiple_files=True,
#     type=["pdf", "docx", "rtf", "txt"]
# )

# if uploaded_files:

#     if len(uploaded_files) > 50:
#         st.error(" Maximum 50 resumes allowed.")
#         st.stop()

#     if st.button(" Match Resumes", type="primary"):

#         if not job_description.strip():
#             st.error(" Please enter a job description.")
#             st.stop()

#         total_start = time.time()

#         # --- Read files in parallel ---
#         with st.spinner(f"Reading {len(uploaded_files)} resumes..."):
#             t = time.time()
#             resumes = read_all_resumes(uploaded_files)
#             st.write(f" Read {len(resumes)} resumes in **{time.time() - t:.2f}s**")

#         if not resumes:
#             st.warning("No valid resume text found.")
#             st.stop()

#         # --- Score with embeddings ---
#         with st.spinner("Scoring resumes with embedding model..."):
#             t = time.time()
#             scored = score_resumes(job_description, resumes)
#             top_10 = scored[:10]
#             st.write(f" Scored {len(resumes)} resumes in **{time.time() - t:.2f}s**")

#         # --- Show results table ---
#         st.subheader(" Top 10 Matching Resumes")

#         for i, resume in enumerate(top_10, 1):
#             info = extract_info(resume["text"])
#             match_pct = resume["score"] * 100

#             # Color the score: green > 60%, orange > 40%, red below
#             if match_pct >= 60:
#                 color = ""
#             elif match_pct >= 40:
#                 color = ""
#             else:
#                 color = ""

#             with st.expander(
#                 f"{i}. {info['name']} — {color} {match_pct:.1f}% match  | {resume['filename']}"
#             ):
#                 col1, col2 = st.columns(2)

#                 with col1:
#                     st.markdown(f"** Email:** {info['email']}")
#                     st.markdown(f"** Phone:** {info['phone']}")
#                     st.markdown(f"**Experience:** {info['experience']}")

#                 with col2:
#                     st.markdown(f"** Skills:** {info['skills']}")
#                     st.markdown(f"** Match Score:** {match_pct:.2f}%")

#                 st.markdown("** Resume Preview:**")
#                 st.text(resume["text"][:500] + "...")

#         st.success(f" Total time: **{time.time() - total_start:.1f} seconds**")



























# ==================================================================================================
# ==================================================================================================

# import logging
# import os
# import time
# from docx import Document
# from langchain_huggingface import HuggingFaceEmbeddings
# from pypdf import PdfReader
# from sklearn.metrics.pairwise import cosine_similarity
# from striprtf.striprtf import rtf_to_text
# import streamlit as st

# logging.getLogger("transformers").setLevel(logging.ERROR)

# # It loads the embedidng mdoel into memory exactly once (prevent from being reload)
# @st.cache_resource
# def load_embedding_model():
#     return HuggingFaceEmbeddings(model_name="./saved_embedding_model")

# # It stores the results of the embedding calculations
# @st.cache_data
# def get_resume_embeddings(texts):
#     return embedding_model.embed_documents(texts)

# # Calls function and stores model object
# embedding_model = load_embedding_model()

# st.title("Resume Matcher Assistant")

# # Create large textbox
# job_description = st.text_area("Enter Job Description", height=200)

# # Create upload
# uploaded_files = st.file_uploader(
#     "Upload Resumes (Max 50)", accept_multiple_files=True
# )

# # Text extraction function
# def extract_text(file):
#     # Get extension
#     ext = os.path.splitext(file.name)[1].lower()
#     text = ""

#     if ext == ".pdf":
#         pdf = PdfReader(file)
#         text = "\n".join(page.extract_text() or "" for page in pdf.pages)

#     elif ext == ".docx":
#         doc = Document(file)
#         text = "\n".join(p.text for p in doc.paragraphs)

#     elif ext == ".rtf":
#         content = file.read().decode("utf-8", errors="ignore")
#         text = rtf_to_text(content)

#     elif ext == ".txt":
#         text = file.read().decode("utf-8", errors="ignore")

#     return text.strip()


# def is_valid_resume(text):
#     words = text.split()
#     # Reject tiny documents
#     if len(words) < 30:
#         return False

#     return True


# def get_score(item):
#     return item["score"]


# if uploaded_files:
#     if len(uploaded_files) > 50:
#         st.error("Maximum 50 resumes allowed.")
#     # Runs matching only when button clicked.
#     elif st.button("Match Resumes"):
#         # if checkbox empty
#         if not job_description.strip():
#             st.error("Please enter a job description.")
#             # stops execution
#             st.stop()
#         # valid resumes
#         resumes = []

#         with st.spinner("Reading resumes..."):
#             for file in uploaded_files:
#                 try:
#                     text = extract_text(file)
#                     if is_valid_resume(text):
#                         resumes.append({"filename": file.name, "text": text})

#                 except Exception as e:
#                     st.error(f"Error in {file.name}: {e}")

#         if not resumes:
#             st.warning("No valid resume text found.")
#             st.stop()

#         st.success(f"{len(resumes)} resumes processed.")

#         with st.spinner("Calculating scores..."):
#             # Start timer.
#             start = time.time()
#             job_embedding = embedding_model.embed_query(job_description)
#             st.write(f"Job embedding time: {time.time() - start:.2f} sec")

#             # Only first 3000 characters used.
#             resume_texts = [resume["text"] for resume in resumes]

#             start = time.time()
#             # creates vectors of all resumes
#             resume_embeddings = get_resume_embeddings(resume_texts)
#             st.write(f"Resume embedding time: {time.time() - start:.2f} sec")

#             results = []
#             # pair resumes and embeddings
#             for resume, resume_embedding in zip(resumes, resume_embeddings):
#                 # computes similarity
#                 score = cosine_similarity([job_embedding], [resume_embedding])[0][0]

#                 results.append(
#                     {
#                         "filename": resume["filename"],
#                         "text": resume["text"],
#                         "score": score,
#                     }
#                 )

#         # Sort results
#         results.sort(key=get_score, reverse=True)

#         # Top 10
#         top_resumes = results[:10]

#         st.subheader("Top 10 Matching Resumes")

#         for index, resume in enumerate(top_resumes, start=1):
#             st.write(
#                 f"{index}. {resume['filename']} ",
#                 # f"({resume['score'] * 100:.2f}% Match)",
#             )

# ==================================================================================================
# ==================================================================================================












# import os
# import time
# import ollama
# import logging
# import streamlit as st
# from docx import Document
# from pypdf import PdfReader
# from striprtf.striprtf import rtf_to_text
# from sklearn.metrics.pairwise import cosine_similarity
# from langchain_huggingface import HuggingFaceEmbeddings

# logging.getLogger("transformers").setLevel(logging.ERROR)

# # It loads the embedidng mdoel into memory exactly once (prevent from being reload)
# @st.cache_resource
# def load_embedding_model():
#     return HuggingFaceEmbeddings(model_name="./saved_embedding_model")

# # It stores the results of the embedding calculations
# @st.cache_data
# def get_resume_embeddings(texts):
#     return embedding_model.embed_documents(texts)

# # Calls function and stores model object
# embedding_model = load_embedding_model()

# st.title("Resume Matcher Assistant")

# # Create large textbox
# job_description = st.text_area("Enter Job Description", height=200)

# # Create upload files
# uploaded_files = st.file_uploader(
#     "Upload Resumes (Max 50)", accept_multiple_files=True,
# )


# # Text extraction function
# def extract_resume_text(file):
#     # Get extension
#     ext = os.path.splitext(file.name)[1].lower()
#     text = ""

#     if ext == ".pdf":
#         pdf = PdfReader(file)
#         # page.extract_text() -> belongs to pypdf library
#         text = "\n".join(page.extract_text() or "" for page in pdf.pages)

#     elif ext == ".docx":
#         doc = Document(file)
#         text = "\n".join(p.text for p in doc.paragraphs)

#     elif ext == ".rtf":
#         content = file.read().decode("utf-8", errors="ignore")
#         text = rtf_to_text(content)

#     elif ext == ".txt":
#         text = file.read().decode("utf-8", errors="ignore")

#     return text.strip()


# def is_valid_resume(text):
#     words = text.split()
#     # Reject tiny documents
#     if len(words) < 30:
#         return False

#     return True


# def get_score(item):
#     return item["score"]


# def generate_llama_analysis(resume, user_query):
#     for resume in top_resumes:
#         print("====> RESUMES \n", resume)
#         context.append(
#             f"--- START OF RESUME: {resume['filename']} (Match Score: {resume['score'] * 100:.2f}%) ---\n"
#             f"{resume['text']}\n"
#             f"--- END OF RESUME ---"
#         )
    
#     context_text = "\n\n".join(context)

#     system_prompt = f"""
#     You are a professional hiring assistant. Evaluate the uploaded resumes using ONLY the provided context below.
#     Compare them against the requirements in the job description query. Provide an analytical breakdown of why these candidates match.
#     If you do not know the answer based on the context, state clearly that the information is not available.
    
#     CONTEXT:
#     {context_text}
#     """

#     response = ollama.chat(
#         model="llama3",
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_query} 
#         ]
#     )
#     return response['message']['content']


# if uploaded_files:
#     if len(uploaded_files) > 50:
#         st.error("Maximum 50 resumes allowed.")
#     # Runs matching only when button clicked.
#     elif st.button("Match and Analyze Resumes"):
#         # if checkbox empty
#         if not job_description.strip():
#             st.error("Please enter a job description.")
#             # stops execution
#             st.stop()
#         # valid resumes
#         resumes = []

#         with st.spinner("Reading resumes..."):
#             for file in uploaded_files:
#                 try:
#                     text = extract_resume_text(file)
#                     if is_valid_resume(text):
#                         resumes.append({"filename": file.name, "text": text})

#                 except Exception as e:
#                     st.error(f"Error in {file.name}: {e}")

#         if not resumes:
#             st.warning("No valid resume text found.")
#             st.stop()

#         st.success(f"{len(resumes)} resumes processed.")

#         with st.spinner("Calculating scores..."):
#             # Start timer.
#             start = time.time()
#             job_embedding = embedding_model.embed_query(job_description)
#             st.write(f"Job embedding time: {time.time() - start:.2f} sec")

#             # Only first 3000 characters used.
#             resume_texts = [resume["text"] for resume in resumes]

#             start = time.time()
#             # creates vectors of all resumes
#             resume_embeddings = get_resume_embeddings(resume_texts)
#             st.write(f"Resume embedding time: {time.time() - start:.2f} sec")

#             results = []
#             # pair resumes and embeddings
#             for resume, resume_embedding in zip(resumes, resume_embeddings):
#                 # computes similarity
#                 score = cosine_similarity([job_embedding], [resume_embedding])[0][0]

#                 results.append(
#                     {
#                         "filename": resume["filename"],
#                         "text": resume["text"],
#                         "score": score,
#                     }
#                 )

#         # Sort results
#         results.sort(key=get_score, reverse=True)

#         # Top 10
#         top_resumes = results[:10]

#         st.subheader("Top 10 Matching Resumes")

#         for index, resume in enumerate(top_resumes, start=1):
#             st.write(
#                 f"{index}. {resume['filename']} ",
#                 # f"({resume['score'] * 100:.2f}% Match)",
#             )
#         st.subheader(" Llama 3 Deep Analysis")
#         with st.spinner("Llama 3 is analysing the best candidates matchin score..."):
#             try:
#                 analysis_result = generate_llama_analysis(top_resumes, job_description)
#                 st.markdown(analysis_result)
#             except Exception as e:
#                 st.error(f"Failed to generate LLM analysis: {e}. Check if Ollama is running.")


































# import os
# import time
# import ollama
# import logging
# import streamlit as st
# from docx import Document
# from pypdf import PdfReader
# from striprtf.striprtf import rtf_to_text
# from sklearn.metrics.pairwise import cosine_similarity
# from langchain_huggingface import HuggingFaceEmbeddings


# logging.getLogger("transformers").setLevel(logging.ERROR)


# # It loads the embedidng mdoel into memory exactly once (prevent from being reload)
# @st.cache_resource
# def load_embedding_model():
#     return HuggingFaceEmbeddings(model_name="./saved_embedding_model")


# # It stores the results of the embedding calculations
# @st.cache_data
# def get_resume_embeddings(texts):
#     return embedding_model.embed_documents(texts)


# # Calls function and stores model object
# embedding_model = load_embedding_model()


# st.title("Resume Matcher Assistant")


# # Create large textbox
# job_description = st.text_area("Enter Job Description", height=200)


# # Create upload files
# uploaded_files = st.file_uploader(
#     "Upload Resumes (Max 50)", accept_multiple_files=True,
# )


# # Text extraction function
# def extract_resume_text(file):
#     # Get extension
#     ext = os.path.splitext(file.name)[1].lower()
#     text = ""

#     if ext == ".pdf":
#         pdf = PdfReader(file)
#         # page.extract_text() -> belongs to pypdf library
#         text = "\n".join(page.extract_text() or "" for page in pdf.pages)

#     elif ext == ".docx":
#         doc = Document(file)
#         text = "\n".join(p.text for p in doc.paragraphs)

#     elif ext == ".rtf":
#         content = file.read().decode("utf-8", errors="ignore")
#         text = rtf_to_text(content)

#     elif ext == ".txt":
#         text = file.read().decode("utf-8", errors="ignore")

#     return text.strip()


# def is_valid_resume(text):
#     words = text.split()
#     # Reject tiny documents
#     if len(words) < 30:
#         return False

#     return True


# def get_score(item):
#     return item["score"]


# def generate_llama_analysis(resume, user_query):
#     text = resume['text']

#     system_prompt = f"""
#         You are a hiring evaluator. You are a professional hiring assistant.
#         Evaluate the uploaded resumes using ONLY the provided context below.

#         Job Description:
#         {job_description}

#         Analyze the candidate resume.

#         Return:
#         1. Match Score (0-100)
#         4. Should this candidate be shortlisted? (YES/NO)
#         5. Reasoning in 2 bullet points

#         Be strict.
#         """
#     user_message = f"""
#     CANDIDATE RESUME ({resume['filename']}):
#     {text}
#     """
#     # for resume in top_resumes:
#     #     print("====> RESUMES \n", resume)
#     #     context.append(
#     #         f"--- START OF RESUME: {resume['filename']} (Match Score: {resume['score'] * 100:.2f}%) ---\n"
#     #         f"{resume['text']}\n"
#     #         f"--- END OF RESUME ---"
#     #     )
    
#     # context_text = "\n\n".join(context)

#     # system_prompt = f"""
#     # You are a professional hiring assistant. Evaluate the uploaded resumes using ONLY the provided context below.
#     # Compare them against the requirements in the job description query. Provide an analytical breakdown of why these candidates match.
#     # If you do not know the answer based on the context, state clearly that the information is not available.
    
#     # CONTEXT:
#     # {context_text}
#     # """

#     response = ollama.chat(
#         model="llama3.2:3b",
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_message} 
#         ]
#     )
#     return response['message']['content']


# def text_chunking(text):
#     if text.strip():
#         chunks = text_splitter.split_text(text)
#         for chunk in chunks:
#             doc = Document(
#                 page_content = chunk,
#                 metadata = {"source":uploaded_file.name}
#             )
#             all_chunks.append(doc_obj)
#     else:
#         st.error(f"Error processing text")

# if uploaded_files:
#     if len(uploaded_files) > 50:
#         st.error("Maximum 50 resumes allowed.")
#     # Runs matching only when button clicked.
#     elif st.button("Match and Analyze Resumes"):
#         # if checkbox empty
#         if not job_description.strip():
#             st.error("Please enter a job description.")
#             # stops execution
#             st.stop()
#         # valid resumes
#         resumes = []

#         with st.spinner("Reading resumes..."):
#             for file in uploaded_files:
#                 try:
#                     text = extract_resume_text(file)
#                     if is_valid_resume(text):
#                         resumes.append({"filename": file.name, "text": text})

#                 except Exception as e:
#                     st.error(f"Error in {file.name}: {e}")

#         if not resumes:
#             st.warning("No valid resume text found.")
#             st.stop()

#         st.success(f"{len(resumes)} resumes processed.")

#         with st.spinner("Calculating scores..."):
#             # Start timer.
#             start = time.time()
#             job_embedding = embedding_model.embed_query(job_description)
#             st.write(f"Job embedding time: {time.time() - start:.2f} sec")

#             # Only first 3000 characters used.
#             resume_texts = [resume["text"] for resume in resumes]

#             start = time.time()
#             # creates vectors of all resumes
#             resume_embeddings = get_resume_embeddings(resume_texts)
#             st.write(f"Resume embedding time: {time.time() - start:.2f} sec")

#             results = []
#             # pair resumes and embeddings
#             for resume, resume_embedding in zip(resumes, resume_embeddings):
#                 # computes similarity
#                 score = cosine_similarity([job_embedding], [resume_embedding])[0][0]

#                 results.append(
#                     {
#                         "filename": resume["filename"],
#                         "text": resume["text"],
#                         "score": score,
#                     }
#                 )

#         # Sort results
#         results.sort(key=get_score, reverse=True)

#         # Top 10
#         top_resumes = results[:10]

#         st.subheader("Top 10 Matching Resumes")

#         for index, resume in enumerate(top_resumes, start=1):
#             st.write(
#                 f"{index}. {resume['filename']} ",
#                 # f"({resume['score'] * 100:.2f}% Match)",
#             )
#         st.subheader(" Llama 3 Deep Analysis")
#         for index, resume in enumerate(top_resumes[:10], start = 1):
#             # st.write(f" {index}. {resume['filename']} (Score: {resume['score'] * 100:.2f}%)")
#             with st.spinner(f"Analyzing candidate {index}..."):
#                 try:
#                     start = time.time()
#                     analysis_result = generate_llama_analysis(resume, job_description)
#                     print(f"Llama time: {time.time()-start:.2f}")
#                     st.write(f"### {index}. {resume['filename']}")
#                     st.info(analysis_result)
#                 except Exception as e:
#                     st.error(f"Failed to analyze {resume['filename']}: {e}")












# import os
# import time
# import ollama
# import logging
# import streamlit as st
# from docx import Document
# from pypdf import PdfReader
# from striprtf.striprtf import rtf_to_text
# from sklearn.metrics.pairwise import cosine_similarity
# from langchain_huggingface import HuggingFaceEmbeddings

# logging.getLogger("transformers").setLevel(logging.ERROR)

# # Load once and reuse
# @st.cache_resource
# def load_embedding_model():
#     return HuggingFaceEmbeddings(model_name="./saved_embedding_model")

# # It stores the results of the embedding calculations
# # cache_data reuires hashable arguments
# @st.cache_data # => input: tuple[str] | output : list[str]
# def get_resume_embeddings(chunks):
#     return embedding_model.embed_documents(list(chunks))

# @st.cache_data
# def get_job_embedding(job_description):
#     return embedding_model.embed_query(job_description)

# # Calls function and stores model object
# embedding_model = load_embedding_model()

# st.title("Resume Matcher Assistant")

# # Create large textbox
# job_description = st.text_area("Enter Job Description", height=200)

# # Create upload files => list
# uploaded_files = st.file_uploader(
#     "Upload Resumes (Max 50)",
#     accept_multiple_files=True,
# )

# # Text extraction function => str
# def extract_resume_text(file):
#     ext = os.path.splitext(file.name)[1].lower() # Get extension
#     text = ""
#     if ext == ".pdf":
#         pdf = PdfReader(file)
#         # page.extract_text() -> belongs to pypdf library
#         text = "\n".join(page.extract_text() or "" for page in pdf.pages)

#     elif ext == ".docx":
#         doc = Document(file)
#         text = "\n".join(p.text for p in doc.paragraphs)

#     elif ext == ".rtf":
#         content = file.read().decode("utf-8", errors="ignore")
#         text = rtf_to_text(content)

#     elif ext == ".txt":
#         text = file.read().decode("utf-8", errors="ignore")
#     return text.strip()

# def is_valid_resume(text):
#     words = text.split()
#     if len(words) < 30: # Reject tiny documents
#         return False
#     return True

# def get_score(item):
#     return item["score"]

# def split_resume(text, chunk_size=500): # input=> str | output => list[str]
#     words = text.split()
#     chunks = []
#     for i in range(0, len(words), chunk_size):    # 0, 500, 1000, 1500...
#         # Creates chunk.
#         chunk = " ".join(words[i:i + chunk_size])
#         chunks.append(chunk)
#     return chunks


# def generate_llama_analysis(resume, user_query):
#     system_prompt = f"""
#     You are a Senior Technical Recruiter and Hiring Manager.
#     Your task is to evaluate the candidate ONLY against the Job Description.
#     JOB DESCRIPTION:
#     {job_description}

#     IMPORTANT RULES:
#     1. Evaluate actual skills, experience, technologies, responsibilities, and achievements from the resume.
#     2. ATS Similarity Score is ONLY a semantic retrieval score.
#     It is NOT the final hiring score.
#     Use it only as a supporting signal.
#     3. Do NOT assume skills that are not explicitly mentioned.
#     4. Penalize missing critical requirements.
#     5. Reward direct experience that closely matches the role.
#     6. Be strict and realistic as a real recruiter.

#     SCORING GUIDE:
#     90-100 = Exceptional Match
#     - Meets nearly all requirements
#     - Strong relevant experience
#     - Immediate shortlist

#     75-89 = Strong Match
#     - Meets most requirements
#     - Minor gaps only
#     - Should be shortlisted

#     60-74 = Moderate Match
#     - Meets some requirements
#     - Noticeable gaps
#     - Shortlist only if applicant pool is small

#     40-59 = Weak Match
#     - Significant missing requirements
#     - Normally not shortlisted

#     0-39 = Poor Match
#     - Major mismatch
#     - Reject

#     SHORTLIST RULE:
#     Score >= 75 → YES
#     Score < 75 → NO

#     Return EXACTLY in this format:
#     Match Score: <0-100>

#     Shortlist: <YES/NO>

#     Strengths:
#     - Point 1
#     - Point 2

#     Gaps:
#     - Point 1
#     - Point 2

#     Final Assessment:
#     <2-3 sentence summary explaining why the candidate should or should not move forward>
#     The shortlist decision MUST match the score.
#     """
#     user_message = f"""
#     ATS Similarity Score: {resume['score'] * 100:.2f}
#     IMPORTANT:
#     This is only a semantic similarity score produced by an embedding model.
#     Do NOT use it as the final hiring score.
#     Candidate:
#     {resume['filename']}
#     Resume:
#     {resume['text']}
#     """
#     # Sends prompt
#     response = ollama.chat(
#         model="llama3.2:3b",
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_message}])
#     return response["message"]["content"]


# # def text_chunking(text):
# #     if text.strip():
# #         chunks = text_splitter.split_text(text)

# #         for chunk in chunks:
# #             doc = Document(
# #                 page_content=chunk,
# #                 metadata={"source": uploaded_file.name}
# #             )
# #             all_chunks.append(doc_obj)

# #     else:
# #         st.error(f"Error processing text")

# ######### VALIDATION AND EXTRACTION #########
# if uploaded_files:
#     if len(uploaded_files) > 50:
#         st.error("Maximum 50 resumes allowed.")
#     # Runs matching only when button clicked.
#     elif st.button("Match Resumes"):
#         # if checkbox empty
#         if not job_description.strip():
#             st.error("Please enter a job description.")
#             # stops execution
#             st.stop()
#         resumes = [] # valid resumes
#         with st.spinner("Reading resumes..."):
#             for file in uploaded_files:
#                 try:
#                     # Extract text
#                     text = extract_resume_text(file)
#                     # Filters bad files
#                     if is_valid_resume(text):
#                         # => list[dict]
#                         resumes.append({"filename": file.name,"text": text})

#                 except Exception as e:
#                     st.error(f"Failed to analyze {file.name}: {e}")
#         if not resumes:
#             st.warning("No valid resume text found.")
#             st.stop()
#         st.success(f"{len(resumes)} resumes processed.")
#         with st.spinner("Calculating scores..."):
#             start = time.time()# Start timer.

#             ######### MATHEMATICL FILTERING #########
#             # Converts JD into vector
#             # job_embedding = embedding_model.embed_query(job_description)
#             job_embedding = get_job_embedding(job_description) # => list[float]
#             st.write(
#                 f"Job embedding time: {time.time() - start:.2f} sec")

#             # Only first 3000 characters used.
#             # resume_texts = [resume["text"] for resume in resumes]

#             # start = time.time()
#             # creates vectors of all resumes
#             # chunks = split_resume(resume_texts)
#             # resume_embeddings = get_resume_embeddings(chunks)
#             # chunks_embeddings = embedding_model.embed_documents(chunks)
#             # st.write(f"Resume embedding time: {time.time() - start:.2f} sec")
#             results = []
#             # pair resumes and embeddings
#             for resume in resumes:
#                 # Each chunk becomes vector
#                 chunks = split_resume(resume["text"]) # => list[str]
#                 # chunk_embeddings = embedding_model.embed_documents(chunks)

#                 # tuple because cache_data requires hashable arguments and chunks is a list which is mutable.
#                 chunk_embeddings = get_resume_embeddings(tuple(chunks)) # list[list[float]]
#                 # computes similarity
#                 scores = [
#                     cosine_similarity(
#                         [job_embedding],
#                         [chunks_embedding]
#                     )[0][0]
#                     for chunks_embedding in chunk_embeddings]
#                 if not scores:
#                     final_score = 0
#                 else:
#                     # These are the 3 most relevant sections of the resume
#                     top_scores = sorted(scores, reverse=True)[:3]

#                     # ranking mechanism
#                     final_score = (
#                         # 60% weight -> candidates final score
#                         # How good is the candidate's strongest evidence?
#                         max(scores) * 0.6
#                         # 40% weight -> entire resume final score
#                         # Takes the average of the top three matching chunks and weights it at 40%
#                         + (sum(top_scores) / len(top_scores)) * 0.4)

#                 results.append({"filename": resume["filename"],"text": resume["text"],"score": final_score,})

#             st.write(
#                 f"Resume embedding time: {time.time() - start:.2f} sec")
#         # Highest score first
#         results.sort(key=get_score, reverse=True)

#         # Top 10
#         top_resumes = results[:10]
#         st.subheader("Top 10 Matching Resumes")

#         for index, resume in enumerate(top_resumes, start=1):
#             st.write(f"{index}. {resume['filename']} ",
#                 # f"({resume['score'] * 100:.2f}% Match)",
#                 )
#         st.subheader(" Llama 3 Deep Analysis")

#         for index, resume in enumerate(top_resumes[:10], start=1):
#             # st.write(f" {index}. {resume['filename']} (Score: {resume['score'] * 100:.2f}%)")
#             with st.spinner(f"Analyzing candidate {index}..."):
#                 try:
#                     start = time.time()
#                     analysis_result = generate_llama_analysis(
#                         resume,
#                         job_description
#                     )
#                     print(f"Llama time: {time.time()-start:.2f}")
#                     st.write(f"### {index}. {resume['filename']}")
#                     st.info(analysis_result)

#                 except Exception as e:
#                     st.error(
#                         f"Failed to analyze {resume['filename']}: {e}"
#                     )










# import os
# import time
# import ollama
# import logging
# import streamlit as st
# from docx import Document
# from pypdf import PdfReader
# from striprtf.striprtf import rtf_to_text
# from sklearn.metrics.pairwise import cosine_similarity
# from langchain_huggingface import HuggingFaceEmbeddings

# # Suppress transformer warning logs
# logging.getLogger("transformers").setLevel(logging.ERROR)

# # Initialize Streamlit Session States to prevent data loss on rerun
# if "evaluation_results" not in st.session_state:
#     st.session_state.evaluation_results = None
# if "processing_done" not in st.session_state:
#     st.session_state.processing_done = False

# # Load model once and reuse across sessions
# @st.cache_resource
# def load_embedding_model():
#     return HuggingFaceEmbeddings(model_name="./saved_embedding_model")

# embedding_model = load_embedding_model()

# st.set_page_config(page_title="Resume Matcher Assistant", layout="wide")
# st.title("📄 Resume Matcher Assistant")

# # Sidebar configurations
# with st.sidebar:
#     st.header("Configuration")
#     chunk_size = st.number_input("Chunk Size (Words)", min_value=100, max_value=1000, value=500, step=50)
#     top_k_chunks = st.slider("Top Chunks for Ranking", min_value=1, max_value=5, value=3)

# # UI Elements
# job_description = st.text_area("Enter Job Description", height=200)
# uploaded_files = st.file_uploader("Upload Resumes (Max 50)", accept_multiple_files=True, type=["pdf", "docx", "rtf", "txt"])

# def extract_resume_text(file):
#     ext = os.path.splitext(file.name)[1].lower()
#     text = ""
#     try:
#         if ext == ".pdf":
#             pdf = PdfReader(file)
#             text = "\n".join(page.extract_text() or "" for page in pdf.pages)
#         elif ext == ".docx":
#             doc = Document(file)
#             text = "\n".join(p.text for p in doc.paragraphs)
#         elif ext == ".rtf":
#             content = file.read().decode("utf-8", errors="ignore")
#             text = rtf_to_text(content)
#         elif ext == ".txt":
#             text = file.read().decode("utf-8", errors="ignore")
#     except Exception as e:
#         st.error(f"Error parsing {file.name}: {str(e)}")
#     return text.strip()

# def is_valid_resume(text):
#     return len(text.split()) >= 30

# def split_resume(text, chunk_size=500):
#     words = text.split()
#     return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]

# def generate_llama_analysis(resume, job_desc):
#     system_prompt = f"""
#     You are a Senior Technical Recruiter and Hiring Manager.
#     Evaluate the candidate ONLY against the provided Job Description.
    
#     JOB DESCRIPTION:
#     {job_desc}

#     IMPORTANT RULES:
#     1. Evaluate actual skills, experience, and achievements from the resume.
#     2. Do NOT assume skills not explicitly mentioned.
#     3. Penalize missing critical requirements.
#     4. Return EXACTLY in the requested format below.

#     SCORING GUIDE:
#     90-100 = Exceptional Match (Meets nearly all requirements)
#     75-89 = Strong Match (Meets most requirements)
#     60-74 = Moderate Match (Noticeable gaps)
#     0-59 = Weak/Poor Match (Significant missing requirements)

#     SHORTLIST RULE: Score >= 75 -> YES | Score < 75 -> NO

#     Return EXACTLY in this format:
#     Match Score: <0-100>
#     Shortlist: <YES/NO>
#     Strengths:
#     - Point 1
#     - Point 2
#     Gaps:
#     - Point 1
#     - Point 2
#     Final Assessment:
#     <2-3 sentence summary explaining the decision>
#     """
    
#     user_message = f"""
#     ATS Semantic Similarity Score: {resume['similarity_score'] * 100:.2f}
#     Candidate Filename: {resume['filename']}
#     Resume Content:
#     {resume['text']}
#     """
#     try:
#         response = ollama.chat(
#             model="llama3.2:3b",
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": user_message}
#             ]
#         )
#         return response["message"]["content"]
#     except Exception as e:
#         return f"LLM Analysis Failed: {str(e)}"

# # Triggers when matching is requested
# if uploaded_files and st.button("Match Resumes", type="primary"):
#     if not job_description.strip():
#         st.error("Please enter a job description.")
#         st.stop()
        
#     if len(uploaded_files) > 50:
#         st.error("Maximum 50 resumes allowed.")
#         st.stop()

#     resumes = []
#     progress_bar = st.progress(0)
#     status_text = st.empty()
    
#     status_text.text("Extracting text from uploaded documents...")
#     for idx, file in enumerate(uploaded_files):
#         text = extract_resume_text(file)
#         if is_valid_resume(text):
#             resumes.append({"filename": file.name, "text": text})
#         progress_bar.progress((idx + 1) / len(uploaded_files))

#     if not resumes:
#         st.warning("No valid resumes containing text were found.")
#         st.stop()

#     status_text.text("Calculating semantic vector embeddings...")
#     # Calculate single vector representation for the Job Description
#     job_embedding = embedding_model.embed_query(job_description)
    
#     results = []
#     for resume in resumes:
#         chunks = split_resume(resume["text"], chunk_size)
#         if not chunks:
#             continue
            
#         chunk_embeddings = embedding_model.embed_documents(chunks)
        
#         # Calculate Cosine Similarities
#         scores = [cosine_similarity([job_embedding], [c_emb])[0][0] for c_emb in chunk_embeddings]
        
#         # Fixed Weighted Ranking Logic (60% weight on top chunk, 40% on average of next best)
#         if scores:
#             top_scores = sorted(scores, reverse=True)[:top_k_chunks]
#             if len(top_scores) == 1:
#                 final_score = top_scores[0]
#             else:
#                 final_score = (top_scores[0] * 0.6) + (sum(top_scores[1:]) / len(top_scores[1:]) * 0.4)
#         else:
#             final_score = 0.0

#         results.append({
#             "filename": resume["filename"],
#             "text": resume["text"],
#             "similarity_score": float(final_score)
#         })

#     # Sort candidates by calculated Vector Similarity score
#     results = sorted(results, key=lambda x: x["similarity_score"], reverse=True)
    
#     # Save parameters directly to Session State
#     st.session_state.evaluation_results = results
#     st.session_state.processing_done = True
#     status_text.empty()
#     progress_bar.empty()

# # Persistent Render Block (Keeps information visible during downstream interactions)
# if st.session_state.processing_done and st.session_state.evaluation_results:
#     st.success(f"Successfully evaluated {len(st.session_state.evaluation_results)} resumes!")
    
#     for idx, candidate in enumerate(st.session_state.evaluation_results):
#         # Create clear metric anchors for scannability 
#         label = f"📋 {candidate['filename']} (Semantic Score: {candidate['similarity_score']*100:.1f}%)"
        
#         with st.expander(label):
#             col1, col2 = st.columns([1, 2])
            
#             with col1:
#                 st.metric(label="ATS Similarity", value=f"{candidate['similarity_score']*100:.1f}%")
#                 # Lazy loading analysis execution inside the expansion widget
#                 if st.button("Generate AI Executive Assessment", key=f"btn_{idx}"):
#                     with st.spinner("Llama 3.2 is analyzing candidate details..."):
#                         llm_report = generate_llama_analysis(candidate, job_description)
#                         st.session_state[f"report_{idx}"] = llm_report
                
#             with col2:
#                 if f"report_{idx}" in st.session_state:
#                     st.markdown("### Deep AI Analysis")
#                     st.text(st.session_state[f"report_{idx}"])
#                 else:
#                     st.info("Click the button on the left to trigger the Local Llama 3.2 Recruiter evaluation report.")
















import os
import time
import ollama
import logging
import streamlit as st
from docx import Document
from pypdf import PdfReader
from striprtf.striprtf import rtf_to_text
from sklearn.metrics.pairwise import cosine_similarity
from langchain_huggingface import HuggingFaceEmbeddings

logging.getLogger("transformers").setLevel(logging.ERROR)

# Load once and reuse
@st.cache_resource
def load_embedding_model():
    return HuggingFaceEmbeddings(model_name="./saved_embedding_model")

# It stores the results of the embedding calculations
# cache_data reuires hashable arguments
@st.cache_data # => input: tuple[str] | output : list[str]
def get_resume_embeddings(chunks):
    return embedding_model.embed_documents(list(chunks))

@st.cache_data
def get_job_embedding(job_description):
    return embedding_model.embed_query(job_description)

# Calls function and stores model object
embedding_model = load_embedding_model()

st.title("Resume Matcher Assistant")

# Create large textbox
job_description = st.text_area("Enter Job Description", height=200)
# Create upload files => list
uploaded_files = st.file_uploader("Upload Resumes (Max 50)",accept_multiple_files=True,)

# Text extraction function => str
def extract_resume_text(file):
    ext = os.path.splitext(file.name)[1].lower() # Get extension
    print(f"EXTENSION OF FILE : {ext}")
    text = ""
    if ext == ".pdf":
        pdf = PdfReader(file)
        # page.extract_text() -> belongs to pypdf library
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    elif ext == ".docx":
        doc = Document(file)
        text = "\n".join(p.text for p in doc.paragraphs)

    elif ext == ".rtf":
        content = file.read().decode("utf-8", errors="ignore")
        text = rtf_to_text(content)

    elif ext == ".txt":
        text = file.read().decode("utf-8", errors="ignore")
    return text.strip()

def is_valid_resume(text):
    words = text.split()
    if len(words) < 30: # Reject tiny documents
        return False
    return True

def get_score(item):
    return item["score"]

def split_resume(text, chunk_size=500): # input=> str | output => list[str]
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):    # 0, 500, 1000, 1500...
        # Creates chunk.
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks



# def text_chunking(text):
#     if text.strip():
#         chunks = text_splitter.split_text(text)

#         for chunk in chunks:
#             doc = Document(
#                 page_content=chunk,
#                 metadata={"source": uploaded_file.name}
#             )
#             all_chunks.append(doc_obj)

#     else:
#         st.error(f"Error processing text")

######### VALIDATION AND EXTRACTION #########
if uploaded_files:
    if len(uploaded_files) > 50:
        st.error("Maximum 50 resumes allowed.")
    # Runs matching only when button clicked.
    elif st.button("Match Resumes"):
        # if checkbox empty
        if not job_description.strip():
            st.error("Please enter a job description.")
            # stops execution
            st.stop()
        resumes = [] # valid resumes
        with st.spinner("Reading resumes..."):
            for file in uploaded_files:
                try:
                    # Extract text
                    text = extract_resume_text(file)
                    # Filters bad files
                    if is_valid_resume(text):
                        # => list[dict]
                        resumes.append({"filename": file.name,"text": text})

                except Exception as e:
                    st.error(f"Failed to analyze {file.name}: {e}")
        if not resumes:
            st.warning("No valid resume text found.")
            st.stop()
        st.success(f"{len(resumes)} resumes processed.")
        with st.spinner("Calculating scores..."):
            start = time.time()# Start timer.

            ######### MATHEMATICL FILTERING #########
            # Converts JD into vector
            # job_embedding = embedding_model.embed_query(job_description)
            job_embedding = get_job_embedding(job_description) # => list[float]
            st.write(
                f"Job embedding time: {time.time() - start:.2f} sec")

            # Only first 3000 characters used.
            # resume_texts = [resume["text"] for resume in resumes]

            # start = time.time()
            # creates vectors of all resumes
            # chunks = split_resume(resume_texts)
            # resume_embeddings = get_resume_embeddings(chunks)
            # chunks_embeddings = embedding_model.embed_documents(chunks)
            # st.write(f"Resume embedding time: {time.time() - start:.2f} sec")
            results = []
            # pair resumes and embeddings
            for resume in resumes:
                # Each chunk becomes vector
                chunks = split_resume(resume["text"]) # => list[str]
                # chunk_embeddings = embedding_model.embed_documents(chunks)

                # tuple because cache_data requires hashable arguments and chunks is a list which is mutable.
                chunk_embeddings = get_resume_embeddings(tuple(chunks)) # list[list[float]]
                # computes similarity
                scores = [
                    cosine_similarity(
                        [job_embedding],
                        [chunks_embedding]
                    )[0][0]
                    for chunks_embedding in chunk_embeddings]
                if not scores:
                    final_score = 0
                else:
                    # These are the 3 most relevant sections of the resume
                    top_scores = sorted(scores, reverse=True)[:3]

                    # ranking mechanism
                    final_score = (
                        # 60% weight -> candidates final score
                        # How good is the candidate's strongest evidence?
                        max(scores) * 0.6 # chunk weightage
                        # 40% weight -> entire resume final score
                        # Takes the average of the top three matching chunks and weights it at 40%
                        + (sum(top_scores) / len(top_scores)) * 0.4)

                results.append({"filename": resume["filename"],"text": resume["text"],"score": final_score,})

            st.write(f"Resume embedding time: {time.time() - start:.2f} sec")
        # Highest score first
        results.sort(key=get_score, reverse=True)

        # Top 10
        top_resumes = results[:10]
        st.subheader("Top 10 Matching Resumes")

        for index, resume in enumerate(top_resumes, start=1):
            st.write(f"{index}. {resume['filename']} ",
                f"({resume['score'] * 100:.2f}% Match)",
                )
        st.subheader(" Llama 3 Deep Analysis")

        for index, resume in enumerate(top_resumes[:10], start=1):
            # st.write(f" {index}. {resume['filename']} (Score: {resume['score'] * 100:.2f}%)")
            with st.spinner(f"Analyzing candidate {index}..."):
                try:
                    start = time.time()
                    analysis_result = generate_llama_analysis(resume,job_description)
                    print(f"Llama time: {time.time()-start:.2f}")
                    st.write(f"### {index}. {resume['filename']}")
                    st.info(analysis_result)

                except Exception as e:
                    st.error(
                        f"Failed to analyze {resume['filename']}: {e}")