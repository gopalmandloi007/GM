import streamlit as st

st.set_page_config(
    page_title="Definedge Trading Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Definedge Trading Dashboard")
st.sidebar.success("Select a page from the left")

st.write("""
Welcome to your compact trading dashboard.  
Use the sidebar to navigate to different modules:  
- Login  
- Portfolio / Holdings / Positions  
- Orders & OrderBook  
- GTT Orders  
- Historical Data  
""")
