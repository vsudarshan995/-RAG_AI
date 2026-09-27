import uuid
import shutil
import asyncio
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel

# Modular Imports - Import ai_service module directly to prevent stale collection references
import providers.ai_service as ai_service
from providers.ai_service import router as ai_router, evaluations_db, client, ROOT_DIR, instance_log, human_review_db, clients_db, policy_db, policy_registry_db
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
        
        async for event in agent_system.astream(initial_state, config=config_graph):
            pass
            
    except asyncio.CancelledError:
        evaluations_db.add_texts(
            texts=["Task was cancelled due to server shutdown or reload."],
            metadatas=[{"instance_id": instance_id, "status": "CANCELLED"}]
        )
    except Exception as e:
        instance_log.add_texts(
            texts=[f"Investigation terminated: {str(e)}"],
            metadatas=[{
                "instance_id": instance_id,
                "client_id": request.client_id,
                "status": "FAILED",
                "error_details": str(e),
                "completion_time": datetime.now().isoformat()
            }],
            ids=[instance_id]
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
        
        # 1. Register file using dynamic ai_service reference
        ai_service.policy_registry_db.upsert(
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
    print(f"🚀 [BACKGROUND TASK STARTED] Processing file: {filename} (ID: {doc_id})")
    try:
        chunks = process_document_with_semantic_chunking(
            file_path_str, filename, category, doc_id, effective_date, effective_end_date, uploaded_by
        )

        ai_service.policy_db.add_documents(chunks)

        existing = ai_service.policy_registry_db.get(ids=[doc_id])
        if existing and existing.get('metadatas'):
            meta = existing['metadatas'][0]
            meta['embedding_status'] = "Completed"
            ai_service.policy_registry_db.upsert(
                documents=[f"Registry entry for {filename}"],
                metadatas=[meta],
                ids=[doc_id]
            )
        print(f"🎉 [BACKGROUND TASK SUCCESS] {filename} is fully processed!")

    except Exception as e:
        print(f"❌ [BACKGROUND TASK FAILED] Error on {filename}: {str(e)}")
        import traceback
        traceback.print_exc()
        
        try:
            existing = ai_service.policy_registry_db.get(ids=[doc_id])
            if existing and existing.get('metadatas'):
                meta = existing['metadatas'][0]
                meta['embedding_status'] = "Failed"
                ai_service.policy_registry_db.upsert(
                    documents=[f"Registry entry for {filename}"],
                    metadatas=[meta],
                    ids=[doc_id]
                )
        except Exception as db_err:
            print(f"💥 Failed to update status to Failed in DB: {db_err}")

# --- QUALITY TESTING CHATBOT ENDPOINT ---

class ChatQueryRequest(BaseModel):
    question: str
    category_filter: str = "All"

@app.post("/chatbot/query", tags=["Quality Testing Chatbot"])
async def chatbot_query_endpoint(request: ChatQueryRequest):
    """
    Executes an intent-driven RAG query against the policy knowledgebase 
    using temporal overlap and category metadata filtering.
    """
    try:
        result = process_rag_query(request.question, request.category_filter)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- CLIENT PORTFOLIO MANAGEMENT ENDPOINTS ---

class ClientRegistrationRequest(BaseModel):
    client_id: str
    name: str
    risk_tier: str
    kyc_status: str
    active_policies: int

@app.get("/clients", tags=["Client Management"])
async def get_all_clients():
    """Retrieves all registered client profiles from the vector database."""
    try:
        results = ai_service.clients_db.get(include=["metadatas"])
        if not results or not results.get('metadatas'):
            return {"clients": []}
        return {"clients": results["metadatas"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clients/register", tags=["Client Management"])
async def register_client(request: ClientRegistrationRequest):
    """Registers or updates a client profile directly into the database."""
    try:
        ai_service.clients_db.upsert(
            documents=[f"Client Profile: {request.name} ({request.client_id}) with risk tier {request.risk_tier}"],
            metadatas=[{
                "client_id": request.client_id,
                "name": request.name,
                "risk_tier": request.risk_tier,
                "kyc_status": request.kyc_status,
                "active_policies": request.active_policies,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }],
            ids=[request.client_id]
        )
        return {"status": "Success", "client_id": request.client_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- HUMAN-IN-THE-LOOP ENDPOINTS ---

@app.get("/reviews/pending", tags=["Human-in-the-Loop"])
async def list_pending_reviews():
    """Retrieves all insurance claims currently flagged for human review."""
    try:
        results = ai_service.human_review_db.get(where={"status": "PENDING_REVIEW"})
        tasks = results.get("metadatas", []) if results else []
        return {"pending_reviews": tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/review/pending/{instance_id}", tags=["Human-in-the-Loop"])
async def get_pending_review_details(instance_id: str):
    """Fetches the paused workflow state snapshot for review."""
    config = {"configurable": {"thread_id": instance_id}}
    state_snapshot = agent_system.get_state(config)
    
    if not state_snapshot.next:
        raise HTTPException(status_code=404, detail="No active review pending for this instance ID.")
        
    return {
        "instance_id": instance_id,
        "values": state_snapshot.values,
        "next_step": state_snapshot.next
    }

@app.get("/review/history/{instance_id}", tags=["Human-in-the-Loop"])
async def get_decision_history(instance_id: str):
    """Shows node-by-node decisions made by previous agents."""
    config = {"configurable": {"thread_id": instance_id}}
    try:
        history_snapshot = list(agent_system.get_state_history(config))
        node_decisions = []
        for state in history_snapshot:
            node_decisions.append({
                "next_steps": state.next,
                "values": {
                    "policy_category": state.values.get("policy_category"),
                    "risk_score": state.values.get("risk_score"),
                    "compliance_report": state.values.get("compliance_report"),
                    "messages": [msg.content for msg in state.values.get("messages", [])]
                }
            })
        return {"instance_id": instance_id, "decision_history": node_decisions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/review/resolve/{instance_id}", tags=["Human-in-the-Loop"])
async def resolve_human_review(instance_id: str, action: str, comments: str = ""):
    """Resolves human review, updates database, and resumes agent workflow."""
    action = action.strip().lower()
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'.")

    config = {"configurable": {"thread_id": instance_id}}
    status_label = "APPROVED" if action == "approve" else "REJECTED"
    
    try:
        ai_service.human_review_db.update(
            ids=[instance_id],
            metadatas=[{
                "status": status_label,
                "human_action": action,
                "human_comments": comments,
                "resolved_at": datetime.now().isoformat()
            }]
        )
    except Exception:
        pass

    resume_payload = {"human_action": action, "human_comments": comments}
    try:
        async for event in agent_system.astream(Command(resume=resume_payload), config=config):
            pass
        return {"instance_id": instance_id, "status": f"Successfully resolved as {status_label}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# --- SYSTEM ADMINISTRATION & PURGE ENDPOINT ---

@app.delete("/system/purge-collection/{collection_name}", tags=["System Administration"])
async def purge_specific_collection(collection_name: str):
    """
    Administrative utility: Purges/resets a single specified collection 
    by delegating to the centralized ai_service.
    """
    try:
        ai_service.reset_single_collection(collection_name)
        return {
            "status": "Success", 
            "message": f"Collection '{collection_name}' successfully purged and reset."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Collection purge failed: {str(e)}")