# streamlit_app.py

import sys
import os

# ----------------------------
# Ensure project root is in Python path
# ----------------------------
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ----------------------------
# Imports from trading_engine
# ----------------------------
from trading_engine.session import SessionManager, SessionError
from trading_engine.api_client import APIClient
from trading_engine.websocket import WebSocketManager
from trading_engine.orders import OrderManager
from trading_engine.portfolio import PortfolioManager

# ----------------------------
# Streamlit imports
# ----------------------------
import streamlit as st
import time
import json

# ----------------------------
# Example Streamlit App Start
# ----------------------------
st.title("Definedge Trading Demo")

st.write("Credentials")
api_token_present = True  # Example: replace with your check
totp_present = True

st.write(f"API token present: {'✅' if api_token_present else '❌'}")
st.write(f"TOTP present: {'✅' if totp_present else '❌'}")

# Session management example
session_mgr = SessionManager()

otp_input = st.text_input("Enter OTP (leave blank to use TOTP)", type="password")
login_btn = st.button("Login / Session")

if login_btn:
    try:
        session_mgr.login(otp=otp_input)
        st.success("Login successful")
        st.json({
            "uid": session_mgr.uid,
            "api_session_key_present": session_mgr.api_session_key is not None
        })
    except SessionError as e:
        st.error(f"Login failed: {str(e)}")

# ----------------------------
# WebSocket example placeholder
# ----------------------------
if st.button("Start WebSocket"):
    st.info("WebSocket started (placeholder)")

# ----------------------------
# Holdings placeholder
# ----------------------------
st.subheader("Live Holdings")
st.write("Holdings will appear here once implemented.")
