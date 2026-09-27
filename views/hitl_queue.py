import streamlit as st
import chromadb
import pandas as pd

CHROMA_PATH = r"D:\pY\InsuranceRAG\local_db"
client = chromadb.PersistentClient(path=CHROMA_PATH)

try:
    collection = client.get_collection("human_review_tasks")
    results = collection.get(include=["documents", "metadatas"])
    review_df = pd.DataFrame([{**meta, 'content': doc} for doc, meta in zip(results['documents'], results['metadatas'])]) if results and results.get('ids') else pd.DataFrame()
except:
    review_df = pd.DataFrame()

st.title("🛡️ Human-in-the-Loop Risk Review Queue")
st.caption("Actionable exception queue for claims exceeding automated risk thresholds (>65/100).")
st.divider()

if not review_df.empty and 'status' in review_df.columns:
    pending = review_df[review_df['status'] == 'PENDING_REVIEW']
    if not pending.empty:
        for _, row in pending.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
                c1.write(f"**ID:** `{row['instance_id'][:10]}...`")
                c2.write(f"**Client:** {row.get('client_id', 'N/A')}")
                c3.error(f"**Risk Score:** {row.get('risk_score', 0)}/100")
                if c4.button("Review Case", key=f"hitl_{row['instance_id']}"):
                    st.info(f"Opening review modal for instance {row['instance_id']}")
    else:
        st.success("✨ Zero pending compliance reviews. All workflows are cleared.")
else:
    st.info("No human review items logged.")