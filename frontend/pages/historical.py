# frontend/pages/06_historical.py
import streamlit as st
from trading_engine.api_client import APIClient
import pandas as pd
from trading_engine.historical import path_hist_day_nse
from trading_engine.session import SessionManager

def app():
    st.header("🕰️ Historical Tools")
    token = st.text_input("Enter NSE token (token from master file)")
    client = st.session_state.get("api_client")
    if st.button("Download last 5 years (example)"):
        if not client:
            st.error("Login first")
            return
        # example: build from date strings; broker expects ddMMyyyyHHmm in docs, but here we fetch/call API wrapper
        st.info("Download not implemented in UI; use backend helper if needed.")
    # show local file if exists
    if token:
        p = path_hist_day_nse(token)
        try:
            df = pd.read_csv(p)
            st.dataframe(df.tail(20))
        except Exception:
            st.info("No historical file found for this token locally.")
