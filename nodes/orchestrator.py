from providers.prompts import PromptRegistry
from providers.logging import audit_step
from ai_service import llm

@audit_step("orchestrator")
def orchestrator_node(state):
    """
    Node 4: Final Synthesis.
    Consolidates risk scores and compliance reports into a final verdict.
    """
    # Retrieve the orchestrator chain
    chain = PromptRegistry.get_chain("orchestrator", llm)
    
    # Execute synthesis based on accumulated state data
    result = chain.invoke({
        "risk_score": state["risk_score"],
        "report": state["compliance_report"],
        
    })
    
    return {"final_verdict": result.content,"messages": []}