import os
import time
import ollama
import logging
import streamlit as st
from docx import Document
from pypdf import PdfReader
from striprtf.striprtf import rtf_to_text
from sentence_transformers import CrossEncoder
from sklearn.metrics.pairwise import cosine_similarity
from langchain_huggingface import HuggingFaceEmbeddings

logging.getLogger("transformers").setLevel(logging.ERROR)
cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

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

def get_score(resume):
    return resume["score"]

def get_embedding_score(resume):
    return resume["score"]

def split_resume(text, chunk_size=500): # input=> str | output => list[str]
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):    # 0, 500, 1000, 1500...
        # Creates chunk.
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

def get_cross_score(resume):
    return resume["cross_score"]


def generate_llama_analysis(resume, user_query):
    system_prompt = f"""
    You are a Senior Technical Recruiter.

    JOB DESCRIPTION:
    {job_description}

    YOUR TASK:
    Evaluate the candidate ONLY against the Job Description.

    CRITICAL RULES:
    1. Use ONLY information explicitly present in the resume.
    2. Evaluate ONLY against requirements found in the Job Description.
    3. Do NOT assume skills, experience, technologies, or responsibilities that are not mentioned.
    4. Penalize candidates only for missing requirements that are directly required by the Job Description.
    5. Ignore unrelated skills that are not important for this role.
    6. The embedding similarity score is NOT the hiring score.
    It is only a weak relevance signal.
    7. If the candidate strongly matches the core requirements,
    reward accordingly.
    8. If the candidate lacks most core requirements,
    assign a low score.

    INTERNAL REASONING (DO NOT OUTPUT):
    * Extract the important requirements from the Job Description.
    * Compare the resume against those requirements.
    * Determine the final score.
    * Never show this reasoning.

    SCORING GUIDE:
    90-100 = Exceptional Match
    * Meets nearly all requirements
    * Strong relevant experience
    * Immediate shortlist

    75-89 = Strong Match
    * Meets most requirements
    * Minor gaps only
    * Should be shortlisted

    60-74 = Moderate Match
    * Meets some requirements
    * Noticeable gaps
    * Shortlist only if applicant pool is small

    40-59 = Weak Match
    * Significant missing requirements
    * Normally not shortlisted

    0-39 = Poor Match
    * Major mismatch
    * Reject

    SHORTLIST RULE:
    Score >= 75 → YES
    Score < 75 → NO

    IMPORTANT:
    DO NOT OUTPUT:
    * Step 1
    * Step 2
    * Step 3
    * Requirement extraction
    * Reasoning process
    * Analysis process
    * Thought process

    OUTPUT ONLY THE FORMAT BELOW:
    Match Score: <0-100>

    Shortlist: <YES/NO>

    Strengths:
    * Point 1
    * Point 2
    Final Assessment:
    <2-3 sentence summary>
    The shortlist decision MUST match the score.
    The response MUST contain ONLY these sections.
    """

    user_message = f"""
    Candidate: {resume['filename']}
    Resume:
    {resume['text']}

    Embedding Similarity Score:
    {resume['score'] * 100:.2f}%

    IMPORTANT:
    The embedding score is NOT the final hiring score.
    Use it only as a weak relevance signal.
    Evaluate the candidate primarily using:

    * skills
    * experience
    * technologies
    * responsibilities
    * achievements

    found in the resume compared to the Job Description.
    """
    response = ollama.chat(
        model="llama3.1:8b",
        options={"temperature": 0.1},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ])
    return response["message"]["content"]


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
            st.write(f"Job embedding time: {time.time() - start:.2f} sec")

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
                # Bi - Encoder:
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
        results.sort(key=get_embedding_score,reverse=True)

        # recall@k
        top_resumes = results[:20]

        for resume in top_resumes:
            chunks = split_resume(
                resume["text"],
                chunk_size=200)
            pairs = [[job_description, chunk]for chunk in chunks]
            chunk_scores = cross_encoder.predict(pairs)
            resume["cross_score"] = float(max(chunk_scores))

        # MRR (Mean Reciprocal Rank)
        top_resumes.sort(
            key=get_cross_score,
            reverse=True)

        # precision@k
        top_resumes = top_resumes[:10]
        st.write(
            f"Embedding={resume['score']:.4f}",
            f"Cross={resume['cross_score']:.4f}")

        # final_resumes = []
        # for i in range(10):
        #     if i < len(top_resumes[i]):
        #         final_resumes.append(top_resumes[i])
        # top_resumes = final_resumes

        for index, resume in enumerate(top_resumes, start=1):
            st.write(f"{index}. {resume['filename']} ",
                f"({resume['score'] * 100:.2f}% Match)",)
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