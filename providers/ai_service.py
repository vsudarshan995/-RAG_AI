import os
from pathlib import Path
import chromadb
from fastapi import APIRouter
from langchain_ollama import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from config import config

router = APIRouter(tags=["AI Interaction"])

# Project Base Directory Definition (Required by main.py)
ROOT_DIR = Path(getattr(config, "PROD_BASE_PATH", Path(__file__).resolve().parent.parent))

# Initialize ChromaDB Client:
# Prefers HttpClient on port 8001 (for run_all.py multi-process setup),
# with automatic fallback to PersistentClient for local standalone execution.
try:
    client = chromadb.HttpClient(host="localhost", port=8001)
    client.heartbeat()
except Exception:
    client = chromadb.PersistentClient(path=config.DB_PATH)

# Shared Embeddings Model
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Fast Router & Reasoning LLMs (Using ChatOllama)
fast_llm = ChatOllama(
    model=config.FAST_LLM_MODEL,
    temperature=0, 
    num_thread=4,
    num_predict=100
)

reasoning_llm = ChatOllama(
    model=config.REASONING_LLM_MODEL,
    temperature=config.TEMPERATURE,
    num_ctx=2048,
    num_thread=4,
    num_predict=350
)

# Pure Vector Stores (Semantic RAG and Historical Claim Anomaly Detection)
policy_vr_db = Chroma(
    client=client,
    collection_name=config.COLLECTIONS.get("policy_vector", "vr_policy"),
    embedding_function=embeddings
)

claims_db = Chroma(
    client=client,
    collection_name=config.COLLECTIONS.get("claims", "claims_collection"),
    embedding_function=embeddings
)

# Policy Metadata Registry in Chroma
policy_registry_db = client.get_or_create_collection(
    name=config.COLLECTIONS.get("registry", "policy_registry")
)

def reset_vector_collection(collection_name: str):
    """Purges and resets a vector collection cleanly."""
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass
    return client.get_or_create_collection(name=collection_name)