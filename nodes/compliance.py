from providers.prompts import PromptRegistry
from providers.logging import audit_step
from ai_service import llm

@audit_step("compliance")
def compliance_evaluator_node(state):
    """
    Node 3: Organization Specific Validation (Custom SOPs).
    Uses a modular prompt and automated logging.
    """
    # In a production environment, these rules could be fetched from 
    # the policy_db or config
    rules = (
        "1. 30-day submission limit from incident date. "
        "2. Original VAT Invoice required for claims > 2000 AED. "
        "3. Police Report mandatory for accident-related claims."
    )
    
    # Retrieve the compliance chain from the registry
    chain = PromptRegistry.get_chain("compliance_evaluator", llm)
    
    # Execute the LLM logic
    report = chain.invoke({
        "rules": rules,
        "content": state["messages"][0].content
    })
    
    # Determine risk based on LLM analysis
    # Modular approach allows for more complex risk logic here later
    risk = 40 if "violation" in report.content.lower() else 0
    
    return {
        "compliance_report": report.content, 
        "risk_score": state["risk_score"] + risk
    }