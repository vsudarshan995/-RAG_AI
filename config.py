import os
from pathlib import Path

class Config:
    # Hardcoded Production Base Path
    # This ensures consistency even if running in a container or different drive
    PROD_BASE_PATH = r"D:\pY\InsuranceRAG" 
    
    # Paths - Env variable takes priority, otherwise uses hardcoded base
    DB_PATH = os.getenv("CHROMA_PATH", os.path.join(PROD_BASE_PATH, "local_db"))
    STORAGE_PATH = os.getenv("STORAGE_PATH", os.path.join(PROD_BASE_PATH, "storage"))
    LOG_FILE = os.getenv("LOG_FILE", os.path.join(PROD_BASE_PATH, "Logs", "processor_debug.log"))
    
    # Model Settings
    LLM_MODEL = "llama3:8b-instruct-q2_K"
    TEMPERATURE = 0.1
    
    # Collection Registry
    COLLECTIONS = {
        "policies": "policy_master_collection",
        "claims": "claims_collection",
        "audit": "evaluation_audit_log",
        "instances": "instance_log"
    }

    # Processing Constants
    DEBOUNCE_SECONDS = 10
    FILE_RETRIES = 15
    FILE_DELAY = 2

config = Config()

# Ensure directories exist upon startup
os.makedirs(config.DB_PATH, exist_ok=True)
os.makedirs(config.STORAGE_PATH, exist_ok=True)
log_dir = os.path.dirname(config.LOG_FILE)
if log_dir:
    os.makedirs(log_dir, exist_ok=True)