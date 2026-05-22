import os
from dotenv import load_dotenv

_base = os.path.dirname(__file__)
load_dotenv(os.path.join(_base, ".env"))
load_dotenv(os.path.join(_base, "..", ".env"))

# Groq LLM (free tier, best Arabic support)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"

# Embeddings (lightweight, runs on CPU)
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# ChromaDB
CHROMA_DB_PATH = os.path.join(_base, "../chroma_db")
CHROMA_COLLECTION_NAME = "real_estate_arabic"

# Data directories
UPLOADS_DIR = os.path.join(_base, "../Data/uploads")
APPLICATIONS_DIR = os.path.join(_base, "../Data/applications")

# RAG
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
TOP_K_RESULTS = 5
MAX_CHAT_HISTORY = 10

# MongoDB
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB  = os.getenv("MONGODB_DB",  "")    # empty = auto-detect first non-system DB
# Collections that hold housing/project data for the pandas router.
# Comma-separated. Leave empty to auto-detect (looks for priceRange/price columns).
MONGODB_HOUSING_COLLECTIONS = os.getenv("MONGODB_HOUSING_COLLECTIONS", "")

# Security
API_KEY = os.getenv("API_KEY", "")            # empty = auth disabled
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
