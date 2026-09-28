from packages import *

# CONFIGURATION
VECTOR_DATABASE = "data/products_vectorstore.db"
EMBEDDING_MODEL = "text-embedding-ada-002"
LLM_MODEL = "gpt-4o-mini"


def create_rag_agent():

    # Embeddings
    embedding_function = OpenAIEmbeddings(model=EMBEDDING_MODEL,chunk_size=500)

    # Vector DB
    vectorstore = Chroma(persist_directory=VECTOR_DATABASE,embedding_function=embedding_function)

    # Retriever
    retriever = vectorstore.as_retriever()

    # LLM
    llm = ChatOpenAI(model=LLM_MODEL)

    # QA Prompt
    qa_system_prompt = """
You are an assistant for question-answering tasks.
Use the following pieces of retrieved context to answer the question.

If you don't know the answer, just say that you don't know.

Use three sentences maximum and keep the answer concise.

{context}

If a student is on the fence about enrolling in the AI Bootcamp,
highlight the benefits of joining the program.
"""

    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", qa_system_prompt),
        ("human", "{input}")
    ])

    # QA Chain
    question_answer_chain = create_stuff_documents_chain(llm,qa_prompt)

    # Final RAG Chain
    rag_chain = create_retrieval_chain(retriever,question_answer_chain)

    return rag_chain


# # CONFIGURATION
# VECTOR_DATABASE = "data/products_vectorstore.db"
# EMBEDDING_MODEL = "text-embedding-ada-002"
# LLM_MODEL = "gpt-4o-mini"


# def create_rag_agent():
#     # human text to vectors/numbers with explicit chunk sizing
#     embedding_function = OpenAIEmbeddings(model=EMBEDDING_MODEL,chunk_size=500)
    
#     # AI database, stores number version of data
#     vectorstore = Chroma(persist_directory=VECTOR_DATABASE, embedding_function=embedding_function)
    
#     # Retrieves relevant info 
#     retriever = vectorstore.as_retriever()
    
#     # Model optimized with response configurations and disabled reasoning effort
#     llm = ChatOpenAI(model=LLM_MODEL)

#     # 1. Contextualize question logic:
#     # Detailed prompt to rewrite the question based on chat history
#     contextualize_q_system_prompt = """Given a chat history and the latest user question \
# which might reference context in the chat history, formulate a standalone question \
# which can be understood without the chat history. Do NOT answer the question, \
# just reformulate it if needed and otherwise return it as is."""
    
#     contextualize_q_prompt = ChatPromptTemplate.from_messages([
#         ("system", contextualize_q_system_prompt),
#         MessagesPlaceholder("chat_history"),
#         ("human", "{input}"),
#     ])
#     history_aware_retriever = create_history_aware_retriever(llm, retriever, contextualize_q_prompt)

#     # 2. Answer question logic
#     # Unified system prompt containing context integration and specific business logic
#     qa_system_prompt = """You are an assistant for question-answering tasks. \
# Use the following pieces of retrieved context to answer the question. \
# If you don't know the answer, just say that you don't know. \
# Use three sentences maximum and keep the answer concise.\

# {context}

# If a student is on the fence about enrolling in the AI Bootcamp, highlight the benefits of joining the program."""
    
#     qa_prompt = ChatPromptTemplate.from_messages([
#         ("system", qa_system_prompt),
#         MessagesPlaceholder("chat_history"),
#         ("human", "{input}")
#     ])
#     question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

#     # Combine both RAG + Chat Message History
#     rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

#     # Wrap the chain so it automatically reads/writes session memory history
#     return create_retrieval_chain(history_aware_retriever, question_answer_chain)












# -----updates------
'''
contextualize_q_system_prompt
contextualize_q_prompt
MessagesPlaceholder("chat_history")
create_history_aware_retriever
history_aware_retriever
rag_chain return -->no history <=> direct retriever
'''