from providers.prompts import PromptRegistry
from providers.logging import audit_step
from ai_service import claims_db, llm

@audit_step("investigator")
def history_investigator_node(state):
    past_docs = claims_db.similarity_search(
        state["submission_date"], 
        k=5, 
        filter={"client_id": state["client_id"]}
    )
    history = "\n".join([d.page_content for d in past_docs]) if past_docs else "No history."
    
    chain = PromptRegistry.get_chain("history_investigator", llm)
    analysis = chain.invoke({"client_id": state["client_id"], "history": history})
    
    risk = 25 if "suspicious" in analysis.content.lower() else 0
    return {"risk_score": state["risk_score"] + risk}