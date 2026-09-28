from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base

# SQLite Database URL
DATABASE_URL = "mysql+pymysql://root:SuperAdminAccess#1234@localhost/chatbot_db"

# Create Engine
engine = create_engine(
    DATABASE_URL,
)

# Create Session
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# Create Base Class
Base = declarative_base()