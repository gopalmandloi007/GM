# frontend/streamlit_app.py
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

import streamlit as st

st.set_page_config(page_title="Definedge Dashboard", layout="wide")
st.title("Definedge — Main Launcher")

st.sidebar.header("Navigation")
pages = {
    "01 - Login & Session": "frontend.pages.01_login",
    "02 - Portfolio": "frontend.pages.02_portfolio",
    "03 - Orders (stub)": "frontend.pages.03_orders",
    "04 - Place Order (stub)": "frontend.pages.04_place_order",
    "05 - Historical Tools": "frontend.pages.05_historical",
    # add other pages as created
}

choice = st.sidebar.selectbox("Open page", list(pages.keys()))
module_path = pages[choice]

# dynamic import
try:
    module = __import__(module_path, fromlist=["*"])
    if hasattr(module, "app"):
        module.app()   # each page exposes app()
    else:
        # fallback: render module-level if function not present
        st.write(f"Page {choice} loaded: {module.__name__}")
except Exception as e:
    st.error(f"Failed to load page {choice}: {e}")
