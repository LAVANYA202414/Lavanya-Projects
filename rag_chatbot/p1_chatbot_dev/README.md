# Rag Chatbot — Setup Guide

A step-by-step guide to clone the project, set up the environment, install dependencies, and run the application.

---

## Step 1 — Clone the Repository

Open your terminal and run:

```bash
git clone <your-repository-url>
```

Once cloned, navigate into the project folder:

```bash
cd your-repo-name
```

## Step 2 — Create a Virtual Environment

A virtual environment keeps your project's dependencies isolated from other Python projects on your machine.

```bash
python -m venv chatbot_env
```

This creates a folder called `chatbot_env/` inside your project directory.

---

## Step 3 — Activate the Virtual Environment

You must activate the environment before installing packages or running the app.

**macOS / Linux:**

```bash
source chatbot_env/bin/activate
```

**Windows (Command Prompt):**

```bash
chatbot_env\Scripts\activate
```

---

## Step 4 — Install Dependencies

With the virtual environment active, install all required packages from `requirements.txt`:

```bash
pip install -r requirements.txt
```

This installs everything the project needs — FastAPI, LangChain, ChromaDB, OpenAI, Streamlit, and more.

---

## Step 5 — Add Your API Credentials

Create a `credentials.yml` file in the root of the project folder:

```bash
# macOS / Linux
touch credentials.yml

# Windows (PowerShell)
New-Item credentials.yml
```

Open the file and add your OpenAI API key:

```yaml
openai: sk-your-openai-api-key-here
```

> ⚠️ **Never share or commit `credentials.yml` to Git.** It is listed in `.gitignore` to protect your key.

---

## Step 6 — Run the Application

Start the FastAPI server using Uvicorn:

```bash
uvicorn rag_chatbot:app --reload
```

**Expected output:**

```
INFO:     Will watch for changes in these directories: ['/your/project/path']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345]
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

The API is now live at: **http://127.0.0.1:8000**

---

## Step 7 — Test the API

Open your browser and go to the interactive API docs:

```
http://127.0.0.1:8000/docs
```

This opens the Swagger UI where you can test the `/chat` endpoint directly in the browser.

---

## Stopping the Server

Press `CTRL + C` in the terminal to stop the server.

To deactivate the virtual environment:

```bash
deactivate
```

---

## Quick Reference — All Commands in Order

```bash
# 1. Clone the repo
git clone <your-repository-url>
cd your-repo-name

# 2. Create virtual environment
python -m venv chatbot_env

# 3. Activate it (macOS/Linux)
source chatbot_env/bin/activate

# 4. Install packages
pip install -r requirements.txt

