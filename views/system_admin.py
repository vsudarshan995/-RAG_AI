import streamlit as st
import requests
import pandas as pd
import chromadb
from config import config

st.subheader("⚙️ System Administration: Collection Management")
st.caption("Inspect, export, or purge database collections independently.")

# Connect directly to persistent Chroma client for data inspection
@st.cache_resource
def get_chroma_client():
    return chromadb.PersistentClient(path=config.DB_PATH)

client = get_chroma_client()

# Dynamically load valid collection names from config.py
collection_options = list(config.COLLECTIONS.values())

selected_collection = st.selectbox("Select Target Collection", collection_options)

st.divider()

# --- SECTION 1: INSPECT & EXPORT DATA ---
st.markdown(f"### 📊 Inspect Data: `{selected_collection}`")

if st.button("🔍 Load Collection Records"):
    try:
        col = client.get_or_create_collection(name=selected_collection)
        data = col.get(include=["metadatas", "documents"])
        
        if data and data.get("metadatas") and len(data["metadatas"]) > 0:
            # Flatten metadata into a DataFrame
            df = pd.DataFrame(data["metadatas"])
            if "documents" in data and data["documents"]:
                df["document_text"] = data["documents"]
                
            st.success(f"Successfully loaded {len(df)} records from `{selected_collection}`.")
            st.dataframe(df, use_container_width=True)
            
            # CSV Export Button
            csv_data = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"📥 Export `{selected_collection}` as CSV",
                data=csv_data,
                file_name=f"{selected_collection}_export.csv",
                mime="text/csv",
                type="secondary"
            )
        else:
            st.info(f"The collection `{selected_collection}` is currently empty.")
    except Exception as e:
        st.error(f"Error loading collection data: {str(e)}")

st.divider()

# --- SECTION 2: PURGE COLLECTION ---
st.markdown(f"### ⚠️ Danger Zone: Purge `{selected_collection}`")
st.warning(f"Warning: This will permanently wipe all data inside the `{selected_collection}` collection.")

if st.button("🗑️ Purge Selected Collection", type="primary"):
    try:
        res = requests.delete(f"http://localhost:8000/system/purge-collection/{selected_collection}")
        if res.status_code == 200:
            st.success(f"Collection `{selected_collection}` successfully purged and re-initialized!")
            st.rerun()
        else:
            st.error("Failed to purge collection via backend API.")
    except Exception as ex:
        st.error(f"Connection error: {ex}")