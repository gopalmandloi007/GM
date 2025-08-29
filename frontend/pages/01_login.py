# frontend/pages/01_login.py

import sys
import os
import streamlit as st

# 🔹 Ensure parent folder is in Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 🔹 Import SessionManager and SessionError safely
from trading_engine.session import SessionManager, SessionError

def login_page():
    st.title("Login to Trading Dashboard")

    api_key = st.text_input("API Key")
    api_secret = st.text_input("API Secret", type="password")
    totp_secret = st.text_input("TOTP Secret (Optional)", type="password")

    if st.button("Login"):
        try:
            session_manager = SessionManager(api_key, api_secret, totp_secret)
            session_manager.authenticate()  # Assuming you have an authenticate method
            st.success("Login successful!")
            st.session_state['session_manager'] = session_manager
        except SessionError as e:
            st.error(f"Login failed: {str(e)}")
        except Exception as e:
            st.error(f"Unexpected error: {str(e)}")

# Run the login page if this file is executed directly
if __name__ == "__main__":
    login_page()
