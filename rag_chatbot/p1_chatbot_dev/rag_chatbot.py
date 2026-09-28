from packages import *
from product_expert_streamlit import create_rag_agent

# FASTAPI SETUP
app = FastAPI(title="Product Assistant API")

# Base.metadata.create_all(bind=engine)
warnings.filterwarnings("ignore", category=DeprecationWarning)
# r = redis.Redis(host="localhost", port=6379, decode_responses=True)
session_ttl = 86400 # 24 hours

# REDIS CHAT LIMIT
# REDIS_CHAT_LIMIT = 15

# CORSS ORIGINS
origins = [
    "http://127.0.0.1",
    "http://32.197.47.86",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5500",
    "http://32.197.47.86:8000",
    "http://l01vkmb2-5173.inc1.devtunnels.ms",
    "https://l01vkmb2-5173.inc1.devtunnels.ms",]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"])


# Load API Key from your credentials file
with open('credentials.yml') as f:
    os.environ["OPENAI_API_KEY"] = yaml.safe_load(f)['openai']

# creating database sessions
# def get_db():
#     db=SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# Initialize the base logic
# connects your chroma database and Openai
base_rag_chain = create_rag_agent()


# def load_recent_history_from_redis(session_id: str):

    # # redis_key = f"chat_history:{session_id}"

    # # messages = r.lrange(redis_key, 0, -1)
    # # history = ChatMessageHistory()

    # # for msg in messages:

        # # parsed = json.loads(msg)

        # # if parsed["role"] == "human":
        #     # history.add_user_message(parsed["content"])

        # # elif parsed["role"] == "ai":
        #     # history.add_ai_message(parsed["content"])

    # return history


# def get_session_history(session_id: str,db=None):
    # def get_session_history(session_id: str,db: Session):

    # now = datetime.now()

    # Get session
    # existing_session = (db.query(Conversation).filter(Conversation.session_id == session_id).first())

    # # No session
    # if not existing_session or not existing_session.active:
    #     return ChatMessageHistory()#--->return None for no history

    # session_age = (now - existing_session.created_at)

    # # Older than 24 hrs
    # if session_age > timedelta(days=1):
    #     # db.query(Messages).filter(Messages.conversation_id== session_id).delete()
    #     # db.query(Conversation).filter(Conversation.session_id == session_id).delete()
    #     # db.commit()
    #     existing_session.active = False
    #     # db.commit()
    #     return ChatMessageHistory()  #--->because no need to show previous chats if exists ,delete and provide new session 


    # FIRST TRY REDIS
    # redis_history = load_recent_history_from_redis(session_id)
    # If redis has messages, use them
    # if len(redis_history.messages) > 0:
    #     return redis_history
    
    # Build history
    # history = ChatMessageHistory()
    # all_messages = (db.query(Messages).filter(Messages.conversation_id == session_id).order_by(Messages.created_at.asc()).all())

    # for msg in all_messages:
    #     if msg.role == "human":
    #         history.add_user_message(msg.content)

    #     elif msg.role == "ai":
    #         history.add_ai_message(msg.content)

    # return history
    # return redis_history
    # return load_recent_history_from_redis(session_id)


# def history_wrapper(session_id: str):
#     # db = SessionLocal()

#     try:
#         return get_session_history(session_id,db)

#     finally:
#         db.close()


# def history_wrapper(session_id: str):
    # print("hello")
    # db = SessionLocal()

    # try:
    #     return get_session_history(session_id,db=None)

    # finally:
    #     # db.close()
    #     pass
    # print(get_session_history(session_id))
    # return get_session_history(session_id)


# api_chain = RunnableWithMessageHistory(
#     base_rag_chain,
#     history_wrapper,
#     input_messages_key="input",
#     history_messages_key="chat_history",
#     output_messages_key="answer")

# API ENDPOINTS
# basemodel check if data sent is correct.
class ChatRequest(BaseModel):
    input: str
    # session_id: str
    email: Optional[EmailStr] = None
    session_id: Optional[str] = None


# def disable_active_sessions(session_id: str, db: Session = Depends(get_db)):
def disable_active_sessions(session_id: str, db=None):
    # conversations = (
    #     db.query(Conversation)
    #     .filter(Conversation.session_id == session_id)
    #     .all()
    # )

    # for conversation in conversations:
    #     conversation.active = False

    # db.commit()
    # return {
    #     "success": True,
    #     "message": f"Successfully deactivated all sessions matching ID: {session_id}"
    # }
    # r.delete(f"session_active:{session_id}")
    # r.delete(f"chat_history:{session_id}")
    return {"success": True, "message": f"Successfully deactivated session matching ID: {session_id}"}


