import streamlit as st
import pandas as pd
import chromadb
import time
from datetime import datetime
from config import config

st.title("📋 Client Policy Subscriptions")
st.caption("Manage active policy assignments, coverage limits, and validity dates for registered clients.")
st.divider()

client = chromadb.PersistentClient(path=config.DB_PATH)

def fetch_client_options():
    try:
        col = client.get_or_create_collection(name=config.COLLECTIONS["clients"])
        res = col.get(include=["metadatas"])
        if res and res.get("metadatas"):
            options = {}
            for m in res["metadatas"]:
                cid = m.get("client_id")
                cname = m.get("name", "Unknown")
                display_label = f"{cid} - {cname}"
                options[display_label] = cid
            return options
        return {}
    except:
        return {}

def fetch_client_policies():
    try:
        col = client.get_or_create_collection(name=config.COLLECTIONS["client_policies"])
        res = col.get(include=["metadatas"])
        return pd.DataFrame(res["metadatas"]) if res and res.get("metadatas") else pd.DataFrame()
    except:
        return pd.DataFrame()

client_options = fetch_client_options()
df_policies = fetch_client_policies()

# Initialize session state for active tab tracking if not present
if "policy_active_tab" not in st.session_state:
    st.session_state.policy_active_tab = 0

# Use radio or radio-like tab selection or manage via query params / session state
tab_titles = ["📚 Assigned Policies", "➕ Assign New Policy"]
selected_tab_idx = st.radio("Navigation", range(len(tab_titles)), format_func=lambda x: tab_titles[x], horizontal=True, label_visibility="collapsed", index=st.session_state.policy_active_tab)

st.divider()

if selected_tab_idx == 0:
    st.session_state.policy_active_tab = 0
    st.subheader("Assigned Policy Directory")
    if not df_policies.empty:
        st.dataframe(df_policies, use_container_width=True)
    else:
        st.info("No client policies assigned yet.")

elif selected_tab_idx == 1:
    st.session_state.policy_active_tab = 1
    st.subheader("Assign New Policy")
    
    if not client_options:
        st.warning("Please register at least one client in 'Manage Clients' before assigning policies.")
    else:
        with st.form("assign_policy_form", clear_on_submit=True):
            selected_display_label = st.selectbox("Select Client", list(client_options.keys()))
            client_id = client_options[selected_display_label]
            
            policy_type = st.selectbox("Policy Type", ["Health", "Life", "Travel", "Commercial", "General"])
            
            type_prefix = policy_type[:3].upper()
            date_suffix = datetime.now().strftime("%Y%m%d")
            default_policy_number = f"{type_prefix}-{client_id}-{date_suffix}"
            
            policy_number = st.text_input("Policy Number (Auto-generated / Editable)", value=default_policy_number)
            coverage_limit = st.number_input("Coverage Limit ($)", min_value=1000.0, value=50000.0, step=1000.0)
            
            c1, c2 = st.columns(2)
            eff_date = c1.date_input("Effective Start Date", datetime.now())
            exp_date = c2.date_input("Policy Expiry Date", datetime.now())
            status = st.selectbox("Policy Status", ["Active", "Suspended", "Expired"])
            
            submitted = st.form_submit_button("Assign Policy", use_container_width=True)
            if submitted:
                if policy_number.strip():
                    try:
                        col = client.get_or_create_collection(name=config.COLLECTIONS["client_policies"])
                        col.upsert(
                            documents=[f"Policy {policy_number.strip()} for client {client_id} ({policy_type})"],
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
                        st.success(f"Successfully assigned policy `{policy_number.strip()}` to client `{client_id}`!")
                        st.session_state.policy_active_tab = 0  # Switch back to Assigned Policies tab
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving policy: {e}")
                else:
                    st.warning("Please enter a valid policy number.")