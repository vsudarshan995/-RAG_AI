from pathlib import Path
import chromadb
from fastapi import APIRouter
from langchain_ollama import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from config import config

router = APIRouter(tags=["AI Interaction"])

# Embeddings & Chroma Persistent Client
client = chromadb.PersistentClient(path=config.DB_PATH)
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

# Pure Vector Stores (Semantic RAG only)
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

# Fallback metadata registry in Chroma if not fully in Postgres
policy_registry_db = client.get_or_create_collection(
    name=config.COLLECTIONS.get("registry", "policy_registry")
)

def reset_vector_collection(collection_name: str):
    """Purges and resets a vector collection."""
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass
    return client.get_or_create_collection(name=collection_name)