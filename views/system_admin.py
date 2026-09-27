import streamlit as st
import requests

st.subheader("⚙️ System Administration: Collection Management")
st.caption("Select a specific database collection to purge or reset independently.")

# List of all available collections in your system
collection_options = [
    "policy_master_collection",
    "policy_registry",
    "claims_collection",
    "evaluations_collection",
    "instance_logs_collection",
    "clients_collection",
    "human_review_tasks"
]

selected_collection = st.selectbox("Select Collection to Purge", collection_options)

st.warning(f"⚠️ Warning: This will wipe all data inside the `{selected_collection}` collection.")

if st.button("🗑️ Purge Selected Collection", type="primary"):
    try:
        res = requests.delete(f"http://localhost:8000/system/purge-collection/{selected_collection}")
        if res.status_code == 200:
            st.success(f"Collection `{selected_collection}` successfully purged and re-initialized!")
        else:
            st.error("Failed to purge collection via backend API.")
    except Exception as ex:
        st.error(f"Connection error: {ex}")