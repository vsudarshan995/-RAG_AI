import streamlit as st
import pandas as pd
import chromadb
from datetime import datetime
from config import config

st.title("📋 Client Policy Subscriptions")
st.caption("Manage active policy assignments, coverage limits, and validity dates for registered clients.")
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

client_ids = fetch_clients()
df_policies = fetch_client_policies()

tab_list, tab_assign = st.tabs(["📚 Assigned Policies", "➕ Assign New Policy"])

with tab_list:
    if not df_policies.empty:
        st.dataframe(df_policies, use_container_width=True)
    else:
        st.info("No client policies assigned yet.")

with tab_assign:
    if not client_ids:
        st.warning("Please register at least one client in 'Manage Clients' before assigning policies.")
    else:
        with st.form("assign_policy_form"):
            client_id = st.selectbox("Select Client ID", client_ids)
            policy_number = st.text_input("Policy Number", placeholder="e.g. POL-HLT-2026-001")
            policy_type = st.selectbox("Policy Type", ["Health", "Life", "Travel", "Commercial", "General"])
            coverage_limit = st.number_input("Coverage Limit ($)", min_value=1000.0, value=50000.0, step=1000.0)
            
            c1, c2 = st.columns(2)
            eff_date = c1.date_input("Effective Start Date", datetime.now())
            exp_date = c2.date_input("Policy Expiry Date", datetime.now())
            status = st.selectbox("Policy Status", ["Active", "Suspended", "Expired"])
            
            submitted = st.form_submit_button("Assign Policy")
            if submitted:
                if policy_number.strip():
                    try:
                        col = client.get_or_create_collection(name=config.COLLECTIONS["client_policies"])
                        col.upsert(
                            documents=[f"Policy {policy_number} for client {client_id} ({policy_type})"],
                            metadatas=[{
                                "policy_number": policy_number.strip(),
                                "client_id": client_id,
                                "policy_type": policy_type,
                                "coverage_limit": coverage_limit,
                                "effective_date": str(eff_date),
                                "expiry_date": str(exp_date),
                                "status": status
                            }],
                            ids=[policy_number.strip()]
                        )
                        st.success(f"Successfully assigned policy `{policy_number}` to client `{client_id}`!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving policy: {e}")
                else:
                    st.warning("Please enter a valid policy number.")