# 5. Add credentials
# Edit credentials.yml and add your OpenAI key
```
# Migration commands:
- alembic init migrations
    -> (after running this you'll see a file named "alembic.ini" . update sqlalchemy.url = mysql+pymysql://user:password@localhost/chatbot_db)
    -> (Update p1_chatbot_dev/alembic/env.py target_metadata = None --> declarative class meta deta like :target_metadata = Base.metadata)
- alembic revision --autogenerate -m "Add new table" # For Migration of the Tables
- alembic upgrade head # Migrate the migrations into the DB

# In database.py
    Create the Database class and configure the database connection by setting the DATABASE_URL and SQLAlchemy engine. This file is responsible for establishing and managing the connection between the FastAPI application and the database.
    like :     DATABASE_URL = "mysql+pymysql://user:password@localhost/chatbot_db"


# 6. Run the app
uvicorn rag_chatbot:app --reload

---

## Troubleshooting

**`ModuleNotFoundError`**
The virtual environment may not be activated. Run `source chatbot_env/bin/activate` (macOS/Linux) or `chatbot_env\Scripts\activate` (Windows) first.

**`ERROR: Could not find a version that satisfies the requirement ...`**
Your Python version may be too old. Make sure you have Python 3.9 or higher: `python --version`.

**`credentials.yml not found` or `KeyError: openai`**
Make sure `credentials.yml` exists in the project root and contains `openai: sk-...`.

**`uvicorn: command not found`**
Uvicorn wasn't installed. Run `pip install uvicorn` and try again.









API Endpoints
POST /start-session
Creates a new conversation session.
Response:
json{
  "success": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}

POST /chat
Sends a message and receives an AI response. If the session has expired or is invalid, a new session is created automatically.
Request Body:
json{
  "input": "What are the specs for the mountain bike?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
Response (success):
json{
  "success": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    { "sender": "human", "text": "What are the specs for the mountain bike?" },
    { "sender": "ai", "text": "The mountain bike features a lightweight carbon frame, 21-speed Shimano gears, and hydraulic disc brakes." }
  ]
}
Response (expired/missing session):
json{
  "message": "Session had been deleted. Started a new Session",
  "success": true,
  "session_id": "new-uuid-here"
}

GET /chat-history/{session_id}
Returns the full conversation history for a session. Tries Redis first; falls back to the database.
Response:
json{
  "success": true,
  "messages": [
    { "sender": "human", "text": "Tell me about the road bike." },
    { "sender": "ai", "text": "The road bike has a carbon fork and weighs 7.8 kg." }
  ]
}

GET /disable-session/{session_id}
Marks a session as inactive, effectively ending the conversation.
Response:
json"Done"








** Changes Made & Why:
1. Replaced Streamlit with FastAPI
What changed: Removed all Streamlit UI components (st.chat_input, st.chat_message, st.spinner) and replaced them with FastAPI route handlers using app.add_api_route().
Why: Streamlit is designed for single-user browser prototypes. FastAPI is built for scalable backend APIs that serve multiple users simultaneously and integrate with any frontend (React, mobile apps, external services).

2. Converted to API-Based Architecture
What changed: All business logic now lives behind REST endpoints that accept JSON and return JSON.
Why: Separating the backend from any specific frontend makes the system flexible, testable, and ready for production. Any frontend — React, Angular, mobile — can consume this API without changes to the backend.

3. Replaced StreamlitChatMessageHistory with Custom Two-Tier Memory
What changed: Replaced StreamlitChatMessageHistory with Redis (L1 cache, last 15 messages) backed by PostgreSQL/SQLite (full persistent history).
Why: Streamlit memory only exists within a single browser session for a single user. This new system supports multiple concurrent users, survives server restarts, and is fast (Redis for active sessions, SQL for historical lookups).

4. Implemented Multi-User Session Management
What changed: Added UUID-based session IDs, a Conversation model, and get_or_create_session() logic.
Why: The original code used a hardcoded session ID ("any"), meaning every user shared the same conversation history. Session isolation is fundamental for any real-world deployment.

5. Added 24-Hour Session Auto-Expiry
What changed: Sessions older than 24 hours are treated as expired. Redis keys are also set to expire after 86400 seconds (session_ttl).
Why: Prevents unbounded memory and storage growth, keeps data fresh, and avoids serving stale context to returning users.

6. Integrated Redis for Fast History Lookups
What changed: Added save_message_to_redis() and load_recent_history_from_redis(). The last 15 messages per session are stored in Redis and served before touching the database.
Why: Reduces database load for active conversations. Redis is orders of magnitude faster for recent-message lookups. The 15-message window covers the vast majority of real conversations while keeping memory usage bounded.

7. Added SQLAlchemy ORM + Alembic Migrations
What changed: Introduced Conversation and Messages SQLAlchemy models and Alembic for schema version control.
Why: A proper ORM layer makes database operations safer and more maintainable. Alembic enables schema changes to be tracked, reviewed, and rolled back — essential for any project that will evolve over time.

8. Added Pydantic Request Validation
What changed: Introduced class ChatRequest(BaseModel) with typed fields including Optional[EmailStr] and Optional[str].
Why: Pydantic validates all incoming data before it reaches business logic, preventing malformed requests from causing unexpected errors deeper in the stack.

9. Added Structured Error Handling
What changed: Wrapped all endpoint logic in try/except blocks that raise HTTPException with line numbers included in the error detail.
Why: Prevents the server from crashing on unexpected errors and returns clear, structured error responses that make debugging in production much easier.

10. Configured CORS Middleware
What changed: Added CORSMiddleware with a list of allowed origins covering common local development ports.
Why: Without CORS headers, browsers block requests from frontends on different ports or domains. This configuration is essential for any separate frontend to communicate with the API.

11. Improved RAG Prompt Structure
What changed: The system prompt, {context}, MessagesPlaceholder("chat_history"), and {input} are now injected as separate, clearly-labelled message blocks in the prompt template.
Why: Clean separation of context, history, and current input gives the model a clearer structure to reason over, improving retrieval quality and the accuracy of follow-up question handling.

12. Encapsulated RAG Logic in create_rag_chain()
What changed: All vector store, retriever, and chain setup is wrapped inside a single create_rag_chain() function that is called once at startup.
Why: Improves readability, makes the initialization logic reusable and testable, and keeps the global scope clean.

13. Preserved Core LangChain RAG Components
What was kept: Chroma, OpenAIEmbeddings, create_history_aware_retriever, create_retrieval_chain, RunnableWithMessageHistory.
Why: These components already implement a well-structured conversational RAG pipeline. The goal was to adapt and extend the architecture for production use, not rebuild working logic from scratch.
