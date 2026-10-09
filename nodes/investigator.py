from typing import Dict, Any
from langchain_core.messages import SystemMessage
from providers.prompts import PromptRegistry
from providers.logging import audit_step
from providers.ai_service import claims_db, reasoning_llm

@audit_step("investigator")
def history_investigator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Historical Claim Frequency and Anomaly Analysis.
    """
    client_id = state.get("client_id", "")
    submission_date = state.get("submission_date", "")
    
    # Fetch past claim history for this client
    past_docs = claims_db.similarity_search(
        submission_date, 
        k=5, 
        filter={"client_id": client_id}
    )
    history = "\n".join([d.page_content for d in past_docs]) if past_docs else "No history."
    
    chain = PromptRegistry.get_chain("history_investigator", reasoning_llm)
    analysis = chain.invoke({
        "client_id": client_id, 
        "history": history
    })
    
    analysis_text = analysis.content if hasattr(analysis, "content") else str(analysis)
    lower_analysis = analysis_text.lower()
    
    # Prevent false positives like "not suspicious"
    is_suspicious = (
        "suspicious" in lower_analysis 
        and "not suspicious" not in lower_analysis 
        and "no suspicious" not in lower_analysis
    )
    risk = 25 if is_suspicious else 0
    
    return {
        "risk_score": state.get("risk_score", 0) + risk,
        "messages": [SystemMessage(content=f"History investigated (added risk: {risk}).")]
    }