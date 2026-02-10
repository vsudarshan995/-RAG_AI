import os
import chromadb
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path

# Modern LangChain 0.3+ / 1.0 Imports
from langchain_ollama import OllamaLLM
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

# 1. Configuration & Paths
CHROMA_PATH = r"D:\pY\InsuranceRAG\local_db"
router = APIRouter(tags=["AI Interaction"])

# 2. Initialize Chroma Client (Shared with main.py for Audit Queries)
# This is what allows your preview flow to query by instance_id
client = chromadb.PersistentClient(path=CHROMA_PATH)

# 3. Initialize Shared AI Components
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
llm = OllamaLLM(
    model="llama3:8b-instruct-q2_K",
    num_ctx=2048,  # Limits memory spike
    temperature=0.1
)

# Initialize TWO separate collections
policy_db = Chroma(
    persist_directory=CHROMA_PATH, 
    embedding_function=embeddings, 
    collection_name="policy_master_collection"
)

claims_db = Chroma(
    persist_directory=CHROMA_PATH, 
    embedding_function=embeddings, 
    collection_name="claims_collection"
)

evaluations_db = Chroma(
    persist_directory=CHROMA_PATH, 
    embedding_function=embeddings, 
    collection_name="evaluation_audit_log"
)

# 4. Request Schemas
class QueryRequest(BaseModel):
    question: str
    client_id: str = "Company"

# --- ENDPOINT 1: Policy Auditor (Strictly Master Policies) ---
@router.post("/ask/policy")
async def ask_policy(request: QueryRequest):
    """Answers using only the policy_master_collection."""
    system_prompt = (
        "You are a professional insurance auditor. Use ONLY the provided Policy context. "
        "If it's not in the documents, say so.\n\nContext: {context}"
    )
    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{input}")])

    # No metadata filter needed because this collection ONLY has policies
    retriever = policy_db.as_retriever(search_kwargs={"k": 5})
    chain = create_retrieval_chain(retriever, create_stuff_documents_chain(llm, prompt))
    
    try:
        response = chain.invoke({"input": request.question})
        return {"answer": response["answer"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINT 2: Claim Evaluator (Policy + Claims Comparison) ---
@router.post("/ask/evaluate-claim")
async def evaluate_claim(request: QueryRequest):
    """Combines Policy rules and specific Client Claim data for cross-checking."""
    system_prompt = (
        "You are a claims adjuster. Compare the client's submitted claim data against "
        "the master policy rules to find discrepancies or fraud.\n\nContext: {context}"
    )
    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{input}")])

    # 1. Manually fetch context from both collections
    policy_context = policy_db.similarity_search(request.question, k=3)
    claim_context = claims_db.similarity_search(
        request.question, 
        k=3, 
        filter={"client_id": request.client_id}
    )
    
    # 2. Combine for the Chain
    # We pass the combined docs directly into the stuff documents chain
    combined_docs = policy_context + claim_context
    stuff_chain = create_stuff_documents_chain(llm, prompt)
    
    try:
        # We bypass create_retrieval_chain here to control the context precisely
        response = stuff_chain.invoke({
            "input": request.question,
            "context": combined_docs
        })
        return {"client_id": request.client_id, "evaluation": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))