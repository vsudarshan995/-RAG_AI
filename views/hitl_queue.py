import streamlit as st
import chromadb
import pandas as pd
from datetime import datetime
from config import config
from core.graph import agent_system

client = chromadb.PersistentClient(path=config.DB_PATH)

try:
    collection = client.get_collection(config.COLLECTIONS["human_reviews"])
    results = collection.get(include=["documents", "metadatas"])
    review_df = pd.DataFrame([{**meta, 'content': doc} for doc, meta in zip(results['documents'], results['metadatas'])]) if results and results.get('ids') else pd.DataFrame()
except Exception:
    review_df = pd.DataFrame()

st.title("🛡️ Human-in-the-Loop Risk Review Queue")
st.caption("Actionable exception queue for claims exceeding automated risk thresholds (>65/100).")
st.divider()

if not review_df.empty and 'status' in review_df.columns:
    pending = review_df[review_df['status'] == 'PENDING_REVIEW']
    if not pending.empty:
        for _, row in pending.iterrows():
            instance_id = row['instance_id']
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
                c1.write(f"**Instance:** `{instance_id[:12]}...`")
                c2.write(f"**Client:** {row.get('client_id', 'N/A')}")
                c3.error(f"**Risk Score:** {row.get('risk_score', 0)}/100")
                
                # Expandable details & review actions
                with st.expander(f"Review Case: {instance_id}"):
                    thread_config = {"configurable": {"thread_id": instance_id}}
                    
                    # Fetch interrupted graph snapshot from PostgreSQL
                    state_snapshot = agent_system.get_state(thread_config)
                    
                    if state_snapshot and state_snapshot.values:
                        st.markdown("#### Claim State Context")
                        st.write(f"**Category:** {state_snapshot.values.get('policy_category', 'N/A')}")
                        st.text_area("Compliance Report", value=state_snapshot.values.get('compliance_report', ''), height=100, disabled=True)
                        st.text_area("Retrieved Policy Context", value=state_snapshot.values.get('policy_context', ''), height=120, disabled=True)
                        
                        reviewer_comments = st.text_input("Reviewer Notes / Justification", key=f"notes_{instance_id}")
                        
                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.button("✅ Approve Claim", key=f"app_{instance_id}", type="primary"):
                                # 1. Inject human decision into Postgres state
                                agent_system.update_state(
                                    thread_config,
                                    {
                                        "human_action": "approve",
                                        "human_comments": reviewer_comments
                                    },
                                    as_node="human_review"
                                )
                                # 2. Resume execution through archiver to END
                                agent_system.invoke(None, config=thread_config)
                                
                                # 3. Update status in ChromaDB task tracker
                                collection.update(
                                    ids=[instance_id],
                                    metadatas=[{**row.to_dict(), "status": "APPROVED", "reviewed_at": datetime.now().isoformat()}]
                                )
                                st.success("Claim approved and workflow completed.")
                                st.rerun()

                        with btn_col2:
                            if st.button("❌ Reject Claim", key=f"rej_{instance_id}"):
                                # 1. Inject rejection into Postgres state
                                agent_system.update_state(
                                    thread_config,
                                    {
                                        "human_action": "reject",
                                        "human_comments": reviewer_comments
                                    },
                                    as_node="human_review"
                                )
                                # 2. Resume execution
                                agent_system.invoke(None, config=thread_config)
                                
                                # 3. Update status in ChromaDB
                                collection.update(
                                    ids=[instance_id],
                                    metadatas=[{**row.to_dict(), "status": "REJECTED", "reviewed_at": datetime.now().isoformat()}]
                                )
                                st.warning("Claim rejected and workflow completed.")
                                st.rerun()
                    else:
                        st.info("State snapshot not found in PostgreSQL. Ensure the graph was executed with this thread_id.")
    else:
        st.success("✨ Zero pending compliance reviews. All workflows are cleared.")
else:
    st.info("No human review items logged.")