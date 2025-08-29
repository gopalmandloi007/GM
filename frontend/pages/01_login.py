import sys
import os
import streamlit as st

# 🔧 Add project root to sys.path (fix for ModuleNotFoundError)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from trading_engine.session import SessionManager, SessionError


def login_page():
    st.title("🔑 Login to Trading Dashboard")

    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    totp_secret = st.text_input("TOTP Secret (if enabled)", type="password")

    if st.button("Login"):
        try:
            session_manager = SessionManager(api_key, api_secret, totp_secret)
            session = session_manager.create_session()

            # Save session in Streamlit session state
            st.session_state["session"] = session
            st.success("✅ Login successful! Go to other pages from sidebar.")

        except SessionError as e:
            st.error(f"❌ Login failed: {str(e)}")


if __name__ == "__main__":
    login_page()
