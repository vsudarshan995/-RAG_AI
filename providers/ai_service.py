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

policy_db = Chroma(collection_name=config.COLLECTIONS["policies"], **db_args)
claims_db = Chroma(collection_name=config.COLLECTIONS["claims"], **db_args)
evaluations_db = Chroma(collection_name=config.COLLECTIONS["audit"], **db_args)
instance_log = Chroma(collection_name=config.COLLECTIONS["instances"], **db_args)

policy_registry_db = client.get_or_create_collection(name=config.COLLECTIONS["registry"])
clients_db = client.get_or_create_collection(name=config.COLLECTIONS["clients"])
human_review_db = client.get_or_create_collection(name=config.COLLECTIONS["human_reviews"])