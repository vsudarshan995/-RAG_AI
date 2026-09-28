import chromadb
from pathlib import Path
from fastapi import APIRouter
from langchain_ollama import OllamaLLM
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from config import config

router = APIRouter(tags=["AI Interaction"])

ROOT_DIR = Path(config.PROD_BASE_PATH)
client = chromadb.PersistentClient(path=config.DB_PATH)
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# --- Local Multi-Model Setup ---

# 1. Fast Router (SmolLM2): 0 temperature for strict JSON
fast_llm = OllamaLLM(
    model=config.FAST_LLM_MODEL,
    temperature=0, 
    num_thread=4,
    num_predict=100
)

# 2. Reasoning Model (Llama 3.2 1B): Deep reading and summaries
reasoning_llm = OllamaLLM(
    model=config.REASONING_LLM_MODEL,
    temperature=config.TEMPERATURE,
    num_ctx=1024,      # Keeps reading payload lightweight
    num_thread=4,      # Binds to your i7 physical cores
    num_predict=200
)

# Vector Store Setup
db_args = {
    "persist_directory": config.DB_PATH,
    "embedding_function": embeddings
}

policy_vr_db = Chroma(collection_name=config.COLLECTIONS["policy_vector"], **db_args)
claims_db = Chroma(collection_name=config.COLLECTIONS["claims"], **db_args)
evaluations_db = Chroma(collection_name=config.COLLECTIONS["audit"], **db_args)
instance_log = Chroma(collection_name=config.COLLECTIONS["instances"], **db_args)

policy_registry_db = client.get_or_create_collection(name=config.COLLECTIONS["registry"])
clients_db = client.get_or_create_collection(name=config.COLLECTIONS["clients"])
human_review_db = client.get_or_create_collection(name=config.COLLECTIONS["human_reviews"])

def reset_single_collection(collection_name: str):
    """
    Safely purges and resets a ChromaDB collection by deleting it 
    from the persistent client and recreating it fresh.
    """
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass  # Collection might not exist yet
        
    # Recreate the correct collection instance based on config mapping
    global policy_vr_db, claims_db, evaluations_db, instance_log, policy_registry_db, clients_db, human_review_db
    
    if collection_name == config.COLLECTIONS["policy_vector"]:
        policy_vr_db = Chroma(collection_name=collection_name, **db_args)
    elif collection_name == config.COLLECTIONS["claims"]:
        claims_db = Chroma(collection_name=collection_name, **db_args)
    elif collection_name == config.COLLECTIONS["audit"]:
        evaluations_db = Chroma(collection_name=collection_name, **db_args)
    elif collection_name == config.COLLECTIONS["instances"]:
        instance_log = Chroma(collection_name=collection_name, **db_args)
    elif collection_name == config.COLLECTIONS["registry"]:
        policy_registry_db = client.get_or_create_collection(name=collection_name)
    elif collection_name == config.COLLECTIONS["clients"]:
        clients_db = client.get_or_create_collection(name=collection_name)
    elif collection_name == config.COLLECTIONS["human_reviews"]:
        human_review_db = client.get_or_create_collection(name=collection_name)
    else:
        client.get_or_create_collection(name=collection_name)