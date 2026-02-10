import chromadb
from pathlib import Path
from fastapi import APIRouter
from langchain_ollama import OllamaLLM
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from config import config # Import centralized config

router = APIRouter(tags=["AI Interaction"])

ROOT_DIR = Path(config.PROD_BASE_PATH)

client = chromadb.PersistentClient(path=config.DB_PATH)
# Initialize Shared AI Components
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
llm = OllamaLLM(
    model=config.LLM_MODEL,
    num_ctx=2048,
    temperature=config.TEMPERATURE
)

# Common configuration for all ChromaDB collections
db_args = {
    "persist_directory": config.DB_PATH,
    "embedding_function": embeddings
}

policy_db = Chroma(collection_name=config.COLLECTIONS["policies"], **db_args)
claims_db = Chroma(collection_name=config.COLLECTIONS["claims"], **db_args)
evaluations_db = Chroma(collection_name=config.COLLECTIONS["audit"], **db_args)
instance_log = Chroma(collection_name=config.COLLECTIONS["instances"], **db_args)

