# frontend/streamlit_app.py
import os
import sys
import threading
import time
from typing import List

# add repo root to path so trading_engine & utils imports work
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from trading_engine.session import SessionManager, SessionError
from trading_engine.api_client import APIClient
from trading_engine.websocket import WebSocketManager
from trading_engine.marketdata import MarketDataService
from trading_engine.portfolio import PortfolioManager
from trading_engine.symbols import update_master_symbols, symbol_lookup, load_nse_cash

st.set_page_config(page_title="Definedge — Dashboard", layout="wide")
st.title("Definedge — Live Dashboard (Phase-1)")

# -------------------------
# Helpers
# -------------------------
def init_session_state():
    if "session_mgr" not in st.session_state:
        st.session_state.session_mgr = SessionManager()
    if "api_client" not in st.session_state:
        st.session_state.api_client = None
    if "order_manager" not in st.session_state:
        st.session_state.order_manager = None
    if "ws_mgr" not in st.session_state:
        st.session_state.ws_mgr = None
    if "marketdata" not in st.session_state:
        st.session_state.marketdata = None
    if "portfolio_mgr" not in st.session_state:
        st.session_state.portfolio_mgr = None

def start_ws_in_background(ws_mgr: WebSocketManager):
    """Start WS in a background thread (non-blocking)."""
    def runner():
        try:
            ws_mgr.start()
        except Exception as e:
            st.error(f"WS start failed: {e}")
    t = threading.Thread(target=runner, daemon=True)
    t.start()
    return t

def subscribe_tokens_from_holdings(ws_mgr: WebSocketManager, holdings_df: pd.DataFrame) -> List[str]:
    """
    Build token keys list like NSE|<token> from holdings dataframe and subscribe.
    Returns list of keys subscribed.
    """
    keys = []
    if holdings_df is None or holdings_df.empty:
        return keys
    for _, row in holdings_df.iterrows():
        token = str(row.get("token") or row.get("token").iloc[0] if "token" in row else "")
        exchange = row.get("exchange") or "NSE"
        if token:
            keys.append(f"{exchange}|{token}")
    if keys:
        ws_mgr.subscribe_touchline(keys)
    return keys

# -------------------------
# Initialize
# -------------------------
init_session_state()

# Sidebar: credential inputs (can use .streamlit/secrets.toml instead)
st.sidebar.header("Credentials")
api_token_in = st.sidebar.text_input("INTEGRATE_API_TOKEN", type="password")
api_secret_in = st.sidebar.text_input("INTEGRATE_API_SECRET", type="password")
totp_secret_in = st.sidebar.text_input("TOTP_SECRET (optional)", type="password")

# Provide quick actions for symbol master & history
st.sidebar.markdown("---")
if st.sidebar.button("Download/Refresh NSE Master (NSE Cash)"):
    with st.spinner("Downloading NSE master..."):
        try:
            res = update_master_symbols(nse_cash=True, nse_fno=False)
            st.sidebar.success(f"Master updated: {res}")
        except Exception as e:
            st.sidebar.error(f"Master download failed: {e}")

st.sidebar.markdown("Run from project root so `data/` folder is created automatically.")

# -------------------------
# Login / Session area (Top)
# -------------------------
st.subheader("Login / Session")
col1, col2, col3 = st.columns([2,2,1])

with col1:
    st.write("Login to Definedge (Step1/Step2 via API).")
    if st.button("Use sidebar credentials & Login"):
        # populate session manager with sidebar values (only if provided)
        if api_token_in:
            st.session_state.session_mgr.api_token = api_token_in
        if api_secret_in:
            st.session_state.session_mgr.api_secret = api_secret_in
        if totp_secret_in:
            st.session_state.session_mgr.totp_secret = totp_secret_in
        try:
            resp = st.session_state.session_mgr.login(otp=None, prefer_totp=True)
            st.success("Login successful")
            # build API client & services
            client = st.session_state.session_mgr.build_client()
            st.session_state.api_client = client
            st.session_state.marketdata = MarketDataService(api_client=client)  # ws to be attached later
            st.session_state.portfolio_mgr = PortfolioManager(api_client=client, marketdata=st.session_state.marketdata)
        except Exception as e:
            st.error(f"Login failed: {e}")

with col2:
    if st.session_state.api_client:
        ac = st.session_state.api_client
        st.markdown(f"**Logged in UID:** `{ac.uid}`")
        st.markdown(f"**Have API session key:** `{bool(ac.api_session_key)}`")
        st.markdown(f"**Have susertoken:** `{bool(ac.susertoken)}`")
    else:
        st.info("Not logged in. Please login with credentials.")

with col3:
    # WS quick control
    if st.session_state.api_client and st.session_state.api_client.susertoken:
        if st.session_state.ws_mgr is None:
            if st.button("Start WebSocket"):
                try:
                    ws = WebSocketManager(uid=st.session_state.api_client.uid, actid=st.session_state.api_client.uid, susertoken=st.session_state.api_client.susertoken)
                    st.session_state.ws_mgr = ws
                    start_ws_in_background(ws)
                    # attach ws to marketdata service
                    st.session_state.marketdata = MarketDataService(api_client=st.session_state.api_client, ws_mgr=ws)
                    st.success("WS start requested")
                except Exception as e:
                    st.error(f"WS start failed: {e}")
        else:
            if st.button("Stop WebSocket"):
                try:
                    st.session_state.ws_mgr.stop()
                    st.session_state.ws_mgr = None
                    st.success("WS stopped")
                except Exception as e:
                    st.error(f"WS stop failed: {e}")

st.markdown("---")

