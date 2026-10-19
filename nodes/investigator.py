from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from providers.ai_service import reasoning_llm
from providers.logging import audit_step
from providers.prompts import history_investigator_prompt

class AnomalyFlag(BaseModel):
    indicator: str = Field(description="Anomaly pattern (e.g. Rapid repeat claim, suspicious timing)")
    risk_points: int = Field(ge=0, le=40, description="Risk penalty points for this pattern (0 to 40)")
    detail: str = Field(description="Factual evidence supporting the suspicion")

class StructuredInvestigationReport(BaseModel):
    is_suspicious: bool = Field(description="True if anomalies or red flags are detected")
    anomaly_score: int = Field(ge=0, le=50, description="Overall risk penalty from historical investigation")
    flags: List[AnomalyFlag] = Field(default_factory=list, description="Itemized anomalies detected")
    summary: str = Field(description="Summary of historical profile and anomaly findings")

@audit_step("History Investigator")
def history_investigator_node(state: dict) -> dict:
    claim_narrative = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage) or (isinstance(msg, dict) and msg.get("role") == "user"):
            claim_narrative = getattr(msg, "content", msg.get("content", ""))
            break

    if not claim_narrative and state.get("messages"):
        claim_narrative = str(state["messages"][-1].content)

    client_id = state.get("client_id", "CLIENT_UNKNOWN")
    history_context = f"Client record: {client_id}. No prior fraudulent history flagged in database."

    try:
        chain = history_investigator_prompt | reasoning_llm.with_structured_output(StructuredInvestigationReport)
        report: StructuredInvestigationReport = chain.invoke({
            "history_context": history_context,
            "current_claim": claim_narrative
        })

        return {
            "risk_score": report.anomaly_score,
            "messages": [SystemMessage(content=f"History investigation complete. Anomaly score: {report.anomaly_score}")]
        }
    except Exception as e:
        return {
            "risk_score": 0,
            "messages": [SystemMessage(content=f"History investigation fallback: {str(e)}")]
        }