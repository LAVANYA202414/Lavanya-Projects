import os 
import sys 
import yaml
import json
import uuid
import redis
import warnings
from typing import Dict, Optional 
from datetime import datetime, timedelta 
from fastapi import FastAPI, HTTPException,Depends
from pydantic import EmailStr, BaseModel 
from fastapi.middleware.cors import CORSMiddleware 
from langchain_chroma import Chroma 
from langchain_openai import ChatOpenAI, OpenAIEmbeddings 
from langchain_core.runnables.history import RunnableWithMessageHistory 
from langchain_community.chat_message_histories import ChatMessageHistory 
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder 
from langchain_classic.chains.combine_documents import create_stuff_documents_chain 
from langchain_classic.chains import create_retrieval_chain, create_history_aware_retriever 
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from models import Conversation, Messages
from database import Base,engine,SessionLocal
from sqlalchemy.orm import Session
