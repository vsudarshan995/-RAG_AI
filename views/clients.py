import streamlit as st
import pandas as pd
from datetime import datetime
from psycopg.rows import dict_row
from providers.db_service import pool

st.title("👥 Client Portfolio Management")
st.caption("PostgreSQL-backed client directory and risk management.")
st.divider()

col_form, col_table = st.columns([1, 2])

with col_form:
    st.subheader("Register / Update Client")
    with st.form("client_reg_form"):
        c_id = st.text_input("Client ID", placeholder="CLIENT_1001")
        c_name = st.text_input("Full Name", placeholder="Acme Logistics LLC")
        c_email = st.text_input("Email", placeholder="contact@acme.ae")
        c_phone = st.text_input("Phone", placeholder="+971 50 123 4567")
        submit_btn = st.form_submit_button("Save Client", type="primary")

        if submit_btn:
            if not c_id or not c_name:
                st.error("Client ID and Full Name are mandatory.")
            else:
                try:
                    with pool.connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                INSERT INTO clients (client_id, name, email, phone)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (client_id) DO UPDATE SET
                                    name = EXCLUDED.name,
                                    email = EXCLUDED.email,
                                    phone = EXCLUDED.phone;
                                """,
                                (c_id.strip(), c_name.strip(), c_email.strip(), c_phone.strip())
                            )
                    st.success(f"Client '{c_name}' recorded successfully.")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error saving to database: {ex}")

with col_table:
    st.subheader("Registered Clients")
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT client_id, name, email, phone, created_at FROM clients ORDER BY created_at DESC;")
                clients = cur.fetchall()

        if clients:
            df = pd.DataFrame(clients)
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Export Clients CSV", data=csv, file_name="clients.csv", mime="text/csv")
        else:
            st.info("No registered clients found in PostgreSQL.")
    except Exception as ex:
        st.error(f"Error reading client directory: {ex}")