import streamlit as st
import pandas as pd
import chromadb
from psycopg.rows import dict_row

from config import config
from providers.db_service import pool

st.subheader("⚙️ System Administration: Storage & DB Management")
st.caption("Inspect and manage ChromaDB vector stores and PostgreSQL relational tables.")

tab_chroma, tab_postgres = st.tabs(["🔮 ChromaDB Vector Stores", "🐘 PostgreSQL Relational DB"])

# --- TAB 1: CHROMADB ---
with tab_chroma:
    @st.cache_resource
    def get_chroma_client():
        try:
            http_client = chromadb.HttpClient(
                host=getattr(config, "CHROMA_HOST", "localhost"), 
                port=getattr(config, "CHROMA_PORT", 8001)
            )
            http_client.heartbeat()
            return http_client
        except Exception:
            return chromadb.PersistentClient(path=config.DB_PATH)

    client = get_chroma_client()

    vector_collections = [
        config.COLLECTIONS.get("policy_vector", "vr_policy"),
        config.COLLECTIONS.get("claims", "claims_collection"),
        config.COLLECTIONS.get("registry", "policy_registry")
    ]

    selected_col_name = st.selectbox("Select Vector Collection", vector_collections)

    st.markdown(f"#### 📊 Inspect Data: `{selected_col_name}`")

    if st.button("🔍 Load Chroma Records", key="btn_load_chroma"):
        try:
            col = client.get_or_create_collection(name=selected_col_name)
            data = col.get(include=["metadatas", "documents"])

            if data and data.get("metadatas") and len(data["metadatas"]) > 0:
                df_meta = pd.DataFrame(data["metadatas"])
                if "documents" in data and data["documents"]:
                    df_meta["document_snippet"] = [
                        (doc[:100] + "...") if doc and len(doc) > 100 else doc 
                        for doc in data["documents"]
                    ]

                st.success(f"Found {len(df_meta)} records in `{selected_col_name}`.")
                st.dataframe(df_meta, use_container_width=True)

                csv_data = df_meta.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label=f"📥 Export `{selected_col_name}` CSV",
                    data=csv_data,
                    file_name=f"{selected_col_name}_export.csv",
                    mime="text/csv",
                    key="dl_chroma_csv"
                )
            else:
                st.info(f"Collection `{selected_col_name}` is currently empty.")
        except Exception as e:
            st.error(f"Error reading Chroma collection: {e}")

    st.divider()
    st.markdown(f"#### ⚠️ Reset Vector Collection: `{selected_col_name}`")

    if st.button("🗑️ Purge Collection", type="primary", key="btn_purge_chroma"):
        try:
            client.delete_collection(name=selected_col_name)
            client.get_or_create_collection(name=selected_col_name)
            st.success(f"Collection `{selected_col_name}` was successfully purged and reset.")
            st.rerun()
        except Exception as ex:
            st.error(f"Failed to reset collection: {ex}")

# --- TAB 2: POSTGRESQL ---
with tab_postgres:
    ALLOWED_PG_TABLES = [
        "human_review_tasks",
        "evaluation_audit_log",
        "clients",
        "client_policies"
    ]

    selected_pg_table = st.selectbox("Select PostgreSQL Table", ALLOWED_PG_TABLES)
    st.markdown(f"#### 📋 Inspect Table: `{selected_pg_table}`")

    if st.button("🔍 Load Table Records", key="btn_load_pg"):
        try:
            with pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(f"SELECT * FROM {selected_pg_table} ORDER BY 1 DESC LIMIT 100;")
                    rows = cur.fetchall()

            if rows:
                df_pg = pd.DataFrame(rows)
                st.success(f"Loaded {len(df_pg)} rows from `{selected_pg_table}`.")
                st.dataframe(df_pg, use_container_width=True)

                csv_pg = df_pg.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label=f"📥 Export `{selected_pg_table}` CSV",
                    data=csv_pg,
                    file_name=f"{selected_pg_table}_export.csv",
                    mime="text/csv",
                    key="dl_pg_csv"
                )
            else:
                st.info(f"Table `{selected_pg_table}` has no records.")
        except Exception as ex:
            st.error(f"Error querying PostgreSQL: {ex}")

    st.divider()
    st.markdown(f"#### ⚠️ Reset Table Data: `{selected_pg_table}`")
    confirm_purge = st.checkbox(f"Confirm truncate of `{selected_pg_table}`", key="chk_confirm_pg")

    if st.button("🗑️ Truncate Table Records", type="secondary", key="btn_purge_pg", disabled=not confirm_purge):
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"TRUNCATE TABLE {selected_pg_table} CASCADE;")
            st.success(f"Table `{selected_pg_table}` has been truncated.")
            st.rerun()
        except Exception as ex:
            st.error(f"Failed to truncate table: {ex}")