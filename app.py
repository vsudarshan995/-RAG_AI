import streamlit as st

# --- ENTERPRISE CONFIGURATION ---
st.set_page_config(
    page_title="AssureEval Enterprise (AEIP)",
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
        }
        [data-testid="stMetricLabel"] label { color: #94a3b8 !important; }
        [data-testid="stMetricValue"] div { color: #f8fafc !important; }
        .stButton button { 
            background-color: #2563eb; color: white; border-radius: 6px; font-weight: 600; border: none; 
        }
        .stButton button:hover { background-color: #1d4ed8; }
        h1, h2, h3 { color: #f8fafc !important; }
    </style>
""", unsafe_allow_html=True)

# --- DEFINE PAGES ---
dashboard_page = st.Page("views/dashboard.py", title="Executive Control Center", icon="📊", default=True)
evaluation_page = st.Page("views/evaluation.py", title="Start New Evaluation", icon="🚀")
hitl_page = st.Page("views/hitl_queue.py", title="Human Review Queue", icon="🛡️")
policies_page = st.Page("views/policies.py", title="Manage Knowledge Base", icon="📁")
clients_page = st.Page("views/clients.py", title="Manage Clients", icon="👥")
system_admin_page = st.Page("views/system_admin.py", title="System Administration", icon="⚙️")

# NEW: Quality Testing Chatbot Page
chatbot_page = st.Page("views/chatbot.py", title="Policy Chatbot (QA)", icon="🤖")

# --- NAVIGATION SETUP ---
pg = st.navigation({
    "Overview": [dashboard_page],
    "Operations": [evaluation_page, hitl_page],
    "Administration": [policies_page, clients_page, system_admin_page],
    "Quality Testing": [chatbot_page]
})

pg.run()