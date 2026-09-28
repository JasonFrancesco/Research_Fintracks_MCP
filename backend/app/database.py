from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# create_engine handles the connection to the database
# PostgreSQL requires psycopg2
engine = create_engine(DATABASE_URL)

# sessionmaker creates a factory for database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is used for our models to inherit from
from .models.models import Base

def get_db():
    """
    Dependency function to provide a database session per request.
    Ensures the connection is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
