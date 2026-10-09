import streamlit as st
import pandas as pd
from core.graph import agent_system
from providers.db_service import db_service

st.set_page_config(page_title="HITL Risk Queue", page_icon="🛡️", layout="wide")

st.title("🛡️ Human-in-the-Loop Risk Review Queue")
st.caption("PostgreSQL-managed escalation queue for claims exceeding risk threshold (>65/100).")
st.divider()

# 1. Fetch pending reviews from PostgreSQL
pending_tasks = db_service.get_pending_reviews()

if not pending_tasks:
    st.success("✨ Zero pending compliance reviews. All claims are cleared.")
else:
    st.info(f"📋 **{len(pending_tasks)} claim(s)** awaiting manual risk determination.")

    for task in pending_tasks:
        instance_id = task["instance_id"]
        client_id = task.get("client_id", "N/A")
        risk_score = task.get("risk_score", 0)
        created_at = task.get("created_at")
        created_str = created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else "Unknown"

        with st.container(border=True):
            col_id, col_client, col_score, col_time = st.columns([3, 2, 2, 2])
            col_id.markdown(f"**Instance ID:** `{instance_id}`")
            col_client.markdown(f"**Client:** `{client_id}`")
            col_score.error(f"**Risk Score:** {risk_score}/100")
            col_time.caption(f"Created: {created_str}")

            with st.expander("🔍 Inspect Full Audit Context & Decide"):
                thread_config = {"configurable": {"thread_id": instance_id}}
                state_snapshot = agent_system.get_state(thread_config)

                if state_snapshot and state_snapshot.values:
                    c_left, c_right = st.columns(2)
                    with c_left:
                        st.subheader("Compliance Violations Report")
                        st.text_area(
                            "Report Details",
                            value=state_snapshot.values.get("compliance_report", "No report available."),
                            height=160,
                            disabled=True,
                            key=f"rep_{instance_id}"
                        )

                    with c_right:
                        st.subheader("Retrieved Policy Context")
                        st.text_area(
                            "Matched SOP & Policy Clauses",
                            value=state_snapshot.values.get("policy_context", "No context fetched."),
                            height=160,
                            disabled=True,
                            key=f"ctx_{instance_id}"
                        )

                    st.markdown("---")
                    reviewer_notes = st.text_input(
                        "Compliance Officer Rationale / Notes",
                        placeholder="Add review explanation or override rationale...",
                        key=f"notes_{instance_id}"
                    )

                    btn_col1, btn_col2, _ = st.columns([2, 2, 5])
                    with btn_col1:
                        if st.button("✅ Approve Claim", key=f"btn_app_{instance_id}", type="primary", use_container_width=True):
                            try:
                                # Update graph state with human action
                                agent_system.update_state(
                                    thread_config,
                                    {"human_action": "approve", "human_comments": reviewer_notes},
                                    as_node="human_review"
                                )
                                # Resume graph execution from breakpoint to completion
                                agent_system.invoke(None, config=thread_config)

                                # Mark task resolved in PostgreSQL
                                db_service.resolve_review_task(instance_id, "APPROVED", reviewer_notes)
                                st.success(f"Claim `{instance_id}` approved successfully!")
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Error resuming thread: {str(ex)}")

                    with btn_col2:
                        if st.button("❌ Reject Claim", key=f"btn_rej_{instance_id}", use_container_width=True):
                            try:
                                agent_system.update_state(
                                    thread_config,
                                    {"human_action": "reject", "human_comments": reviewer_notes},
                                    as_node="human_review"
                                )
                                agent_system.invoke(None, config=thread_config)

                                db_service.resolve_review_task(instance_id, "REJECTED", reviewer_notes)
                                st.warning(f"Claim `{instance_id}` rejected and archived.")
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Error resuming thread: {str(ex)}")
                else:
                    st.warning("No checkpoint found in PostgreSQL for this instance thread.")