import uuid
import shutil
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from psycopg.rows import dict_row

from config import config

# Modular Providers
import providers.ai_service as ai_service
from providers.ai_service import (
    router as ai_router, 
    client, 
    ROOT_DIR, 
    policy_vr_db, 
    policy_registry_db,
    claims_db
)
from providers.db_service import db_service, pool
from providers.chunker import process_document_with_semantic_chunking
from providers.rag_service import process_rag_query
from core.graph import agent_system, InvestigationRequest

app = FastAPI(title="AssureEval Enterprise (AEIP) API")
app.include_router(ai_router)

BASE_DIR = ROOT_DIR / "storage"
BASE_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/")
def read_root():
    return {
        "status": "System Online", 
        "platform": "AssureEval Enterprise (AEIP)",
        "docs_url": "/docs",
        "root_directory": str(ROOT_DIR)
    }

# --- ASYNCHRONOUS MULTI-AGENT ENDPOINTS ---

@app.post("/ask/investigate/async", tags=["Multi-Agent Intelligence"])
async def start_async_investigation(request: InvestigationRequest, background_tasks: BackgroundTasks):
    instance_id = str(uuid.uuid4())
    background_tasks.add_task(run_agent_background_task, instance_id, request)

    return {
        "instance_id": instance_id,
        "status": "Triggered",
        "verification_url": f"/review/pending/{instance_id}",
        "message": "Investigation started. Monitor progress via instance ID."
    }

async def run_agent_background_task(instance_id: str, request: InvestigationRequest):
    try:
        user_input = request.question or f"Audit for {request.submission_date}"
        config_graph = {"configurable": {"thread_id": instance_id}}
        
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "client_id": request.client_id,
            "submission_date": request.submission_date,
            "instance_id": instance_id,
            "risk_score": 0,
            "policy_category": "Pending",
            "policy_context": "",
            "compliance_report": "",
            "final_verdict": "",
            "human_action": None,
            "human_comments": None
        }
        
        async for _ in agent_system.astream(initial_state, config=config_graph):
            pass
            
    except asyncio.CancelledError:
        db_service.archive_evaluation(
            instance_id=instance_id,
            client_id=request.client_id,
            risk_score=0,
            final_verdict="Task cancelled due to server shutdown or reload."
        )
    except Exception as e:
        db_service.archive_evaluation(
            instance_id=instance_id,
            client_id=request.client_id,
            risk_score=100,
            final_verdict=f"Investigation terminated unexpectedly: {str(e)}"
        )

# --- POLICY KNOWLEDGE BASE MANAGEMENT ENDPOINTS ---

