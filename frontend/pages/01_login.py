import streamlit as st
from trading_engine.session import SessionManager, SessionError
from trading_engine.client import Client  # <-- यह तुम्हारे broker का SDK wrapper है

def login_page():
    st.title("🔐 Login to Trading App")

    api_key = st.text_input("API Key")
    api_secret = st.text_input("API Secret", type="password")
    totp_secret = st.text_input("TOTP Secret (if any)", type="password")

    if st.button("Login"):
        if not api_key or not api_secret:
            st.error("API Key and Secret required")
            return

        try:
            session_manager = SessionManager(api_key, api_secret, totp_secret)
            session = session_manager.login(Client)  # Client class से broker login होगा
            st.session_state["session_manager"] = session_manager
            st.success("✅ Login successful!")
            st.switch_page("pages/02_holdings.py")  # अगली page पर redirect
        except SessionError as e:
            st.error(f"Login failed: {e}")
