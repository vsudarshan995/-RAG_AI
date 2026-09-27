import streamlit as st
import requests
from datetime import datetime

st.title("🚀 Start New Insurance Evaluation")
st.caption("Trigger an autonomous multi-agent evaluation pipeline with policy RAG and risk scoring.")
st.divider()

with st.form("evaluation_form"):
    client_id = st.text_input("Client ID", placeholder="e.g. client_123")
    submission_date = st.date_input("Claim / Submission Date", datetime.now())
    question = st.text_area("Claim Context / Audit Inquiry", placeholder="Enter specific incident details or policy verification questions...")
    
    submitted = st.form_submit_button("🚀 Run Autonomous Evaluation", use_container_width=True)
    
    if submitted:
        payload = {
            "client_id": client_id,
            "submission_date": submission_date.strftime("%Y-%m-%d"),
            "question": question
        }
        try:
            res = requests.post("http://localhost:8000/ask/investigate/async", json=payload)
            if res.status_code == 200:
                st.success("Evaluation pipeline triggered successfully! Monitor progress in the Executive Control Center.")
            else:
                st.error("Failed to connect to backend engine.")
        except Exception as e:
            st.error(f"Connection error: {e}")