import streamlit as st
import chromadb
import pandas as pd
import time

# --- CONFIGURATION ---
CHROMA_PATH = r"D:\pY\InsuranceRAG\local_db"
st.set_page_config(page_title="InsuranceRAG Audit Dashboard", layout="wide")

@st.cache_resource
def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_PATH)

client = get_chroma_client()

def fetch_collection_data(collection_name):
    try:
        collection = client.get_collection(collection_name)
        results = collection.get(include=["documents", "metadatas"])
        if not results['ids']: return pd.DataFrame()
        data = [{**meta, 'content': doc} for doc, meta in zip(results['documents'], results['metadatas'])]
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# --- THE NATIVE POPUP (DIALOG) ---
@st.dialog("Investigation Flow Preview", width="large")
def show_audit_flow(instance_id):
    st.write(f"Showing detailed logs for: **{instance_id}**")
    audit_details_df = fetch_collection_data("evaluation_audit_log")
    
    if audit_details_df.empty:
        st.warning("No logs found.")
        return

    detail_data = audit_details_df[audit_details_df['instance_id'] == instance_id]
    
    # Simple vertical flow using containers
    for i, (_, row) in enumerate(detail_data.iterrows()):
        with st.container(border=True):
            c1, c2 = st.columns([1, 4])
            c1.markdown(f"**Step {i+1}**")
            c1.caption(row.get('timestamp', ''))
            
            c2.markdown(f"**Status:** `{row['status']}`")
            c2.info(row['content'])
            
    if st.button("Close"):
        st.rerun()

# --- MAIN DASHBOARD ---
st.title("🛡️ InsuranceRAG: Multi-Agent Audit Monitor")

instances_df = fetch_collection_data("instance_log")

if not instances_df.empty:
    st.subheader("📋 Instance Registry")
    
    # Display the registry in a clean table
    # We use a loop to add a functional button for every row
    for _, row in instances_df.iterrows():
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            col1.write(f"**ID:** {row['instance_id']}")
            col2.write(f"**Client:** {row.get('client_id', 'N/A')}")
            col3.write(f"**Status:** `{row['status']}`")
            
            # The Straightforward Streamlit Way:
            if col4.button("View Flow", key=f"btn_{row['instance_id']}"):
                show_audit_flow(row['instance_id'])

# --- REFRESH LOGIC ---
st.sidebar.caption("Last updated: " + time.strftime("%H:%M:%S"))
if st.sidebar.button("Manual Refresh"):
    st.rerun()

# Auto-refresh only if a dialog is NOT open
# (Streamlit handles dialog state automatically)
time.sleep(10)
st.rerun()