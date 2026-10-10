from typing import List
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from providers.ai_service import reasoning_llm
from providers.logging import audit_step

class PolicyViolation(BaseModel):
    clause_reference: str = Field(description="Policy clause or exclusion identifier (e.g. Clause 4.2 - Police Report Requirement)")
    violation_nature: str = Field(description="Brief description of the breached condition")
    severity_penalty: int = Field(ge=0, le=50, description="Penalty points for this specific breach (0 to 50)")
    evidence: str = Field(description="Direct snippet from claim narrative or policy")

class StructuredComplianceAudit(BaseModel):
    is_compliant: bool = Field(description="True if claim complies with all terms; False if violations exist")
    assigned_risk_score: int = Field(ge=0, le=100, description="Calculated compliance risk score (0 to 100)")
    detected_violations: List[PolicyViolation] = Field(default_factory=list, description="Identified violations")
    adjudication_summary: str = Field(description="Concise rationale for the adjuster")

@audit_step("Compliance Evaluator")
def compliance_evaluator_node(state: dict) -> dict:
    claim_narrative = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage) or (isinstance(msg, dict) and msg.get("role") == "user"):
            claim_narrative = getattr(msg, "content", msg.get("content", ""))
            break

    if not claim_narrative and state.get("messages"):
        claim_narrative = str(state["messages"][-1].content)

    policy_context = state.get("policy_context", "Standard terms and conditions apply.")
    historical_risk = state.get("risk_score", 0)

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """You are a Senior Insurance Compliance Auditor.
Audit the submitted claim against the retrieved policy clauses.

Rules:
1. Verify mandatory documentation (e.g., official police reports for motor collisions, original receipts).
2. Check for exclusions (commercial use, unlisted drivers, territorial limits).
3. If no conditions are violated, set is_compliant=true, detected_violations=[], and assigned_risk_score=0.
4. If violations exist, specify each breach with a realistic severity penalty (10-50 pts).
5. Ground all reasoning strictly in the provided policy and claim details."""
        ),
        (
            "human",
            """Retrieved Policy Context:
{policy_context}

Claim Narrative:
{claim_narrative}

Perform the structured compliance audit:"""
        )
    ])

    try:
        evaluator_chain = prompt | reasoning_llm.with_structured_output(StructuredComplianceAudit)
        audit_result: StructuredComplianceAudit = evaluator_chain.invoke({
            "policy_context": policy_context,
            "claim_narrative": claim_narrative
        })

        total_risk = min(100, historical_risk + audit_result.assigned_risk_score)

        if audit_result.detected_violations:
            violations_text = "\n".join([
                f"• [{v.clause_reference}] {v.violation_nature} (+{v.severity_penalty} pts) — Evidence: \"{v.evidence}\""
                for v in audit_result.detected_violations
            ])
        else:
            violations_text = "None. All evaluated policy terms satisfied."

        formatted_report = (
            f"=== COMPLIANCE EVALUATION REPORT ===\n"
            f"Status: {'COMPLIANT' if audit_result.is_compliant else 'NON-COMPLIANT'}\n"
            f"Evaluated Risk: {total_risk}/100 (History: {historical_risk} | Compliance: {audit_result.assigned_risk_score})\n\n"
            f"Detected Violations:\n{violations_text}\n\n"
            f"Adjudication Summary:\n{audit_result.adjudication_summary}"
        )

        return {
            "risk_score": total_risk,
            "compliance_report": formatted_report,
            "messages": [SystemMessage(content=f"Compliance evaluation complete. Risk: {total_risk}")]
        }

    except Exception as e:
        fallback_report = f"Compliance evaluation fallback due to parsing error: {str(e)}"
        return {
            "risk_score": max(historical_risk, 30),
            "compliance_report": fallback_report,
            "messages": [SystemMessage(content="Compliance evaluation fallback applied.")]
        }