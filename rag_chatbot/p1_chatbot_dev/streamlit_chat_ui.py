import uuid
import streamlit as st
import requests

# The FastAPI backend URL we'll send questions to
API_URL = "http://127.0.0.1:8000"

#  PAGE SETUP 
st.set_page_config(page_title="Product Expert Chatbot", page_icon="🤖")
st.title("🤖 Product Expert Chatbot")
st.caption("Ask me anything about our products!")

#  MEMORY (saved while the app is open) 
# messages: stores the full chat history to display on screen
if "messages" not in st.session_state:
    st.session_state.messages = []

# session_id: a unique ID so the backend remembers THIS user's conversation
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

#  SHOW PAST MESSAGES 
# Every time the page refreshes, redraw all previous messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):       # "user" or "assistant"
        st.markdown(msg["content"])

#  HANDLE NEW USER INPUT 
if prompt := st.chat_input("Ask about a product..."):

    # 1. Save and show the user's message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Send the question to FastAPI and get the answer
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    API_URL,
                    json={
                        "input": prompt,
                        "session_id": st.session_state.session_id  # links to backend memory
                    },
                    timeout=30
                )
                if response.status_code == 200:
                    answer = response.json()["answer"]  # success
                else:
                    answer = f"⚠️ Error {response.status_code}: {response.text}"

            except requests.exceptions.ConnectionError:
                # FastAPI server is not running
                answer = "❌ Cannot connect to the backend. Make sure FastAPI is running on port 8000."
            except Exception as e:
                answer = f"❌ Unexpected error: {str(e)}"

    # 3. Show and save the assistant's answer
        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})

# #  SIDEBAR 
# with st.sidebar:
#     st.header("Session Info")
#     st.caption(f"Session ID: `{st.session_state.session_id}`")

#     # Clear chat: wipe messages and generate a fresh session ID
#     if st.button("🗑️ Clear Chat"):
#         st.session_state.messages = []
#         st.session_state.session_id = str(uuid.uuid4())
#         st.rerun()