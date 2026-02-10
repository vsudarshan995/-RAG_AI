import uuid
import shutil
import asyncio
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from langchain_core.messages import HumanMessage

# --- 1. PRODUCT QUALITY MODULAR IMPORTS ---
# Dynamically sourcing paths and services from the new providers and core modules
from providers.ai_service import router as ai_router, evaluations_db, client, ROOT_DIR, instance_log
from core.graph import agent_system, InvestigationRequest  # The compiled LangGraph in the core folder

# --- 2. APP INITIALIZATION ---
app = FastAPI(title="Insurance Multi-Agent RAG API")
app.include_router(ai_router)

# Define Storage paths relative to the project root to ensure portability
BASE_DIR = ROOT_DIR / "storage"
BASE_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/")
def read_root():
    return {
        "status": "System Online", 
        "docs_url": "/docs",
        "root_directory": str(ROOT_DIR)
    }

# --- 3. ASYNCHRONOUS MULTI-AGENT ENDPOINTS ---

@app.post("/ask/investigate/async", tags=["Multi-Agent Intelligence"])
async def start_async_investigation(request: InvestigationRequest, background_tasks: BackgroundTasks):
    """
    Triggers an asynchronous investigation instance. 
    Audit logs are viewable via the instance_id in the evaluation_audit_log.
    """
    instance_id = str(uuid.uuid4())
    
    # Trigger background task for the LangGraph workflow
    background_tasks.add_task(run_agent_background_task, instance_id, request)

    return {
        "instance_id": instance_id,
        "status": "Triggered",
        "verification_url": f"/preview/flow/{instance_id}",
        "message": "Investigation started. Monitor progress via the instance ID."
    }

async def run_agent_background_task(instance_id: str, request: InvestigationRequest):
    """Executes the graph with specific error handling for AsyncIO cancellations."""
    try:
        user_input = request.question or f"Audit for {request.submission_date}"
        
        # Ensure the thread_id matches the instance_id for LangGraph tracking
        config_graph = {"configurable": {"thread_id": instance_id}}
        
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "client_id": request.client_id,
            "submission_date": request.submission_date,
            "instance_id": instance_id,
            "risk_score": 0,
            "policy_category": "Pending", # Added
            "policy_context": "",          # Added
            "compliance_report": "", # Initialize empty strings to avoid None errors
            "final_verdict": ""
        }
        
        # Use astream to keep the event loop active and track progress
        async for event in agent_system.astream(initial_state, config=config_graph):
             # This loop helps prevent the 'CancelledError' by keeping the task busy
             pass
        
    except asyncio.CancelledError:
        # Graceful handling if the server reloads
        evaluations_db.add_texts(
            texts=["Task was cancelled due to server shutdown or reload."],
            metadatas=[{"instance_id": instance_id, "status": "CANCELLED"}]
        )
    except Exception as e:
        # Mark the SINGLE record as FAILED in the instance log
        status = "CANCELLED" if isinstance(e, asyncio.CancelledError) else "FAILED"
        
        instance_log.add_texts(
            texts=[f"Investigation terminated: {str(e)}"],
            metadatas=[{
                "instance_id": instance_id,
                "client_id": request.client_id,
                "status": status, # Records Failure/Cancellation
                "error_details": str(e),
                "completion_time": datetime.now().isoformat()
            }],
            ids=[instance_id] # Same ID ensures we update the existing record
        )
        evaluations_db.add_texts(
            texts=[f"Critical Graph Failure: {str(e)}"], 
            metadatas=[{"instance_id": instance_id, "status": "ERROR"}]
        )

# --- 4. STORAGE ENDPOINTS ---

@app.post("/upload/policy", tags=["Storage Management"])
async def upload_policy(category: str, file: UploadFile = File(...)):
    category = category.strip().capitalize()
    if not category: 
        raise HTTPException(status_code=400, detail="Category is mandatory.")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    target_folder = BASE_DIR / "policies" / category / timestamp
    target_folder.mkdir(parents=True, exist_ok=True)
    
    file_path = target_folder / file.filename
    with open(file_path, "wb") as buffer: 
        buffer.write(await file.read())
        
    return {"message": "Policy uploaded", "category": category, "path": str(file_path)}

@app.post("/upload/claim/{client_id}/{submission_type}", tags=["Storage Management"])
async def upload_claim(client_id: str, submission_type: str, file: UploadFile = File(...)):
    date_str = datetime.now().strftime("%Y-%m-%d")
    folder_name = f"{date_str}_{submission_type}"
    target_folder = BASE_DIR / "claims" / client_id / folder_name
    target_folder.mkdir(parents=True, exist_ok=True)
    
    file_path = target_folder / file.filename
    with open(file_path, "wb") as buffer: 
        buffer.write(await file.read())
        
    return {"message": "Claim submitted", "path": str(file_path)}

# --- 5. DATABASE MANAGEMENT ---

@app.delete("/clear-all", tags=["Database Management"])
async def clear_all_data():
    """Wipes all dual-collection architecture data and storage."""
    try:
        collections = ["policy_master_collection", "claims_collection", "evaluation_audit_log","instance_log"]
        for coll_name in collections:
            try: 
                client.delete_collection(name=coll_name)
            except: 
                pass
            client.create_collection(name=coll_name)
        
        if BASE_DIR.exists():
            shutil.rmtree(BASE_DIR)
            BASE_DIR.mkdir(parents=True, exist_ok=True)
            
        return {"message": "All database collections and physical storage cleared."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete-client/{client_id}", tags=["Database Management"])
async def delete_client_data(client_id: str):
    """Removes all claims and audit logs associated with a specific client ID."""
    try:
        claims_col = client.get_collection(name="claims_collection")
        claims_col.delete(where={"client_id": client_id})
        
        audit_col = client.get_collection(name="evaluation_audit_log")
        audit_col.delete(where={"client_id": client_id})
        
        client_folder = BASE_DIR / "claims" / client_id
        if client_folder.exists(): 
            shutil.rmtree(client_folder)
            
        return {"message": f"Data for {client_id} removed from all records."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))