# def get_or_create_session(session_id: str, db: Session):
def get_or_create_session(session_id: str, db= None):

    # find session in database--->latest one because we only need to find session id if it exists return and check, otherwise generate
    # existing_session = (db.query(Conversation).filter(Conversation.session_id == session_id).first())
    
    # session does not exist
    # if not existing_session or not existing_session.active:
    #     return False
    # # # valid session
    # return existing_session.session_id
    session_meta_key = f"session_active:{session_id}"
    # if not r.exists(session_meta_key):
    #     return False
    return session_id


# def chat_endpoint(request: ChatRequest,db: Session = Depends(get_db)):
def chat_endpoint(request: ChatRequest,db=None):
    session = get_or_create_session(request.session_id,db=None)
    if not session:
        session_id =  create_session(db=None)
        return {
                "message": "Session had been deleted. Started a new Session",
                "success": True,
                "session_id": session_id
            }
    try:
        response = base_rag_chain.invoke(
            {"input": request.input},
            config={"configurable": {"session_id": session}},
        )

        ai_answer = response["answer"]
        # conversation = (
        #     db.query(Conversation)
        #     .filter(Conversation.session_id == session)
        #     .first()
        # )

        # HUMAN MESSAGE
        # human_message = Messages(
        #     conversation_id=conversation.id,
        #     role="human",
        #     content=request.input
        # )

        # AI MESSAGE
        # ai_message = Messages(
        #     conversation_id=conversation.id,
        #     role="ai",
        #     content=ai_answer
        # )

        # db.add(human_message)
        # db.add(ai_message)

        # db.commit()

        # save_message_to_redis(
        #     session,
        #     "human",
        #     request.input
        # )

        # save_message_to_redis(
        #     session,
        #     "ai",
        #     ai_answer
        # )

        return {
            "success": True,
            "session_id": session,
            "messages": [
                {
                    "sender": "human",
                    "text": request.input
                },
                {
                    "sender": "ai",
                    "text": ai_answer
                }
            ]
        }

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        raise HTTPException(
            status_code=500,
            detail=f"[ERROR] {str(e)}, line {exc_tb.tb_lineno if exc_tb else 'unknown'}"
        )


def create_session(db=None):
    # def create_session(db: Session):
    session_id = str(uuid.uuid4())

    # conversation = Conversation(
    #     session_id=session_id
    # )

    # db.add(conversation)
    # db.commit()
    # db.refresh(conversation)

    # return conversation.session_id
    # r.set(f"session_active:{session_id}", "true", ex=session_ttl)
    # print("successfull",session_id)
    return session_id


def start_session_endpoint(db=None):
    # def start_session_endpoint(db: Session = Depends(get_db)):
    session_id = create_session(db=None)

    return {
        "success": True,
        "session_id": session_id
    }


# def get_chat_history(session_id: str,db=None):
#     # def get_chat_history(session_id: str,db: Session = Depends(get_db)):
#     session_meta_key = f"session_active:{session_id}"
#     if not r.exists(session_meta_key):
#         return {"success": False, "messages": [], "message": "Session expired or inactive"}

#     # FIRST TRY REDIS
#     redis_history = load_recent_history_from_redis(session_id)
#     # If redis has messages, use them
#     formatted_messages = []
#     if len(redis_history.messages) > 0:
#         for msg in redis_history.messages:
#             role = "human" if msg.type == "human" else "ai"
#             formatted_messages.append({"sender": role, "text": msg.content})
#         return {"success": True, "messages": formatted_messages}
        # return redis_history
    
    # conversation = (
    #     db.query(Conversation)
    #     .filter(Conversation.session_id == session_id)
    #     .first()
    # )
    # if conversation.active==False:
    #     return {"success":False,
    #     "message":[]
    #     }
    # if not conversation:
    #     return {
    #         "success": False,
    #         "messages": []
    #     }

    # all_messages = (
    #     db.query(Messages)
    #     .filter(Messages.conversation_id == conversation.id)
    #     .order_by(Messages.created_at.asc())
    #     .all()
    # )


    # for msg in all_messages:

    #     formatted_messages.append({
    #         "sender": msg.role,
    #         "text": msg.content
    #     })

    # return {
    #     "success": True,
    #     "messages": []
    # }


# def save_message_to_redis(session_id: str,role: str,content: str):
# 
    # redis_key = f"chat_history:{session_id}"
# 
    # message = {
        # "role": role,
        # "content": content
    # }
# 
    # r.rpush(redis_key, json.dumps(message))
    # Keep only latest 15 messages
    # r.ltrim(redis_key, -REDIS_CHAT_LIMIT, -1)
# 
    # Auto expire after 24 hrs
    # r.expire(redis_key, session_ttl)


app.add_api_route(
    "/start-session",
    start_session_endpoint,
    methods=["POST"]
)

app.add_api_route(
    "/chat",
    chat_endpoint,
    methods=["POST"]
)

# app.add_api_route(
#     "/chat-history/{session_id}",
#     get_chat_history,
#     methods=["GET"]
# )

app.add_api_route(
    "/disable-session/{session_id}",
    disable_active_sessions,
    methods=["GET"]
)