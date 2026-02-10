from typing import Annotated, TypedDict, Optional
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from ai_service import policy_db, claims_db, evaluations_db, llm

# Request Schema
class InvestigationRequest(BaseModel):
    client_id: str
    submission_date: str
    question: Optional[str] = None

# Shared State
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    client_id: str
    submission_date: str
    instance_id: str
    policy_category: str
    policy_context: str
    risk_score: int
    compliance_report: str
    final_verdict: str

# --- NODES ---

def initialization_node(state: AgentState):
    """
    NEW NODE: Injects the investigation start log immediately into the
    evaluation_audit_log collection.
    """
    evaluations_db.add_texts(
        texts=[f"Investigation started for client {state['client_id']}."],
        metadatas=[{
            "client_id": state["client_id"],
            "instance_id": state["instance_id"],
            "submission_date": state["submission_date"],
            "status": "In_Progress",
            "start_time": datetime.now().isoformat()
        }]
    )
    return {"messages": [SystemMessage(content=f"Audit Log Initialized for Instance: {state['instance_id']}")]}

def policy_selector_node(state: AgentState):
    """Node 1: Retrieves specific policy context."""
    query = state["messages"][0].content
    docs = policy_db.similarity_search(query, k=3)
    category = docs[0].metadata.get("document_category", "General") if docs else "General"
    return {
        "policy_category": category,
        "policy_context": "\n".join([d.page_content for d in docs]),
        "messages": [SystemMessage(content=f"Context fetched for category: {category}")]
    }

def history_investigator_node(state: AgentState):
    """Node 2: Checks past transactions for patterns."""
    past_docs = claims_db.similarity_search(
        state["submission_date"], 
        k=5, 
        filter={"client_id": state["client_id"]}
    )
    history = "\n".join([d.page_content for d in past_docs]) if past_docs else "No history."
    prompt = f"Analyze claim history for {state['client_id']}:\n{history}"
    analysis = llm.invoke(prompt)
    risk = 25 if "suspicious" in analysis.lower() else 0
    return {"risk_score": state["risk_score"] + risk, "messages": [SystemMessage(content="History analyzed.")]}

def compliance_evaluator_node(state: AgentState):
    """Node 3: Organization Specific Validation (Custom SOPs)."""
    rules = "1. 30-day submission limit. 2. VAT Invoice for >2000 AED. 3. Police Report for accidents."
    prompt = f"Apply Rules:\n{rules}\n\nClaim Context: {state['messages'][0].content}"
    report = llm.invoke(prompt)
    risk = 40 if "violation" in report.lower() else 0
    return {"compliance_report": report, "risk_score": state["risk_score"] + risk}

def orchestrator_node(state: AgentState):
    """Node 4: Final Synthesis."""
    summary = f"Risk: {state['risk_score']}\nCompliance: {state['compliance_report']}"
    verdict = llm.invoke(f"Provide final APPROVED/DENIED verdict based on:\n{summary}")
    return {"final_verdict": verdict}

def evaluation_archiver_node(state: AgentState):
    """
    Node 5: Permanent Storage of FINAL result in evaluation_audit_log.
    This effectively updates or appends the final verdict to the audit trail.
    """
    evaluations_db.add_texts(
        texts=[f"Verdict: {state['final_verdict']}\nReport: {state['compliance_report']}"],
        metadatas=[{
            "client_id": state["client_id"],
            "instance_id": state["instance_id"],
            "submission_date": state["submission_date"],
            "status": "Completed",
            "risk_score": state["risk_score"],
            "completion_time": datetime.now().isoformat()
        }]
    )
    return {"messages": [SystemMessage(content="Final result archived to Audit Log.")]}

# --- GRAPH ASSEMBLY ---
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("initializer", initialization_node)
workflow.add_node("selector", policy_selector_node)
workflow.add_node("investigator", history_investigator_node)
workflow.add_node("compliance", compliance_evaluator_node)
workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("archiver", evaluation_archiver_node)

# Set Flow
workflow.set_entry_point("initializer") # New Start Point
workflow.add_edge("initializer", "selector")
workflow.add_edge("selector", "investigator")
workflow.add_edge("investigator", "compliance")
workflow.add_edge("compliance", "orchestrator")
workflow.add_edge("orchestrator", "archiver")
workflow.add_edge("archiver", END)

agent_system = workflow.compile()