import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    PROD_BASE_PATH = r"D:\pY\InsuranceRAG" 
    
    # Storage and paths
    DB_PATH = os.getenv("CHROMA_PATH", os.path.join(PROD_BASE_PATH, "local_db"))
    STORAGE_PATH = os.getenv("STORAGE_PATH", os.path.join(PROD_BASE_PATH, "storage"))
    LOG_FILE = os.getenv("LOG_FILE", os.path.join(PROD_BASE_PATH, "Logs", "processor_debug.log"))
    
    # --- Standalone ChromaDB Server Configuration ---
    CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
    CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8001"))

    # --- PostgreSQL Checkpointer URI ---
    POSTGRES_DB_URI = os.getenv(
        "POSTGRES_DB_URI", 
        "postgresql://postgres:postgres@localhost:5432/rag_ai"
    )

    # --- Multi-Model Settings ---
    FAST_LLM_MODEL = "llama3.2:1b"
    REASONING_LLM_MODEL = "llama3.2:1b"
    TEMPERATURE = 0.1
    
    # Active Vector Collections
    COLLECTIONS = {
        "policy_vector": "vr_policy",
        "claims": "claims_collection",
        "registry": "policy_registry"
    }

config = Config()

os.makedirs(config.DB_PATH, exist_ok=True)
os.makedirs(config.STORAGE_PATH, exist_ok=True)
log_dir = os.path.dirname(config.LOG_FILE)
if log_dir:
    os.makedirs(log_dir, exist_ok=True)