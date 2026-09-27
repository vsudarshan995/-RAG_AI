import streamlit as st
import pandas as pd
import chromadb
import time
from datetime import datetime

CHROMA_PATH = r"D:\pY\InsuranceRAG\local_db"

st.title("👥 Enterprise Client Portfolio & Risk Governance")
st.caption("Centralized Directory of Customer Profiles, Historical Risk Ratings, and Policy Bindings")
st.divider()

@st.cache_resource
def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_PATH)

client = get_chroma_client()

def get_clients_collection():
    return client.get_or_create_collection(name="client_directory")

def fetch_clients_from_db():
    try:
        col = get_clients_collection()
        results = col.get(include=["metadatas"])
        if not results or not results.get('metadatas'):
            return pd.DataFrame()
        return pd.DataFrame(results['metadatas'])
    except Exception:
        return pd.DataFrame()

df_clients = fetch_clients_from_db()

# --- PORTFOLIO SUMMARY METRICS ---
total_clients = len(df_clients) if not df_clients.empty else 0
high_risk_count = len(df_clients[df_clients["risk_tier"] == "High Risk"]) if not df_clients.empty and "risk_tier" in df_clients.columns else 0
verified_count = len(df_clients[df_clients["kyc_status"] == "Verified"]) if not df_clients.empty and "kyc_status" in df_clients.columns else 0
total_policies = int(df_clients["active_policies"].sum()) if not df_clients.empty and "active_policies" in df_clients.columns else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Client Portfolios", total_clients)
m2.metric("KYC Verified Accounts", verified_count, delta=f"{(verified_count/total_clients*100):.0f}% compliant" if total_clients > 0 else "0%")
m3.metric("High-Risk Tier Flagged", high_risk_count, delta="Requires monitoring" if high_risk_count > 0 else "Normal", delta_color="inverse" if high_risk_count > 0 else "normal")
m4.metric("Active Policy Bindings", total_policies)

st.divider()

# --- NAVIGATION TABS ---
tab_directory, tab_onboard, tab_analytics = st.tabs([
    "📋 Client Directory & Master List", 
    "➕ Onboard / Update Client", 
    "📊 Portfolio Risk Distribution"
])

# --- TAB 1: CLIENT DIRECTORY ---
with tab_directory:
    st.subheader("Client Master Directory (Live Database)")
    
    if not df_clients.empty:
        col_search, col_filter = st.columns([3, 1])
        search_query = col_search.text_input("🔍 Search by Client Name or ID", placeholder="Type client ID or name...")
        risk_filter = col_filter.selectbox("Filter Risk Tier", ["All", "Low Risk", "Medium Risk", "High Risk"])
        
        filtered_df = df_clients
        if search_query:
            filtered_df = filtered_df[
                filtered_df['client_id'].str.contains(search_query, case=False, na=False) |
                filtered_df['name'].str.contains(search_query, case=False, na=False)
            ]
        if risk_filter != "All":
            filtered_df = filtered_df[filtered_df['risk_tier'] == risk_filter]
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        for idx, row in filtered_df.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                c1.markdown(f"**ID:** `{row['client_id']}` | **Name:** {row['name']}")
                c2.markdown(f"**KYC:** `{'🟢 ' + row['kyc_status']}`")
                risk_color = "red" if row['risk_tier'] == "High Risk" else "orange" if row['risk_tier'] == "Medium Risk" else "green"
                c3.markdown(f"**Risk:** :{risk_color}[**{row['risk_tier']}**]")
                c4.markdown(f"**Policies:** {row['active_policies']}")
    else:
        st.info("No client profiles found in the database. Use the onboarding tab to register clients.")

# --- TAB 2: ONBOARD / UPDATE CLIENT ---
with tab_onboard:
    st.subheader("Customer Onboarding & Profile Sync")
    
    with st.form("onboard_form"):
        col_a, col_b = st.columns(2)
        new_id = col_a.text_input("Client ID", f"client_{total_clients + 101}")
        new_name = col_b.text_input("Full Legal Name", placeholder="e.g. Maryam Al-Binali")
        
        col_c, col_d = st.columns(2)
        new_risk = col_c.selectbox("Risk Assessment", ["Low Risk", "Medium Risk", "High Risk"])
        new_kyc = col_d.selectbox("KYC Compliance Status", ["Verified", "Pending Review"])
        
        initial_policies = st.number_input("Active Policies", min_value=1, max_value=10, value=1)
        
        if st.form_submit_button("💾 Save / Register Client to Database", use_container_width=True):
            try:
                col = get_clients_collection()
                # Use upsert to handle new registrations or updating existing client IDs seamlessly
                col.upsert(
                    documents=[f"Client Profile: {new_name} ({new_id}) with risk tier {new_risk}"],
                    metadatas=[{
                        "client_id": new_id,
                        "name": new_name,
                        "risk_tier": new_risk,
                        "kyc_status": new_kyc,
                        "active_policies": int(initial_policies),
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }],
                    ids=[new_id]
                )
                st.success(f"Client {new_name} (`{new_id}`) successfully saved to database!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Database error: {e}")

# --- TAB 3: PORTFOLIO RISK DISTRIBUTION ---
with tab_analytics:
    st.subheader("Portfolio Risk Analytics & Compliance Breakdown")
    st.markdown("Overview of portfolio risk distribution for executive risk management review.")
    
    if not df_clients.empty:
        col_x, col_y = st.columns(2)
        with col_x:
            st.markdown("#### Risk Tier Composition")
            risk_counts = df_clients["risk_tier"].value_counts()
            st.dataframe(risk_counts, use_container_width=True)
            
        with col_y:
            st.markdown("#### KYC Compliance Status")
            kyc_counts = df_clients["kyc_status"].value_counts()
            st.dataframe(kyc_counts, use_container_width=True)
    else:
        st.info("No analytics available. Register clients to view portfolio distribution.")