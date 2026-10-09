import uuid
import streamlit as st
from langchain_core.messages import HumanMessage
from core.graph import agent_system
from providers.db_service import db_service

st.title("🚀 Start New Claim Evaluation")
st.caption("Submit a claim scenario to the multi-agent compliance pipeline.")
st.divider()

with st.form("eval_form"):
    col1, col2 = st.columns(2)
    with col1:
        client_id = st.text_input("Client ID", value="CLIENT_1001")
        submission_date = st.date_input("Incident Date")
    with col2:
        policy_category = st.selectbox("Policy Category", ["Motor", "Health", "Commercial", "General"])
        claim_amount = st.number_input("Claim Amount (AED)", min_value=0.0, value=3500.0, step=500.0)

    claim_narrative = st.text_area(
        "Incident Description & Damage Summary",
        value="Vehicle collision occurred on highway. Driver claims damage to front bumper and radiator without a formal police report.",
        height=140
    )

    submit_button = st.form_submit_button("Initiate Multi-Agent Audit", type="primary")

if submit_button:
    instance_id = f"eval_{uuid.uuid4().hex[:8]}"
    thread_config = {"configurable": {"thread_id": instance_id}}

    initial_state = {
        "messages": [HumanMessage(content=claim_narrative)],
        "client_id": client_id,
        "submission_date": str(submission_date),
        "instance_id": instance_id,
        "policy_category": policy_category,
        "policy_context": "",
        "risk_score": 0,
        "compliance_report": "",
        "final_verdict": "",
        "human_action": None,
        "human_comments": None
    }

    with st.spinner("Executing agent workflow (Router ➔ Investigator ➔ Compliance)..."):
        try:
            result = agent_system.invoke(initial_state, config=thread_config)
            snapshot = agent_system.get_state(thread_config)

            st.success(f"Audit initiated for Instance: `{instance_id}`")
            
            # Check if workflow halted for human review
            if snapshot.next and "human_review" in snapshot.next:
                st.warning("⚠️ Escalated to Human-in-the-Loop Risk Queue (Risk score exceeded threshold).")
                st.info("Head to the **Human Review Queue** page to review context and make a decision.")
            else:
                st.markdown("### Final Audit Verdict")
                st.write(result.get("final_verdict", "Evaluation finalized."))

            with st.expander("Detailed Evaluation Report"):
                st.write(f"**Risk Score:** {result.get('risk_score', 0)}/100")
                st.text_area("Compliance Report", value=result.get("compliance_report", ""), height=150, disabled=True)

        except Exception as ex:
            st.error(f"Pipeline error: {str(ex)}")