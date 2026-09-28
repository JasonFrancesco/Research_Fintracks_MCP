import os
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Load .env file from mcp-server directory or fallback to backend directory
env_path = Path(__file__).resolve().parent / ".env"
backend_env_path = backend_path / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
elif backend_env_path.exists():
    load_dotenv(dotenv_path=backend_env_path)
else:
    load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set. Please create a .env file with DATABASE_URL.")

MCP_API_KEY = os.getenv("MCP_API_KEY", "default-dev-key-123") # Use env var in production
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_session():
    return SessionLocal()

