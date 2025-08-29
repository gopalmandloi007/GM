# frontend/pages/01_login.py
import streamlit as st
from trading_engine.session import SessionManager, SessionError
from trading_engine.marketdata import MarketDataService
from trading_engine.websocket import WebSocketManager
from trading_engine.portfolio import PortfolioManager

def app():
    st.header("🔐 Login & Session")
    if "session_mgr" not in st.session_state:
        st.session_state.session_mgr = SessionManager()
    sm = st.session_state.session_mgr

    api_token = st.text_input("INTEGRATE_API_TOKEN", type="password")
    api_secret = st.text_input("INTEGRATE_API_SECRET", type="password")
    totp = st.text_input("TOTP_SECRET (optional)", type="password")
    otp = st.text_input("OTP (if using manual OTP)")

    if st.button("Login (prefer TOTP)"):
        try:
            if api_token:
                sm.api_token = api_token
            if api_secret:
                sm.api_secret = api_secret
            if totp:
                sm.totp_secret = totp
            resp = sm.login(otp=otp or None, prefer_totp=True)
            st.success("Login successful")
            client = sm.build_client()
            st.session_state.api_client = client
            # prepare marketdata + portfolio placeholders
            st.session_state.marketdata = MarketDataService(api_client=client)
            st.session_state.portfolio_mgr = PortfolioManager(api_client=client, marketdata=st.session_state.marketdata)
        except SessionError as e:
            st.error(f"Login failed: {e}")
        except Exception as e:
            st.error(f"Login error: {e}")

    # WS control
    st.markdown("---")
    if st.session_state.get("api_client"):
        client = st.session_state.api_client
        st.write(f"Logged in UID: {client.uid}")
        if st.button("Start WebSocket"):
            ws = WebSocketManager(uid=client.uid, actid=client.uid, susertoken=client.susertoken)
            st.session_state.ws_mgr = ws
            try:
                ws.start()
                st.success("WS started (background)")
                # attach to marketdata
                st.session_state.marketdata = MarketDataService(api_client=client, ws_mgr=ws)
                st.session_state.portfolio_mgr = PortfolioManager(api_client=client, marketdata=st.session_state.marketdata)
            except Exception as e:
                st.error(f"WS start failed: {e}")
