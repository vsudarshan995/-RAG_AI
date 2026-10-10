from typing import Annotated, TypedDict, Optional
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from langgraph.checkpoint.postgres import PostgresSaver

from config import config
from providers.ai_service import policy_vr_db
from providers.logging import audit_step
from providers.db_service import pool, db_service

from nodes.compliance import compliance_evaluator_node
from nodes.investigator import history_investigator_node
from nodes.orchestrator import orchestrator_node

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
    human_action: Optional[str]
    human_comments: Optional[str]

@audit_step("Initialization")
def initialization_node(state: AgentState):
    return {"messages": [SystemMessage(content=f"Audit Log Initialized for Instance: {state['instance_id']}")]}

@audit_step("Policy Selection")
def policy_selector_node(state: AgentState):
    query = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage) or (isinstance(msg, dict) and msg.get("role") == "user"):
            query = getattr(msg, "content", msg.get("content", ""))
            break

    if not query and state.get("messages"):
        query = str(state["messages"][-1].content)

    docs = policy_vr_db.similarity_search(query, k=3)
    category = docs[0].metadata.get("document_category", "General") if docs else "General"
    return {
        "policy_category": category,
        "policy_context": "\n".join([d.page_content for d in docs]),
        "messages": [SystemMessage(content=f"Context fetched for category: {category}")]
    }

def check_for_anomalies(state: AgentState) -> str:
    risk_score = state.get("risk_score", 0)
    instance_id = state.get("instance_id")

    if risk_score > 65:
        db_service.create_review_task(
            instance_id=instance_id,
            client_id=state.get("client_id", "CLIENT_UNKNOWN"),
            risk_score=risk_score,
            compliance_report=state.get("compliance_report", "")
        )
        return "human_review"
    return "orchestrator"

@audit_step("Human Review Interception")
def human_review_node(state: AgentState):
    action = state.get("human_action", "pending")
    comments = state.get("human_comments", "")
    verdict = f"Claim manually adjudicated by compliance officer. Action: {action.upper()}. Notes: {comments}"

    return {
        "final_verdict": verdict,
        "compliance_report": state.get("compliance_report", "") + f"\n[HITL Decision: {action} | Rationale: {comments}]",
        "messages": [SystemMessage(content=f"Human review applied: {action}")]
    }

@audit_step("Final Archiver")
def evaluation_archiver_node(state: AgentState):
    db_service.archive_evaluation(
        instance_id=state["instance_id"],
        client_id=state.get("client_id", "CLIENT_UNKNOWN"),
        risk_score=state.get("risk_score", 0),
        final_verdict=state.get("final_verdict", "")
    )
    return {"messages": [SystemMessage(content="Evaluation archived to PostgreSQL audit log.")]}

# --- WORKFLOW COMPILATION ---
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

checkpointer = PostgresSaver(pool)
checkpointer.setup()

agent_system = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["human_review"]
)