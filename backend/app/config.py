import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Relational Database (SQLite)
DATABASE_URL = f"sqlite:///{DATA_DIR}/stitchmind.db"

# Vector Database (LanceDB)
LANCE_DB_PATH = str(DATA_DIR / ".lancedb")

# Credentials storage
GOOGLE_CREDENTIALS_FILE = DATA_DIR / "credentials.json"
GOOGLE_TOKENS_FILE = DATA_DIR / "google_tokens.json"

# Key derivation for credential encryption
ENCRYPTION_KEY_PATH = DATA_DIR / "secret.key"

# LLM Providers & API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Default Embedding Model
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
