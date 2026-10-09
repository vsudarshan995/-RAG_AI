from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from providers.prompts import PromptRegistry
from providers.logging import audit_step
from providers.ai_service import reasoning_llm

@audit_step("compliance")
def compliance_evaluator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Organization Specific Validation (Custom SOPs).
    Uses PromptRegistry and evaluates standard compliance rules.
    """
    rules = (
        "1. 30-day submission limit from incident date. "
        "2. Original VAT Invoice required for claims > 2000 AED. "
        "3. Police Report mandatory for accident-related claims."
    )
    
    # Locate the claim description from the latest human message or fallback to index 0
    claim_content = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage) or (isinstance(msg, dict) and msg.get("role") == "user"):
            claim_content = getattr(msg, "content", msg.get("content", ""))
            break
    if not claim_content and state.get("messages"):
        first_msg = state["messages"][0]
        claim_content = getattr(first_msg, "content", str(first_msg))

    chain = PromptRegistry.get_chain("compliance_evaluator", reasoning_llm)
    report = chain.invoke({
        "rules": rules,
        "content": claim_content
    })
    
    report_text = report.content if hasattr(report, "content") else str(report)
    
    # Check for negative affirmation phrases to prevent false positives
    lower_report = report_text.lower()
    has_violation = (
        "violation" in lower_report 
        and "no violation" not in lower_report 
        and "without violation" not in lower_report
    )
    risk = 40 if has_violation else 0
    
    return {
        "compliance_report": report_text, 
        "risk_score": state.get("risk_score", 0) + risk,
        "messages": [SystemMessage(content=f"Compliance check evaluated (added risk: {risk}).")]
    }