import streamlit as st

st.set_page_config(
    page_title="Trading Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.sidebar.title("📌 Navigation")
st.sidebar.markdown("Use the sidebar to navigate between dashboards.")

st.title("🚀 Algo Trading Dashboard")
st.markdown("""
Welcome to your trading dashboard.  
Select a page from the left sidebar to view holdings, positions, orders, or GTT orders.
""")

st.info("✅ Navigate to pages via the left sidebar.")
