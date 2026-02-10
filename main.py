import os
import uuid
import shutil
import json
import chromadb
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from langchain_core.messages import HumanMessage

# 1. Connect the AI service logic
from ai_service import router as ai_router

# 2. Connect the Multi-Agent Orchestrator components
from agent_orchestrator import agent_system, InvestigationRequest

# 3. The main app object
app = FastAPI(title="Insurance Multi-Agent RAG API")

# 4. Include the AI Router (Basic /ask endpoints)
app.include_router(ai_router)

# 5. Define ABSOLUTE storage paths
BASE_DIR = Path(r"D:\pY\InsuranceRAG\storage")
CHROMA_PATH = r"D:\pY\InsuranceRAG\local_db"
BASE_DIR.mkdir(parents=True, exist_ok=True)

# 6. Initialize Chroma Client and In-Memory Instance Tracker
client = chromadb.PersistentClient(path=CHROMA_PATH)
instance_tracker = {} # Temporary store for live progress visualization

@app.get("/")
def read_root():
    return {"status": "System Online", "docs_url": "/docs"}

# --- ASYNCHRONOUS MULTI-AGENT ENDPOINTS ---

@app.post("/ask/investigate/async", tags=["Multi-Agent Intelligence"])
async def start_async_investigation(request: InvestigationRequest, background_tasks: BackgroundTasks):
    """
    Triggers an asynchronous investigation instance. 
    Returns an Instance ID and a URL to verify the visual flow and results.
    """
    instance_id = str(uuid.uuid4())
    verify_url = f"http://127.0.0.1:8000/verify/flow/{instance_id}"
    
    # Initialize the tracker for this instance
    instance_tracker[instance_id] = {
        "status": "Running",
        "client_id": request.client_id,
        "submission_date": request.submission_date,
        "start_time": datetime.now().isoformat(),
        "steps_completed": []
    }

    # Add the agent execution to background tasks
    background_tasks.add_task(run_agent_background_task, instance_id, request)

    return {
        "instance_id": instance_id,
        "verification_url": verify_url,
        "message": "Investigation instance triggered successfully."
    }

async def run_agent_background_task(instance_id: str, request: InvestigationRequest):
    """Background worker to execute the LangGraph workflow."""
    try:
        user_input = request.question if request.question else f"Perform full audit for submission on {request.submission_date}"
        
        # Thread-specific configuration for LangGraph
        config = {"configurable": {"thread_id": instance_id}}
        
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "client_id": request.client_id,
            "submission_date": request.submission_date,
            "instance_id": instance_id,
            "risk_score": 0
        }
        
        # Stream the graph execution to track progress per node
        async for event in agent_system.astream(initial_state, config=config):
            for node_name, _ in event.items():
                instance_tracker[instance_id]["steps_completed"].append(node_name)
        
        instance_tracker[instance_id]["status"] = "Completed"
    except Exception as e:
        instance_tracker[instance_id]["status"] = f"Failed: {str(e)}"

@app.get("/preview/flow/{instance_id}", response_class=HTMLResponse, tags=["Multi-Agent Intelligence"])
async def preview_flow_visual(instance_id: str):
    
    # 1. Query the permanent collection first
    try:
        audit_col = client.get_collection("evaluation_audit_log")
        db_records = audit_col.get(where={"instance_id": instance_id})
    except Exception:
        # If the collection doesn't exist yet, it's definitely a 404
        raise HTTPException(status_code=404, detail="Audit collection not initialized.")

    # 2. Hard 404 ONLY if not found in the Database
    if not db_records or not db_records['documents']:
        raise HTTPException(status_code=404, detail=f"No record found for Instance ID: {instance_id}")

    # --- DATA PROCESSING ---
    # Combine all related documents for this instance into a timeline view
    full_history = []
    latest_metadata = {}
    
    for doc, meta in zip(db_records['documents'], db_records['metadatas']):
        full_history.append({
            "content": doc,
            "status": meta.get("status", "N/A"),
            "timestamp": meta.get("completion_time") or meta.get("start_time", "N/A")
        })
        # Keep track of the most recent metadata for top-level display
        latest_metadata = meta 

    # Determine current status for the refresh logic
    status = "Historical"
    completed_steps = []
    if instance_id in instance_tracker:
        status = instance_tracker[instance_id]["status"]
        completed_steps = instance_tracker[instance_id]["steps_completed"]
    else:
        status = latest_metadata.get("status", "Completed")

    mermaid_chart = agent_system.get_graph().draw_mermaid()

    # --- HTML RENDERING ---
    history_html = "".join([
        f"<div class='log-entry'><strong>[{item['status']}]</strong> ({item['timestamp']})<br>{item['content']}</div>"
        for item in full_history
    ])

    return HTMLResponse(content=f"""
    <html>
    <head>
        <title>Investigation Detail - {instance_id}</title>
        <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
        <script>
            mermaid.initialize({{ startOnLoad: true, theme: 'forest' }});
            if ("{status}" === "Running") {{ setTimeout(() => {{ location.reload(); }}, 3000); }}
        </script>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; padding: 30px; background: #f8f9fa; }}
            .card {{ background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }}
            .status-tag {{ padding: 5px 12px; border-radius: 15px; font-weight: bold; font-size: 0.8em; }}
            .Running {{ background: #fff3cd; color: #856404; }}
            .Completed {{ background: #d4edda; color: #155724; }}
            .log-entry {{ background: #f1f3f5; padding: 10px; margin-bottom: 10px; border-left: 4px solid #343a40; font-family: monospace; font-size: 0.9em; }}
            .mermaid {{ display: flex; justify-content: center; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div style="max-width: 1000px; margin: auto;">
            <div class="card">
                <h1>Investigation ViewFlow</h1>
                <p><strong>Instance:</strong> {instance_id} <span class="status-tag {status}">{status}</span></p>
                <p><strong>Client:</strong> {latest_metadata.get('client_id', 'Unknown')}</p>
                <div class="mermaid">{mermaid_chart}</div>
            </div>

            <div class="card">
                <h2>Full Audit History</h2>
                <p>Showing all records found in <code>evaluation_audit_log</code>:</p>
                {history_html}
            </div>
        </div>
    </body>
    </html>
    """)

# --- STORAGE ENDPOINTS ---

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

# --- DATABASE MANAGEMENT ---

@app.delete("/clear-all", tags=["Database Management"])
async def clear_all_data():
    try:
        # Clear all three dual database collections
        for name in ["policy_master_collection", "claims_collection", "evaluation_audit_log"]:
            try:
                client.delete_collection(name=name)
            except:
                pass
            client.create_collection(name=name)
        
        if BASE_DIR.exists():
            shutil.rmtree(BASE_DIR)
            BASE_DIR.mkdir(parents=True, exist_ok=True)
            
        return {"message": "All database collections and physical storage cleared."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete-client/{client_id}", tags=["Database Management"])
async def delete_client_data(client_id: str):
    try:
        claims_col = client.get_collection(name="claims_collection")
        claims_col.delete(where={"client_id": client_id})
        
        # Also clean audit logs for this client
        audit_col = client.get_collection(name="evaluation_audit_log")
        audit_col.delete(where={"client_id": client_id})
        
        client_folder = BASE_DIR / "claims" / client_id
        if client_folder.exists():
            shutil.rmtree(client_folder)
            
        return {"message": f"Data for {client_id} removed from all records."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))