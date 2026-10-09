from typing import Dict, Any
from langchain_core.messages import SystemMessage
from providers.prompts import PromptRegistry
from providers.logging import audit_step
from providers.ai_service import reasoning_llm

@audit_step("orchestrator")
def orchestrator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Final Synthesis.
    Consolidates risk scores and compliance reports into a final verdict.
    """
    chain = PromptRegistry.get_chain("orchestrator", reasoning_llm)
    
    result = chain.invoke({
        "risk_score": state.get("risk_score", 0),
        "report": state.get("compliance_report", "No compliance notes.")
    })
    
    verdict_text = result.content if hasattr(result, "content") else str(result)
    
    return {
        "final_verdict": verdict_text,
        "messages": [SystemMessage(content="Final verdict synthesized.")]
    }