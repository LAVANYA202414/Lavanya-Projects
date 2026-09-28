@st.cache_resource: 
    Tells Streamlit to load this model only once into memory when the server starts. This prevents your app from lagging every time a button is clicked.


In Streamlit, @st.cache_resource is a built-in decorator used to cache expensive, long-lived resources so they only load once.


./saved_embedding_model: 
    Instead of pulling from the internet, it loads the embedding model locally from the folder you created using your save.py script.


Chunking: 
    AI systems struggle to read entire documents at once. This tool splits each resume into overlapping segments of roughly 1000 characters. The 200 character overlap ensures no context is split awkwardly in half between chunks.


Database Reset: 
    Before saving new data, the script attempts to call db.delete_collection() to wipe out old data in ./chroma_db. This keeps your search fresh for only the currently uploaded resumes.


Ingestion: 
    Chroma.from_documents processes all text blocks into mathematical points and commits them to disk.


Semantic Search: 
    vector_db.similarity_search instantly pulls the top 100 closest matching text chunks based on the overall meaning of your job description.


What is :.2f?
    f → floating point number
    .2 → show 2 digits after the decimal point



CROSS - ENCODER:
        -> EMBEDDING MODEL:
                takes rawt text. converts job description and resumes into embeddings.

        -> THE CROSS ENCODER:
                It completely throws away the mathematical embeddings calculated in Step 1.
                It looks directly at your code line:
                cross_encoder.predict([[job_description, resume["text"]]])









## Phase 1: Initialization & Setup

Loads Required Libraries:
The application imports libraries for file processing, resume parsing, embedding generation, similarity scoring, AI analysis, and Streamlit UI rendering.

Loads Embedding Model:
The app loads a locally saved Hugging Face embedding model from ./saved_embedding_model. It uses @st.cache_resource so the model is loaded only once and reused across all user interactions, significantly improving performance.

Configures Logging:
Transformer-related warnings are suppressed to keep the application output clean and readable.

Builds User Interface:
Streamlit renders:

A large text area for entering the Job Description (JD).
A multi-file uploader that accepts up to 50 resumes.
Supported file formats: PDF, DOCX, RTF, and TXT.

## Phase 2: Resume Upload & Validation

Upload Processing:
When resumes are uploaded, the application first checks whether the number of uploaded files exceeds the maximum limit of 50.

Job Description Validation:
Before matching begins, the application verifies that a Job Description has been provided. If the JD is empty, processing stops and an error message is displayed.

Resume Validation:
After text extraction, each resume is validated using the is_valid_resume() function.

Minimum Content Requirement:
Resumes containing fewer than 30 words are considered invalid and are automatically skipped. This prevents empty, corrupted, or non-resume files from affecting the matching process.

## Phase 3: Resume Text Extraction

Automatic File Type Detection:
The application determines the resume format using the file extension and applies the appropriate extraction method.

PDF Processing:
Each page is read using PdfReader, and all extracted text is combined into a single document.

DOCX Processing:
All paragraphs are extracted from the Word document and merged into one text string.

RTF Processing:
RTF formatting tags are removed using rtf_to_text(), leaving only plain text.

TXT Processing:
The file content is directly decoded and stored as plain text.

Resume Storage:
Each valid resume is stored with:

Filename
Extracted text content

These resumes are collected into a list for further processing.

## Phase 4: Job Description Embedding Generation

Converts JD into Numerical Representation:
The Job Description is transformed into a semantic embedding vector using the Hugging Face embedding model.

Purpose:
The embedding captures the meaning and context of the job requirements rather than relying solely on keyword matching.

Performance Monitoring:
The application records and displays the time required to generate the Job Description embedding.

## Phase 5: Resume Chunking

Splits Large Resumes into Sections:
Instead of embedding an entire resume as one large document, the resume is divided into chunks of 500 words.

Why Chunking Is Used:
Different sections of a resume may contain different skills and experiences. Chunking helps identify the most relevant parts of a resume and improves matching accuracy.

Example:
A 1,500-word resume would be split into:

Chunk 1: Words 1–500
Chunk 2: Words 501–1000
Chunk 3: Words 1001–1500

## Phase 6: Resume Embedding Generation

Creates Embeddings for Each Chunk:
Every resume chunk is converted into an embedding vector using the same embedding model used for the Job Description.

