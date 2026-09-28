from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base , sessionmaker
from core.config import settings
from urllib.parse import quote_plus

password = quote_plus(settings.POSTGRES_PASSWORD)

# Database Credentials
DATABASE_URL = (
    f"postgresql://{settings.POSTGRES_USER}:"
    f"{password}@"
    f"{settings.POSTGRES_HOST}:"
    f"{settings.POSTGRES_PORT}/"
    f"{settings.POSTGRES_DB}"
)


# Engine manage actual connection to the DB
engine = create_engine(DATABASE_URL)

# SessionLocal establishes connections to the DB
SessionLocal= sessionmaker(
                            autocommit = False,
                            autoflush= False,
                            bind= engine
                        )

# Base class for your SQL Database Models
Base = declarative_base()

# Fastapi Dependency to handle request-scopped DB sessions
def get_db():
    db = SessionLocal()
    
    try:
        yield db
    
    finally:
        db.close()