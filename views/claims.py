import streamlit as st
import pandas as pd
import chromadb
import requests
from datetime import datetime
from config import config

st.title("🛡️ Claims Management & Adjudication")
st.caption("Submit new insurance claims, verify client-policy associations, and monitor multi-agent evaluation statuses.")
st.divider()

client = chromadb.PersistentClient(path=config.DB_PATH)

def fetch_clients():
    try:
        col = client.get_or_create_collection(name=config.COLLECTIONS["clients"])
        res = col.get(include=["metadatas"])
        return [m["client_id"] for m in res["metadatas"]] if res and res.get("metadatas") else []
    except:
        return []

def fetch_client_policies():
    try:
        col = client.get_or_create_collection(name=config.COLLECTIONS["client_policies"])
        res = col.get(include=["metadatas"])
        return pd.DataFrame(res["metadatas"]) if res and res.get("metadatas") else pd.DataFrame()
    except:
        return pd.DataFrame()

def fetch_claims():
    try:
        col = client.get_or_create_collection(name=config.COLLECTIONS["claims"])
        res = col.get(include=["metadatas"])
        return pd.DataFrame(res["metadatas"]) if res and res.get("metadatas") else pd.DataFrame()
    except:
        return pd.DataFrame()

client_ids = fetch_clients()
df_policies = fetch_client_policies()
df_claims = fetch_claims()

tab_claims_list, tab_submit_claim = st.tabs(["📚 Submitted Claims", "⚡ Submit New Claim"])

# --- TAB 1: SUBMITTED CLAIMS LIST ---
with tab_claims_list:
    st.subheader("Claims Audit Trail")
    
    if not df_claims.empty:
        # Search & Filter
        col_s1, col_s2 = st.columns(2)
        search_id = col_s1.text_input("🔍 Search Claim ID", placeholder="Type Claim ID...")
        
        filtered_df = df_claims
        if search_id:
            filtered_df = filtered_df[filtered_df['claim_id'].str.contains(search_id, case=False, na=False)]
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        for idx, row in filtered_df.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 2, 1.5, 1.5])
                
                c1.markdown(f"**Claim ID:** `{row.get('claim_id', 'N/A')}`")
                c1.caption(f"Client ID: {row.get('client_id', 'N/A')} | Policy: {row.get('policy_number', 'N/A')}")
                
                c2.markdown(f"**Category & Amount:**")
                c2.write(f"🏷️ {row.get('claim_category', 'General')} | 💵 ${row.get('claim_amount', 0):,.2f}")
                
                c3.markdown(f"**Incident Date:**")
                c3.caption(row.get('incident_date', 'N/A'))
                
                status = row.get('status', 'PENDING_EVALUATION')
                c4.markdown(f"**Status:**")
                if "APPROVED" in status:
                    c4.success(status)
                elif "REJECTED" in status:
                    c4.error(status)
                else:
                    c4.warning(status)
    else:
        st.info("No claims submitted in the system yet. Use the 'Submit New Claim' tab to file a claim.")

# --- TAB 2: SUBMIT NEW CLAIM ---
with tab_submit_claim:
    st.subheader("File New Insurance Claim")
    st.caption("Claims must be linked to a verified client and an active policy subscription.")

    if not client_ids or df_policies.empty:
        st.warning("⚠️ Prerequisites missing: Please ensure at least one client and one active client policy are registered before submitting a claim.")
    else:
        with st.form("submit_claim_form", clear_on_submit=True):
            claim_id = st.text_input("Claim ID", value=f"CLM-{int(datetime.now().timestamp())}")
            
            # Filter active policies
            active_policies_df = df_policies[df_policies["status"] == "Active"] if "status" in df_policies.columns else df_policies
            policy_choices = active_policies_df["policy_number"].tolist() if not active_policies_df.empty else []
            
            if not policy_choices:
                st.error("No active policies found. Please activate a client policy first.")
            
            selected_policy = st.selectbox("Select Active Policy Number", policy_choices)
            
            # Auto-detect client ID from selected policy
            matched_client_id = ""
            matched_category = "General"
            if selected_policy and not active_policies_df.empty:
                match_row = active_policies_df[active_policies_df["policy_number"] == selected_policy]
                if not match_row.empty:
                    matched_client_id = match_row.iloc[0].get("client_id", "")
                    matched_category = match_row.iloc[0].get("policy_type", "General")

            client_id = st.text_input("Associated Client ID (Auto-linked)", value=matched_client_id, disabled=True)
            claim_category = st.text_input("Claim Category (Inherited from Policy)", value=matched_category, disabled=True)
            
            col_c1, col_c2 = st.columns(2)
            incident_date = col_c1.date_input("Incident Date", datetime.now())
            claim_amount = col_c2.number_input("Claim Amount ($)", min_value=10.0, value=1500.0, step=100.0)
            
            submit_btn = st.form_submit_button("🚀 Submit Claim for Evaluation", use_container_width=True)
            
            if submit_btn:
                if claim_id.strip() and selected_policy:
                    payload = {
                        "claim_id": claim_id.strip(),
                        "client_id": matched_client_id,
                        "policy_number": selected_policy,
                        "incident_date": str(incident_date),
                        "claim_amount": claim_amount,
                        "claim_category": matched_category
                    }
                    try:
                        res = requests.post("http://localhost:8000/claims/submit", json=payload)
                        if res.status_code == 200:
                            data = res.json()
                            st.success(f"Claim `{claim_id}` successfully submitted! Instance ID: `{data.get('instance_id')}`")
                            st.info("The multi-agent evaluation pipeline has been triggered in the background. Check the 'Human Review Queue' or 'Executive Control Center' to monitor verdicts.")
                            time.sleep(2)
                            st.rerun()
                        else:
                            err_detail = res.json().get("detail", "Unknown backend error")
                            st.error(f"Submission failed: {err_detail}")
                    except Exception as ex:
                        st.error(f"Connection error to backend API: {ex}")
                else:
                    st.warning("Please provide a valid Claim ID and select an active policy.")