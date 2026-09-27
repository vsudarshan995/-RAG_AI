import os
from pathlib import Path

class Config:
    PROD_BASE_PATH = r"D:\pY\InsuranceRAG" 
    
    DB_PATH = os.getenv("CHROMA_PATH", os.path.join(PROD_BASE_PATH, "local_db"))
    STORAGE_PATH = os.getenv("STORAGE_PATH", os.path.join(PROD_BASE_PATH, "storage"))
    LOG_FILE = os.getenv("LOG_FILE", os.path.join(PROD_BASE_PATH, "Logs", "processor_debug.log"))
    
    # --- Multi-Model Settings ---
    FAST_LLM_MODEL = "llama3.2:1b"    # For routing and quick greetings
    REASONING_LLM_MODEL = "llama3.2:1b" # For deep RAG reading and summaries
    TEMPERATURE = 0.1
    #GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your_gemini_api_key_here")
    
    COLLECTIONS = {
        "policies": "policy_master_collection",
        "claims": "claims_collection",
        "audit": "evaluation_audit_log",
        "instances": "instance_log",
        "registry": "policy_registry",
        "clients": "clients_collection",
        "human_reviews": "human_review_tasks"
    }

config = Config()

os.makedirs(config.DB_PATH, exist_ok=True)
os.makedirs(config.STORAGE_PATH, exist_ok=True)
log_dir = os.path.dirname(config.LOG_FILE)
if log_dir:
    os.makedirs(log_dir, exist_ok=True)