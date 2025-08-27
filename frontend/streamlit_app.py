# frontend/streamlit_app.py

# --- Path fix for project_root imports ---
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# --- Standard imports ---
import streamlit as st
from datetime import datetime

# --- Trading engine imports ---
from trading_engine.session import SessionManager, SessionError
from trading_engine.api_client import APIClient
from trading_engine.websocket import WebSocketManager

# --- Initialize session manager ---
session_mgr = SessionManager()

# --- Streamlit UI ---
st.set_page_config(page_title="Definedge Trading Demo", layout="wide")

st.title("📈 Definedge Trading Bot Demo")

# --- Login Section ---
st.header("Step 1: Login / Authentication")
if "api_session_key" not in st.session_state:
    api_token = st.text_input("API Token", type="password")
    api_secret = st.text_input("API Secret", type="password")
    totp_secret = st.text_input("TOTP Secret", type="password")

    if st.button("Login"):
        try:
            login_response = session_mgr.login(
                api_token=api_token,
                api_secret=api_secret,
                totp_secret=totp_secret
            )
            st.session_state.api_session_key = login_response["api_session_key"]
            st.session_state.susertoken = login_response["susertoken"]
            st.success("Login successful!")
        except SessionError as e:
            st.error(f"Login failed: {e}")

# --- Display account info if logged in ---
if "api_session_key" in st.session_state:
    st.header("Account Info")
    st.json({
        "api_session_key": st.session_state.api_session_key,
        "susertoken": st.session_state.susertoken
    })

# --- Holdings / Positions Section ---
st.header("📊 Holdings & Positions")
if "api_session_key" in st.session_state:
    client = APIClient(session_key=st.session_state.api_session_key)
    try:
        holdings = client.get_holdings()
        positions = client.get_positions()
        st.subheader("Holdings")
        st.dataframe(holdings)
        st.subheader("Positions")
        st.dataframe(positions)
    except Exception as e:
        st.error(f"Failed to fetch holdings/positions: {e}")

# --- WebSocket Live Updates ---
st.header("💹 Live Market Updates")
if "susertoken" in st.session_state:
    ws_mgr = WebSocketManager(
        uid="your_uid_here",
        actid="your_actid_here",
        susertoken=st.session_state.susertoken
    )
    if st.button("Connect WebSocket"):
        ws_mgr.connect()
        st.success("WebSocket connected. Live updates will appear in console/logs.")

# --- Orders Section ---
st.header("📝 Orders")
if "api_session_key" in st.session_state:
    st.write("Order operations will be implemented here (OCO, TSL, Regular orders).")

# --- Historical Data Section ---
st.header("🕰️ Historical Data")
st.write("Historical data fetch and display will be implemented here.")
