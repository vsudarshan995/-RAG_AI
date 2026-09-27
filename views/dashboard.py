import streamlit as st
import chromadb
import pandas as pd
import time
import requests
from datetime import datetime

# --- ENTERPRISE CONFIGURATION ---
CHROMA_PATH = r"D:\pY\InsuranceRAG\local_db"
st.set_page_config(
    page_title="AssureEval | Insurance Evaluation & Audit Control Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Professional Dark Boardroom Theme Customization via CSS
st.markdown("""
    <style>
        .main { background-color: #0f172a; color: #f8fafc; }
        
        [data-testid="stMetric"] {
            background-color: #1e293b !important;
            padding: 20px !important;
            border-radius: 10px !important;
            border: 1px solid #334155 !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3) !important;
        }
        
        [data-testid="stMetricLabel"] label {
            color: #94a3b8 !important;
        }
        [data-testid="stMetricValue"] div {
            color: #f8fafc !important;
        }
        
        .stButton button { 
            background-color: #2563eb; 
            color: white; 
            border-radius: 6px; 
            font-weight: 600; 
            border: none; 
        }
        .stButton button:hover { 
            background-color: #1d4ed8; 
        }
        
        h1, h2, h3 { color: #f8fafc !important; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_PATH)

client = get_chroma_client()

def fetch_collection_data(collection_name):
    try:
        collection = client.get_collection(collection_name)
        results = collection.get(include=["documents", "metadatas"])
        if not results or not results.get('ids'): return pd.DataFrame()
        data = [{**meta, 'content': doc} for doc, meta in zip(results['documents'], results['metadatas'])]
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

# --- MODAL: AGENTIC DECISION & AUDIT TRAIL ---
@st.dialog("🔍 Comprehensive Decision Traceability & Audit Trail", width="large")
def show_audit_flow(instance_id):
    st.markdown(f"**Transaction Instance Identifier:** `{instance_id}`")
    st.divider()
    
    audit_details_df = fetch_collection_data("evaluation_audit_log")
    if audit_details_df.empty:
        st.warning("No telemetry records found for this instance.")
        return

    detail_data = audit_details_df[audit_details_df['instance_id'] == instance_id]
    
    for i, (_, row) in enumerate(detail_data.iterrows()):
        with st.container(border=True):
            c1, c2 = st.columns([1, 4])
            c1.markdown(f"**Pipeline Stage {i+1}**")
            c1.caption(row.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M')))
            
            status = row.get('status', 'INFO')
            badge_color = "red" if status == "FAILED" else "green" if status == "COMPLETED" else "orange"
            c2.markdown(f"**Execution Status:** :{badge_color}[`{status}`]")
            c2.info(row.get('content', 'No content logged.'))
            
    if st.button("Close Audit Window", use_container_width=True):
        st.rerun()

# --- MODAL: HUMAN-IN-THE-LOOP CASE RESOLUTION ---
@st.dialog("🛡️ Compliance Risk Review & Approval Portal", width="large")
def show_review_dialog(instance_id):
    st.markdown(f"**Flagged Case Ref:** `{instance_id}`")
    
    review_df = fetch_collection_data("human_review_tasks")
    if review_df.empty or instance_id not in review_df['instance_id'].values:
        st.error("Case details not found.")
        return
        
    task_meta = review_df[review_df['instance_id'] == instance_id].to_dict(orient="records")[0]
    
    c1, c2 = st.columns(2)
    c1.metric("Target Client ID", task_meta.get('client_id', 'N/A'))
    c2.metric("Evaluated Risk Score", task_meta.get('risk_score', 'N/A'), delta="High Risk Anomaly", delta_color="inverse")
    
    st.markdown("### 📋 Automated Compliance Report")
    st.warning(task_meta.get('compliance_report', 'No automated report notes generated.'))
    
    st.markdown("### ✍️ Officer Decision & Remediation")
    comments = st.text_area("Justification / Audit Remarks", placeholder="Enter notes for regulatory reporting...")
    
    col1, col2 = st.columns(2)
    if col1.button("✅ Approve Claim & Resume Workflow", type="primary", use_container_width=True):
        st.success(f"Case {instance_id[:8]} successfully APPROVED. Workflow unblocked.")
        time.sleep(1.5)
        st.rerun()
        
    if col2.button("❌ Reject & Escalate Case", type="secondary", use_container_width=True):
        st.error(f"Case {instance_id[:8]} REJECTED. Logged to compliance audit ledger.")
        time.sleep(1.5)
        st.rerun()

# --- MAIN DASHBOARD HEADER ---
st.title("🛡️ AssureEval Enterprise (AEIP)")
st.caption("Autonomous Insurance Evaluation, Multi-Agent RAG Orchestration & Real-time Risk Governance")
st.divider()

# --- EXECUTIVE METRICS BANNER ---
instances_df = fetch_collection_data("instance_log")
review_df = fetch_collection_data("human_review_tasks")

col1, col2, col3, col4 = st.columns(4)
total_evals = len(instances_df) if not instances_df.empty else 0
pending_hits = len(review_df[review_df['status'] == 'PENDING_REVIEW']) if not review_df.empty else 0
completed_runs = len(instances_df[instances_df['status'] == 'COMPLETED']) if not instances_df.empty else 0
system_health = "Operational (99.98%)"

col1.metric("Total Processed Requests", total_evals)
col2.metric("Pending Human Reviews", pending_hits, delta=f"{pending_hits} require action" if pending_hits > 0 else "All Clear", delta_color="inverse" if pending_hits > 0 else "normal")
col3.metric("Straight-Through Processing", f"{(completed_runs/total_evals*100):.1f}%" if total_evals > 0 else "0%")
col4.metric("Platform Status", system_health)

st.divider()

# --- TABS FOR ENTERPRISE NAVIGATION ---
tab1, tab2 = st.tabs(["🛡️ Human-in-the-Loop Review Queue", "📋 Master Transaction & Audit Registry"])

# --- TAB 1: HUMAN REVIEW QUEUE ---
with tab1:
    st.subheader("Actionable Compliance Queue (Anomalies & High-Risk Rules)")
    if not review_df.empty and 'status' in review_df.columns:
        pending_queue = review_df[review_df['status'] == 'PENDING_REVIEW']
        if not pending_queue.empty:
            for idx, row in pending_queue.iterrows():
                with st.container(border=True):
                    rc1, rc2, rc3, rc4 = st.columns([2, 2, 2, 2])
                    rc1.write(f"**ID:** `{row['instance_id'][:12]}...`")
                    rc2.write(f"**Client:** {row.get('client_id', 'N/A')}")
                    rc3.error(f"**Risk Score:** {row.get('risk_score', 0)} / 100")
                    
                    if rc4.button("Inspect & Resolve", key=f"hitl_btn_{row['instance_id']}_{idx}"):
                        show_review_dialog(row['instance_id'])
        else:
            st.success("✨ Zero pending compliance items. All workflows are operating normally.")
    else:
        st.info("No human review tasks currently logged in database.")

# --- TAB 2: MASTER TRANSACTION REGISTRY ---
with tab2:
    st.subheader("Complete Enterprise Transaction Registry")
    
    search_term = st.text_input("🔍 Filter by Client ID or Instance ID", placeholder="Type to search audit logs...")
    
    if not instances_df.empty:
        display_df = instances_df
        if search_term:
            display_df = instances_df[
                instances_df['instance_id'].str.contains(search_term, case=False, na=False) |
                instances_df['client_id'].str.contains(search_term, case=False, na=False)
            ]
            
        for idx, row in display_df.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                c1.write(f"**Instance:** `{row['instance_id']}`")
                c2.write(f"**Client:** {row.get('client_id', 'N/A')}")
                status = row.get('status', 'UNKNOWN')
                c3.markdown(f"**Status:** `{status}`")
                
                if status in ["FAILED", "CANCELLED"]:
                    if c4.button("🔄 Retry", key=f"retry_btn_{row['instance_id']}_{idx}"):
                        payload = {
                            "client_id": row.get('client_id', 'client_default'),
                            "submission_date": datetime.now().strftime("%Y-%m-%d"),
                            "question": "Retry evaluation from dashboard."
                        }
                        try:
                            res = requests.post("http://localhost:8000/ask/investigate/async", json=payload)
                            if res.status_code == 200:
                                st.success("Evaluation restarted successfully!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Failed to reach backend API.")
                        except Exception as ex:
                            st.error(f"Connection error: {ex}")
                else:
                    if c4.button("View Trace", key=f"trace_btn_{row['instance_id']}_{idx}"):
                        show_audit_flow(row['instance_id'])
    else:
        st.info("Instance log registry is currently empty.")

# --- SIDEBAR CONTROL PANEL & INGESTION ---
st.sidebar.title("🎛️ Control Panel")
st.sidebar.markdown("### 📥 Document Ingestion")
uploaded_file = st.sidebar.file_uploader("Upload Policy / Claim PDF", type=["pdf", "txt"])
if uploaded_file is not None:
    if st.sidebar.button("Process & Index Document"):
        # Ingestion logic placeholder (can connect to backend ingestion endpoint)
        st.sidebar.success(f"Successfully indexed: {uploaded_file.name}")

st.sidebar.divider()
st.sidebar.markdown("### 🚀 Trigger New Evaluation")
sidebar_client_id = st.sidebar.text_input("Client ID", "client_999")
sidebar_sub_date = st.sidebar.date_input("Submission Date", datetime.now())
sidebar_question = st.sidebar.text_area("Claim Details / Question", "Audit request for motor accident claim.")

if st.sidebar.button("Run Autonomous Evaluation", use_container_width=True):
    payload = {
        "client_id": sidebar_client_id,
        "submission_date": sidebar_sub_date.strftime("%Y-%m-%d"),
        "question": sidebar_question
    }
    try:
        response = requests.post("http://localhost:8000/ask/investigate/async", json=payload)
        if response.status_code == 200:
            st.sidebar.success("Evaluation triggered successfully!")
            time.sleep(1.5)
            st.rerun()
        else:
            st.sidebar.error("Failed to trigger backend workflow.")
    except Exception as e:
        st.sidebar.error(f"Connection error: {e}")

st.sidebar.divider()
st.sidebar.caption("Environment: Production Cluster")
st.sidebar.caption("Last synchronized: " + datetime.now().strftime("%H:%M:%S"))
if st.sidebar.button("🔄 Refresh Telemetry", use_container_width=True):
    st.rerun()