Semantic Representation:
These vectors capture the meaning of each section of the resume, enabling semantic similarity comparison instead of simple keyword matching.

## Phase 7: ATS Similarity Scoring

Calculates Similarity Scores:
Each resume chunk is compared against the Job Description embedding using cosine similarity.

Cosine Similarity:
This measures how closely the semantic meaning of the resume aligns with the job requirements.

Chunk-Level Evaluation:
Every chunk receives an individual similarity score.

Example:

Chunk 1 → 0.91
Chunk 2 → 0.84
Chunk 3 → 0.72

## Phase 8: Final Resume Score Calculation

Identifies Strongest Resume Sections:
The application selects the top three highest-scoring chunks from each resume.

Weighted Scoring Formula:
The final ATS score is calculated using:

60% weight from the best-performing chunk.
40% weight from the average of the top three chunks.

Purpose:
This approach rewards:

Strong evidence of relevant experience.
Consistent alignment throughout the resume.

Result:
A single final similarity score is generated for each candidate.

## Phase 9: Resume Ranking

Sorts Candidates by Match Score:
All resumes are sorted in descending order based on their final ATS score.

Highest Match First:
Candidates with the strongest alignment to the Job Description appear at the top of the ranking list.

Top Candidate Selection:
Only the top 10 highest-scoring resumes proceed to AI-based recruiter analysis.

## Phase 10: AI Recruiter Analysis Using Llama 3

Generates Human-Like Evaluation:
For each of the top 10 resumes, the application sends the following information to the Llama 3 model:

Job Description
ATS Similarity Score
Candidate Resume Content
Candidate Filename

Recruiter Role Prompting:
The model is instructed to act as a senior recruiter and evaluate candidates strictly against the provided Job Description.

Scoring Guidelines:

90–100 → Exceptional Match
75–89 → Strong Match
60–74 → Moderate Match
40–59 → Weak Match
0–39 → Poor Match

Shortlisting Decision:
The AI determines whether the candidate should be shortlisted and ensures the decision is consistent with the assigned score.

## Phase 11: Recruiter Insights Generation

Produces Structured Feedback:
For every candidate, Llama generates:

Match Score
Shortlist Decision (YES/NO)
Key Hiring Reasons

Example Output:

Strong Python and Django experience
Relevant backend development projects
Experience working with cloud platforms

This provides recruiters with qualitative insights beyond the ATS similarity score.

## Phase 12: Results Presentation

Displays Top Matching Candidates:
The application shows the filenames of the top 10 resumes ranked by ATS score.

Displays AI Analysis:
Each candidate's recruiter-style evaluation is displayed below the ranking list.

Final Outcome:
Recruiters receive:

Semantic ATS matching scores.
Ranked candidate list.
AI-generated hiring recommendations.
Shortlisting decisions with reasoning.


End-to-End Workflow:

        [ Job Description Input ]
                        │
                        ▼
        [ Generate JD Embedding ]
                        │
                        ▼
        [ Upload Resumes (Max 50 Files) ]
                        │
                        ▼
        [ Extract Raw Resume Text ]
        (.pdf, .docx, .rtf, .txt)
                        │
                        ▼
        [ Validate Resumes ]
        (Filter out files < 30 words)
                        │
                        ▼
        [ Split Resumes into Chunks ]
                (500-word blocks)
                        │
                        ▼
        [ Generate Chunk Embeddings ]
        (Cached HuggingFace vectors)
                        │
                        ▼
        [ Calculate Cosine Similarity ]
        (Compare JD vector vs Chunks)
                        │
                        ▼
        [ Compute Weighted ATS Scores ]
        (60% Best Chunk + 40% Top 3 Average)
                        │
                        ▼
        [ Stage 1 Ranking: Select Top 20 ]
                        │
                        ▼
⭐ [ CROSS-ENCODER RE-RANKING PASS ] ⭐
(Reads raw text of Top 20 simultaneously)
                        │
                        ▼
        [ Stage 2 Ranking: Select Top 10 ]
        (Based on Cross-Encoder score)
                        │
                        ▼
        [ Llama 3 Recruiter Analysis ]
        (Checks context & extracts strengths)
                        │
                        ▼
        [ Generate Shortlist Decisions ]
        (Strict Score >= 75 Rule)
                        │
                        ▼
        [ Display Final Results ]
        (Streamlit UI Components)
