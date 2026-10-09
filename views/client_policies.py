import streamlit as st
import pandas as pd
from datetime import datetime
from psycopg.rows import dict_row
from providers.db_service import pool

st.title("📋 Client Policy Subscriptions")
st.caption("Manage active coverage bindings between clients and policy numbers.")
st.divider()

col_form, col_table = st.columns([1, 2])

with col_form:
    st.subheader("Bind New Policy")
    with st.form("policy_sub_form"):
        pol_id = st.text_input("Policy ID", placeholder="POL_9001")
        client_id = st.text_input("Client ID", placeholder="CLIENT_1001")
        pol_number = st.text_input("Policy Number", placeholder="POL-AUTO-2026-X")
        category = st.selectbox("Category", ["Motor", "Health", "Commercial", "General", "Property"])
        coverage = st.number_input("Coverage Limit (AED)", min_value=0.0, value=50000.0, step=5000.0)
        status = st.selectbox("Status", ["ACTIVE", "EXPIRED", "SUSPENDED"])
        submit_btn = st.form_submit_button("Bind Policy", type="primary")

        if submit_btn:
            if not pol_id or not client_id or not pol_number:
                st.error("Policy ID, Client ID, and Policy Number are mandatory.")
            else:
                try:
                    with pool.connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                INSERT INTO client_policies (policy_id, client_id, policy_number, category, coverage_limit, status)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                ON CONFLICT (policy_id) DO UPDATE SET
                                    category = EXCLUDED.category,
                                    coverage_limit = EXCLUDED.coverage_limit,
                                    status = EXCLUDED.status;
                                """,
                                (pol_id.strip(), client_id.strip(), pol_number.strip(), category, coverage, status)
                            )
                    st.success(f"Policy '{pol_number}' bound successfully.")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error binding policy: {ex}")

with col_table:
    st.subheader("Active Subscriptions")
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT p.policy_id, p.policy_number, p.client_id, c.name AS client_name, 
                           p.category, p.coverage_limit, p.status
                    FROM client_policies p
                    LEFT JOIN clients c ON p.client_id = c.client_id
                    ORDER BY p.policy_id DESC;
                    """
                )
                policies = cur.fetchall()

        if policies:
            df = pd.DataFrame(policies)
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Export Subscriptions CSV", data=csv, file_name="client_policies.csv", mime="text/csv")
        else:
            st.info("No policy subscriptions recorded.")
    except Exception as ex:
        st.error(f"Error reading policies: {ex}")