@app.post("/policies/upload", tags=["Policy Management"])
async def upload_policy_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    category: str = Form("General"),
    effective_date: str = Form(str(datetime.now().date())),
    effective_end_date: str = Form(str(datetime.now().date())),
    uploaded_by: str = Form("System Admin")
):
    file_path = BASE_DIR / file.filename
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        doc_id = f"pol_{int(datetime.now().timestamp())}_{file.filename}"
        
        # 1. Register file in ChromaDB policy registry
        policy_registry_db.upsert(
            documents=[f"Registry entry for {file.filename}"],
            metadatas=[{
                "doc_id": doc_id,
                "filename": file.filename,
                "document_category": category,
                "effective_date": effective_date,
                "effective_end_date": effective_end_date,
                "uploaded_by": uploaded_by,
                "date_added": upload_date,
                "embedding_status": "Processing"
            }],
            ids=[doc_id]
        )
        
        # 2. Dispatch background task
        background_tasks.add_task(
            process_policy_background_task, 
            str(file_path), 
            file.filename, 
            category,
            doc_id,
            effective_date,
            effective_end_date,
            uploaded_by
        )
        
        return {"filename": file.filename, "doc_id": doc_id, "status": "Queued for processing."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def process_policy_background_task(
    file_path_str: str, 
    filename: str, 
    category: str, 
    doc_id: str, 
    effective_date: str, 
    effective_end_date: str,
    uploaded_by: str
):
    try:
        chunks = process_document_with_semantic_chunking(
            file_path_str, filename, category, doc_id, effective_date, effective_end_date, uploaded_by
        )

        policy_vr_db.add_documents(chunks)

        existing = policy_registry_db.get(ids=[doc_id])
        if existing and existing.get('metadatas'):
            meta = existing['metadatas'][0]
            meta['embedding_status'] = "Completed"
            policy_registry_db.upsert(
                documents=[f"Registry entry for {filename}"],
                metadatas=[meta],
                ids=[doc_id]
            )
    except Exception as e:
        try:
            existing = policy_registry_db.get(ids=[doc_id])
            if existing and existing.get('metadatas'):
                meta = existing['metadatas'][0]
                meta['embedding_status'] = "Failed"
                policy_registry_db.upsert(
                    documents=[f"Registry entry for {filename}"],
                    metadatas=[meta],
                    ids=[doc_id]
                )
        except Exception:
            pass

# --- RAG QUERY / CHATBOT ENDPOINT ---

class ChatQueryRequest(BaseModel):
    question: str
    category_filter: str = "All"

@app.post("/chatbot/query", tags=["Quality Testing Chatbot"])
async def chatbot_query_endpoint(request: ChatQueryRequest):
    try:
        result = process_rag_query(request.question, request.category_filter)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- CLIENT PORTFOLIO MANAGEMENT ENDPOINTS (POSTGRESQL) ---

class ClientRegistrationRequest(BaseModel):
    client_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None

@app.get("/clients", tags=["Client Management"])
async def get_all_clients():
    """Retrieves all registered client profiles from PostgreSQL."""
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT client_id, name, email, phone, created_at FROM clients ORDER BY created_at DESC;")
                clients = cur.fetchall()
        return {"clients": clients}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clients/register", tags=["Client Management"])
async def register_client(request: ClientRegistrationRequest):
    """Registers or updates a client profile directly in PostgreSQL."""
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO clients (client_id, name, email, phone)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (client_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        phone = EXCLUDED.phone;
                    """,
                    (request.client_id, request.name, request.email, request.phone)
                )
        return {"status": "Success", "client_id": request.client_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- CLAIMS SUBMISSION & EVALUATION ENDPOINTS ---

class ClaimSubmissionRequest(BaseModel):
    claim_id: str
    client_id: str
    policy_number: str
    incident_date: str
    claim_amount: float
    claim_category: str

@app.post("/claims/submit", tags=["Claims & Evaluations"])
async def submit_claim(request: ClaimSubmissionRequest, background_tasks: BackgroundTasks):
    try:
        # Ingest claim semantic description into ChromaDB vector store
        claims_db.upsert(
            documents=[f"Claim {request.claim_id} by Client {request.client_id} for amount {request.claim_amount} AED. Category: {request.claim_category}"],
            metadatas=[{
                "claim_id": request.claim_id,
                "client_id": request.client_id,
                "policy_number": request.policy_number,
                "incident_date": request.incident_date,
                "claim_amount": request.claim_amount,
                "claim_category": request.claim_category,
                "status": "PENDING_EVALUATION",
                "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }],
            ids=[request.claim_id]
        )

        instance_id = str(uuid.uuid4())
        inv_request = InvestigationRequest(
            client_id=request.client_id,
            submission_date=request.incident_date,
            question=f"Evaluate claim {request.claim_id} under policy {request.policy_number} for amount {request.claim_amount} AED."
        )
        background_tasks.add_task(run_agent_background_task, instance_id, inv_request)

        return {
            "status": "Success",
            "claim_id": request.claim_id,
            "instance_id": instance_id,
            "message": "Claim registered and queued for multi-agent evaluation."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- HUMAN-IN-THE-LOOP (POSTGRESQL) ---

@app.get("/reviews/pending", tags=["Human-in-the-Loop"])
async def list_pending_reviews():
    try:
        tasks = db_service.get_pending_reviews()
        return {"pending_reviews": tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/review/pending/{instance_id}", tags=["Human-in-the-Loop"])
async def get_pending_review_details(instance_id: str):
    config_dict = {"configurable": {"thread_id": instance_id}}
    state_snapshot = agent_system.get_state(config_dict)
    
    if not state_snapshot or not state_snapshot.next:
        raise HTTPException(status_code=404, detail="No active review pending for this instance ID.")
        
    return {
        "instance_id": instance_id,
        "values": state_snapshot.values,
        "next_step": state_snapshot.next
    }

@app.post("/review/resolve/{instance_id}", tags=["Human-in-the-Loop"])
async def resolve_human_review(instance_id: str, action: str, comments: str = ""):
    action_clean = action.strip().lower()
    if action_clean not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'.")

    thread_config = {"configurable": {"thread_id": instance_id}}
    status_label = "APPROVED" if action_clean == "approve" else "REJECTED"

    try:
        agent_system.update_state(
            thread_config,
            {"human_action": action_clean, "human_comments": comments},
            as_node="human_review"
        )
        agent_system.invoke(None, config=thread_config)
        db_service.resolve_review_task(instance_id, status_label, comments)

        return {"instance_id": instance_id, "status": f"Successfully resolved as {status_label}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume execution: {str(e)}")

@app.get("/health", tags=["System Health"])
def health_check():
    chroma_status = "offline"
    try:
        client.heartbeat()
        chroma_status = "online (port 8001)"
    except Exception:
        pass

    return {
        "status": "healthy",
        "chroma_server": chroma_status,
        "database": "PostgreSQL (rag_ai)"
    }