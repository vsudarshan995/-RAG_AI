from typing import Annotated, TypedDict, Optional
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage
from pydantic import BaseModel

# Modular Imports
from providers.ai_service import policy_db, claims_db, evaluations_db,instance_log, llm
from providers.prompts import PromptRegistry
from providers.logging import audit_step

class InvestigationRequest(BaseModel):
    client_id: str
    submission_date: str
    question: Optional[str] = None

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

@audit_step("Initialization") # Triggers instance_log and evaluations_db
def initialization_node(state: AgentState):
    return {"messages": [SystemMessage(content=f"Audit process started.")]}

@audit_step("Policy Selection")
def policy_selector_node(state: AgentState):
    query = state["messages"][0].content
    docs = policy_db.similarity_search(query, k=3)
    category = docs[0].metadata.get("document_category", "General") if docs else "General"
    return {
        "policy_category": category,
        "policy_context": "\n".join([d.page_content for d in docs])
    }

@audit_step("History Investigation")
def history_investigator_node(state: AgentState):
    past_docs = claims_db.similarity_search(state["submission_date"], k=5, filter={"client_id": state["client_id"]})
    history = "\n".join([d.page_content for d in past_docs]) if past_docs else "No history."
    
    # Use the centralized Prompt Registry
    chain = PromptRegistry.get_chain("history_investigator", llm)
    analysis = chain.invoke({"client_id": state["client_id"], "history": history})
    
    risk = 25 if "suspicious" in analysis.lower() else 0
    return {"risk_score": state["risk_score"] + risk}

@audit_step("Compliance Evaluation")
def compliance_evaluator_node(state: AgentState):
    rules = "1. 30-day submission limit. 2. Police Report for accidents."
    report = llm.invoke(f"Apply Rules: {rules}\nContext: {state['messages'][0].content}")
    risk = 40 if "violation" in report.lower() else 0
    return {"compliance_report": report, "risk_score": state["risk_score"] + risk}

@audit_step("Verdict Orchestration")
def orchestrator_node(state: AgentState):
    chain = PromptRegistry.get_chain("orchestrator", llm)
    verdict = chain.invoke({"risk_score": state['risk_score'], "report": state['compliance_report']})
    return {"final_verdict": verdict}

@audit_step("Final Archiver")
def evaluation_archiver_node(state: AgentState):
    # Final permanent storage
    instance_log.add_texts(
        texts=[f"Evaluation successfully completed for {state['client_id']}"],
        metadatas=[{
            "instance_id": state["instance_id"],
            "client_id": state["client_id"],
            "status": "COMPLETED", # Final Success Status
            "risk_score": state["risk_score"],
            "completion_time": datetime.now().isoformat()
        }],
        ids=[state["instance_id"]] # Crucial: Same ID as used in initialization
    )

    evaluations_db.add_texts(
        texts=[f"Final Verdict: {state['final_verdict']}"],
        metadatas=[{
            "instance_id": state["instance_id"],
            "status": "COMPLETED",
            "risk_score": state["risk_score"]
        }],
        ids=[f"{state['instance_id']}_final"]
    )
    return {"messages": [SystemMessage(content="Final result archived.")]}

# --- ASSEMBLY ---
workflow = StateGraph(AgentState)
workflow.add_node("initializer", initialization_node)
workflow.add_node("selector", policy_selector_node)
workflow.add_node("investigator", history_investigator_node)
workflow.add_node("compliance", compliance_evaluator_node)
workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("archiver", evaluation_archiver_node)

workflow.set_entry_point("initializer")
workflow.add_edge("initializer", "selector")
workflow.add_edge("selector", "investigator")
workflow.add_edge("investigator", "compliance")
workflow.add_edge("compliance", "orchestrator")
workflow.add_edge("orchestrator", "archiver")
workflow.add_edge("archiver", END)

agent_system = workflow.compile()