# -------------------------
# Main pages: simple nav for now
# -------------------------
page = st.radio("Open page:", ["Portfolio", "Orders (stub)", "Place Order (stub)", "Historical (tools)"], horizontal=True)

# -------------------------
# PAGE: Portfolio
# -------------------------
if page == "Portfolio":
    st.header("Portfolio Dashboard")
    if not st.session_state.portfolio_mgr:
        st.info("Login to load portfolio.")
    else:
        pm: PortfolioManager = st.session_state.portfolio_mgr

        # controls
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            if st.button("Refresh Holdings & Positions"):
                # simple refresh triggers below
                st.session_state._holdings_df = pm.fetch_holdings_table()
                st.session_state._positions_df = pm.fetch_positions_table()
        with c2:
            if st.button("Subscribe holdings tokens to WS"):
                if st.session_state.ws_mgr is None:
                    st.warning("Start WebSocket first.")
                else:
                    hf = st.session_state._holdings_df if st.session_state.get("_holdings_df") is not None else pm.fetch_holdings_table()
                    keys = []
                    # build keys NSE|token per row
                    for _, r in hf.iterrows():
                        tok = r.get("token")
                        exch = r.get("exchange", "NSE")
                        if tok:
                            keys.append(f"{exch}|{tok}")
                    if keys:
                        st.session_state.ws_mgr.subscribe_touchline(keys)
                        st.success(f"Subscribed {len(keys)} tokens.")
                    else:
                        st.info("No tokens available to subscribe (master mapping may be missing).")
        with c3:
            if st.button("Auto-refresh + subscribe (recommended)"):
                # refresh then subscribe
                st.session_state._holdings_df = pm.fetch_holdings_table()
                st.session_state._positions_df = pm.fetch_positions_table()
                hf = st.session_state._holdings_df
                keys = []
                for _, r in hf.iterrows():
                    tok = r.get("token")
                    exch = r.get("exchange", "NSE")
                    if tok:
                        keys.append(f"{exch}|{tok}")
                if st.session_state.ws_mgr and keys:
                    st.session_state.ws_mgr.subscribe_touchline(keys)
                    st.success(f"Refreshed & subscribed {len(keys)} tokens.")
                else:
                    st.info("Refreshed. Start WS then subscribe.")

        # Data fetch (use cached in session_state if exists)
        holdings_df = st.session_state.get("_holdings_df") or pm.fetch_holdings_table()
        positions_df = st.session_state.get("_positions_df") or pm.fetch_positions_table()

        # Summary
        summary = pm.portfolio_summary()
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Total Invested", f"₹ {summary['total_invested']:.2f}")
        col_b.metric("Current Value", f"₹ {summary['total_current_value']:.2f}")
        col_c.metric("Today P&L", f"₹ {summary['todays_pnl']:.2f}")
        col_d.metric("Overall Unrealized", f"₹ {summary['total_unrealized_pnl']:.2f}")

        st.markdown("### Holdings")
        if holdings_df is None or holdings_df.empty:
            st.info("No holdings returned from API.")
        else:
            # format numeric columns
            df = holdings_df.copy()
            # show LTP source tooltip if available
            st.dataframe(df, use_container_width=True)

            # charts
            try:
                # pie: capital allocation by invested
                fig1, ax1 = plt.subplots(figsize=(5,4))
                labels = df["symbol"].astype(str).tolist()
                sizes = df["invested"].astype(float).tolist()
                if sum(sizes) > 0:
                    ax1.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140)
                    ax1.axis('equal')
                    st.pyplot(fig1)
                # bar: unrealized pnl
                fig2, ax2 = plt.subplots(figsize=(7,4))
                ax2.bar(df["symbol"].astype(str).tolist(), df["unrealized_pnl"].astype(float).tolist())
                ax2.set_title("Unrealized P&L per symbol")
                ax2.set_ylabel("₹")
                plt.xticks(rotation=45, ha='right')
                st.pyplot(fig2)
            except Exception as e:
                st.write("Charting failed:", e)

        st.markdown("### Positions")
        if positions_df is None or positions_df.empty:
            st.info("No positions returned.")
        else:
            st.dataframe(positions_df, use_container_width=True)

# -------------------------
# PAGE: Orders stub
# -------------------------
elif page == "Orders (stub)":
    st.header("Orders & Trades (coming soon)")
    st.info("Order Book, Trade Book and GTT UI will be added next. For now use logs / API directly.")

# -------------------------
# PAGE: Place Order stub
# -------------------------
elif page == "Place Order (stub)":
    st.header("Place Order (stub)")
    st.info("Interactive order entry UI will be added in next iteration. For now use your existing place order flow via API.")

# -------------------------
# PAGE: Historical tools
# -------------------------
elif page == "Historical (tools)":
    st.header("Historical Data tools")
    st.write("Download or refresh historical data for a given token (NSE only).")
    token_inp = st.text_input("Enter NSE token (e.g. 22 for NIFTY)")
    lookback = st.number_input("Lookback days if new (default ~548)", min_value=30, value=548)
    if st.button("Download/Refresh historical for token"):
        if not st.session_state.api_client:
            st.error("Login first to get API session key.")
        else:
            try:
                from trading_engine.historical import update_daily_history_nse
                df = update_daily_history_nse(api_session_key=st.session_state.api_client.api_session_key, token=token_inp, lookback_days=lookback)
                st.success("Historical update finished.")
                st.write(df.tail(5))
            except Exception as e:
                st.error(f"Historical update failed: {e}")

st.markdown("---")
st.caption("Phase-1 dashboard. Next: full Orders UI, modify/cancel, watchlists, charts & OCO/TSL orchestration.")
