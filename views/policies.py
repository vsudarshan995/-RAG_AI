import streamlit as st
import pandas as pd
import chromadb
import requests
import time
from datetime import datetime

CHROMA_PATH = r"D:\pY\InsuranceRAG\local_db"

st.title("📁 Policy Knowledgebase")
st.caption("Manage enterprise policy documents, document list, and embedding statuses.")
st.divider()

@st.cache_resource
def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_PATH)

client = get_chroma_client()

def get_registry_collection():
    return client.get_or_create_collection(name="policy_registry")

def fetch_policy_registry():
    try:
        col = get_registry_collection()
        results = col.get(include=["metadatas"])
        if not results or not results.get('metadatas'):
            return pd.DataFrame()
        return pd.DataFrame(results['metadatas'])
    except Exception:
        return pd.DataFrame()

df_registry = fetch_policy_registry()

# --- METRICS BANNER ---
total_files = len(df_registry) if not df_registry.empty else 0
completed_embeddings = len(df_registry[df_registry["embedding_status"] == "Completed"]) if not df_registry.empty and "embedding_status" in df_registry.columns else 0

m1, m2, m3 = st.columns(3)
m1.metric("Total Documents", total_files)
m2.metric("Embeddings Completed", f"{completed_embeddings} / {total_files}")
m3.metric("Vector Status", "Synchronized" if total_files > 0 else "Empty")

st.divider()

# --- NAVIGATION TABS ---
tab_repo, tab_upload = st.tabs(["📚 Document List", "📤 Add New Document"])

# --- TAB 1: DOCUMENT LIST TABLE ---
with tab_repo:
    st.subheader("Document List")
    
    if not df_registry.empty:
        col_search, col_cat = st.columns([2, 2])
        search_query = col_search.text_input("🔍 Search Filename", placeholder="Type policy filename...")
        
        categories = ["All", "Health", "Life", "Travel", "Commercial", "General"]
        cat_filter = col_cat.selectbox("Filter Category", categories)
        
        filtered_df = df_registry
        if search_query:
            filtered_df = filtered_df[filtered_df['filename'].str.contains(search_query, case=False, na=False)]
        if cat_filter != "All":
            filtered_df = filtered_df[filtered_df['document_category'] == cat_filter]
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        for idx, row in filtered_df.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([2.5, 1.5, 1.5, 1.5, 1])
                
                c1.markdown(f"**Filename:** `{row.get('filename', 'N/A')}`")
                c1.caption(f"Effective: {row.get('effective_date', 'N/A')} to {row.get('effective_end_date', 'N/A')} | By: {row.get('uploaded_by', 'Admin')}")
                
                c2.markdown(f"**Category:**")
                c2.info(row.get('document_category', 'General'))
                
                c3.markdown(f"**Date Added:**")
                c3.caption(row.get('date_added', 'N/A'))
                
                c4.markdown(f"**Embedding Status:**")
                status = row.get('embedding_status', 'Pending')
                if status == "Completed":
                    c4.success("🟢 Completed")
                elif status == "Failed":
                    c4.error("🔴 Failed")
                else:
                    c4.warning("🟠 Processing")
                    
                if c5.button("Delete", key=f"del_file_{idx}"):
                    filename = row.get('filename')
                    try:
                        res = requests.delete(f"http://localhost:8000/policies/delete/{filename}")
                        if res.status_code == 200:
                            st.success(f"Deleted `{filename}` successfully!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Failed to delete via backend API.")
                    except Exception as ex:
                        st.error(f"Connection error: {ex}")
    else:
        st.info("No documents found in the knowledgebase. Use the 'Add New Document' tab to upload files.")

# --- TAB 2: ADD NEW DOCUMENT ---
with tab_upload:
    st.subheader("Add New Document")
    st.caption("Define parameters, select a single policy document, and trigger automated vector chunking.")

    with st.form("policy_upload_form", clear_on_submit=True):
        policy_category = st.selectbox("Document Category", ["Health", "Life", "Travel", "Commercial", "General"])
        
        col_f1, col_f2 = st.columns(2)
        effective_date = col_f1.date_input("Effective Start Date", datetime.now())
        effective_end_date = col_f2.date_input("Effective End Date", datetime.now())
        
        uploaded_by = st.text_input("Uploaded By", placeholder="e.g. Compliance Officer")
        
        # File uploader control
        uploaded_file = st.file_uploader("Select Policy Document (PDF / TXT)", type=["pdf", "txt"], accept_multiple_files=False)
        
        default_filename = uploaded_file.name if uploaded_file is not None else ""

        # Filename textbox set to read-only (`disabled=True`)
        custom_filename = st.text_input("Filename", value=default_filename, placeholder="File name will appear here upon selection...", disabled=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        submit_button = st.form_submit_button("⚡ Process & Add Document", use_container_width=True)
        
    if submit_button:
        if uploaded_file is not None:
            # Uses the uploaded file name directly since textbox is read-only
            final_filename = uploaded_file.name
            
            files = {"file": (final_filename, uploaded_file.getvalue(), uploaded_file.type)}
            data = {
                "category": policy_category,
                "effective_date": effective_date.strftime("%Y-%m-%d"),
                "effective_end_date": effective_end_date.strftime("%Y-%m-%d"),
                "uploaded_by": uploaded_by.strip() if uploaded_by.strip() else "System Admin"
            }
            try:
                res = requests.post("http://localhost:8000/policies/upload", files=files, data=data)
                if res.status_code == 200:
                    st.success(f"Successfully added and embedded `{final_filename}` under [{policy_category}]!")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error("Backend error during policy processing.")
            except Exception as ex:
                st.error(f"Connection error: {ex}")
        else:
            st.warning("Please select a file to upload first.")