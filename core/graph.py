from typing import Annotated, TypedDict, Optional, Dict, Any
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from langgraph.checkpoint.memory import MemorySaver

# Modular Imports
from providers.ai_service import policy_db, claims_db, evaluations_db, instance_log, human_review_db, reasoning_llm
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
    # Human-in-the-Loop Fields
    human_action: Optional[str]   # 'approve' or 'reject'
    human_comments: Optional[str] # Reviewer notes

# --- NODES ---

@audit_step("Initialization")
def initialization_node(state: AgentState):
    return {"messages": [SystemMessage(content=f"Audit Log Initialized for Instance: {state['instance_id']}")]}

@audit_step("Policy Selection")
def policy_selector_node(state: AgentState):
    query = state["messages"][0].content
    docs = policy_db.similarity_search(query, k=3)
    category = docs[0].metadata.get("document_category", "General") if docs else "General"
    return {
        "policy_category": category,
        "policy_context": "\n".join([d.page_content for d in docs]),
        "messages": [SystemMessage(content=f"Context fetched for category: {category}")]
    }

@audit_step("History Investigation")
def history_investigator_node(state: AgentState):
    past_docs = claims_db.similarity_search(state["submission_date"], k=5, filter={"client_id": state["client_id"]})
    history = "\n".join([d.page_content for d in past_docs]) if past_docs else "No history."
    
    chain = PromptRegistry.get_chain("history_investigator", reasoning_llm)
    analysis = chain.invoke({"client_id": state["client_id"], "history": history})
    
    risk = 25 if "suspicious" in analysis.lower() else 0
    return {"risk_score": state["risk_score"] + risk, "messages": [SystemMessage(content="History analyzed.")]}

@audit_step("Compliance Evaluation")
def compliance_evaluator_node(state: AgentState):
    rules = "1. 30-day submission limit. 2. Police Report for accidents."
    response = reasoning_llm.invoke(f"Apply Rules: {rules}\nContext: {state['messages'][0].content}")
    report_content = response.content if hasattr(response, 'content') else str(response)
    
    risk = 40 if "violation" in report_content.lower() else 0
    return {
        "compliance_report": report_content, 
        "risk_score": state["risk_score"] + risk,
        "messages": [SystemMessage(content="Compliance evaluated.")]
    }

# --- HUMAN-IN-THE-LOOP & ROUTING NODES ---

def check_for_anomalies(state: AgentState) -> str:
    """
    Evaluates risk score. If > 65, register task in database and route to human review.
    """
    risk_score = state.get("risk_score", 0)
    instance_id = state["instance_id"]
    
    if risk_score > 65:
        try:
            human_review_db.add_texts(
                texts=[f"Pending review for client {state['client_id']} due to high risk score: {risk_score}"],
                metadatas=[{
                    "instance_id": instance_id,
                    "client_id": state["client_id"],
                    "status": "PENDING_REVIEW",
                    "risk_score": risk_score,
                    "compliance_report": state.get("compliance_report", ""),
                    "created_at": datetime.now().isoformat()
                }],
                ids=[instance_id]
            )
        except Exception:
            pass
        return "human_review"
    return "orchestrator"

@audit_step("Human Review Interception")
def human_review_node(state: AgentState):
    """
    Executes after the graph resumes from a breakpoint via human command.
    """
    action = state.get("human_action", "pending")
    comments = state.get("human_comments", "")
    
    verdict = f"Claim reviewed by compliance officer. Action: {action.upper()}. Notes: {comments}"
    
    return {
        "final_verdict": verdict,
        "compliance_report": state.get("compliance_report", "") + f"\n[HITL Audit] Human Decision: {action} | Comments: {comments}",
        "messages": [SystemMessage(content=f"Human review completed with action: {action}")]
    }

@audit_step("Verdict Orchestration")
def orchestrator_node(state: AgentState):
    chain = PromptRegistry.get_chain("orchestrator", reasoning_llm)
    res = chain.invoke({
        "risk_score": state['risk_score'], 
        "report": state['compliance_report']
    })
    verdict_text = res.content if hasattr(res, 'content') else str(res)
    return {"final_verdict": verdict_text, "messages": [SystemMessage(content="Verdict orchestrated.")]}

@audit_step("Final Archiver")
def evaluation_archiver_node(state: AgentState):
    instance_log.add_texts(
        texts=[f"Evaluation successfully completed for {state['client_id']}"],
        metadatas=[{
            "instance_id": state["instance_id"],
            "client_id": state["client_id"],
            "status": "COMPLETED",
            "risk_score": state["risk_score"],
            "completion_time": datetime.now().isoformat()
        }],
        ids=[state["instance_id"]]
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
    return {"messages": [SystemMessage(content="Final result archived to Audit Log.")]}

# --- ASSEMBLY ---
workflow = StateGraph(AgentState)
workflow.add_node("initializer", initialization_node)
workflow.add_node("selector", policy_selector_node)
workflow.add_node("investigator", history_investigator_node)
workflow.add_node("compliance", compliance_evaluator_node)
workflow.add_node("human_review", human_review_node)
workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("archiver", evaluation_archiver_node)

workflow.set_entry_point("initializer")
workflow.add_edge("initializer", "selector")
workflow.add_edge("selector", "investigator")
workflow.add_edge("investigator", "compliance")

workflow.add_conditional_edges(
    "compliance",
    check_for_anomalies,
    {
        "human_review": "human_review",
        "orchestrator": "orchestrator"
    }
)

workflow.add_edge("human_review", "archiver")
workflow.add_edge("orchestrator", "archiver")
workflow.add_edge("archiver", END)

memory = MemorySaver()
agent_system = workflow.compile(
    checkpointer=memory,
    interrupt_before=["human_review"]
)