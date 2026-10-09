import os
from pathlib import Path
import chromadb
from fastapi import APIRouter
from langchain_ollama import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from config import config

router = APIRouter(tags=["AI Interaction"])

# Project Base Directory Definition
ROOT_DIR = Path(getattr(config, "PROD_BASE_PATH", Path(__file__).resolve().parent.parent))

# Initialize ChromaDB Client (Prefer Standalone HTTP on 8001; Fallback to Persistent)
try:
    client = chromadb.HttpClient(
        host=getattr(config, "CHROMA_HOST", "localhost"), 
        port=getattr(config, "CHROMA_PORT", 8001)
    )
    client.heartbeat()
except Exception:
    client = chromadb.PersistentClient(path=config.DB_PATH)

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Fast Router & Reasoning LLMs
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

# Pure Vector Stores
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

policy_registry_db = client.get_or_create_collection(
    name=config.COLLECTIONS.get("registry", "policy_registry")
)

def reset_vector_collection(collection_name: str):
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass
    return client.get_or_create_collection(name=collection_name)