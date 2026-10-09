import streamlit as st
import uuid
from langchain_core.messages import HumanMessage
from core.graph import agent_system

st.title("🤖 Policy Knowledgebase Chatbot")
st.caption("Interactive multi-agent claim and policy evaluation.")
st.divider()

# Ensure session-persistent thread_id for PostgreSQL checkpoints
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous conversation messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask a policy question or submit claim details..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Processing through agent pipeline..."):
            thread_config = {"configurable": {"thread_id": st.session_state.thread_id}}
            
            # Execute graph through PostgreSQL checkpointer
            initial_state = {
                "messages": [HumanMessage(content=prompt)],
                "client_id": "CLIENT_001",
                "submission_date": "2026-03-01",
                "instance_id": st.session_state.thread_id,
                "policy_category": "General",
                "policy_context": "",
                "risk_score": 0,
                "compliance_report": "",
                "final_verdict": "",
                "human_action": None,
                "human_comments": None
            }
            
            output = agent_system.invoke(initial_state, config=thread_config)
            
            # Check if workflow halted for Human-in-the-Loop review
            snapshot = agent_system.get_state(thread_config)
            if snapshot.next and "human_review" in snapshot.next:
                response_text = (
                    f"⚠️ **High Risk Flagged (Risk Score: {output.get('risk_score')})**\n\n"
                    f"This evaluation requires compliance review before a verdict can be issued. "
                    f"Task registered in **HITL Review Queue** under ID: `{st.session_state.thread_id}`."
                )
            else:
                response_text = output.get("final_verdict") or "Audit evaluation completed."

            st.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})