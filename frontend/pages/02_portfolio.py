# frontend/pages/02_portfolio.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from trading_engine.session import SessionManager
from trading_engine.marketdata import MarketDataService
from trading_engine.websocket import WebSocketManager
from trading_engine.portfolio import PortfolioManager

def app():
    st.header("Portfolio Dashboard")

    # session manager must already be used via Login page; fallback make new
    if "session_mgr" not in st.session_state:
        st.session_state.session_mgr = SessionManager()

    sm = st.session_state.session_mgr

    if "api_client" not in st.session_state:
        st.info("Please login from Login page first.")
        return

    client = st.session_state.api_client
    # ensure marketdata & portfolio_mgr exist
    if "ws_mgr" not in st.session_state:
        st.session_state.ws_mgr = None
    if "marketdata" not in st.session_state:
        st.session_state.marketdata = MarketDataService(api_client=client, ws_mgr=st.session_state.ws_mgr)
    if "portfolio_mgr" not in st.session_state:
        st.session_state.portfolio_mgr = PortfolioManager(api_client=client, marketdata=st.session_state.marketdata)

    pm: PortfolioManager = st.session_state.portfolio_mgr

    # Controls row
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        if st.button("Refresh"):
            st.session_state.holdings = pm.fetch_holdings_table()
            st.session_state.positions = pm.fetch_positions_table()
    with c2:
        if st.button("Subscribe holdings tokens"):
            hv = st.session_state.get("holdings") or pm.fetch_holdings_table()
            keys = []
            for _, r in hv.iterrows():
                tok = r.get("token")
                exch = r.get("exchange","NSE")
                if tok:
                    keys.append(f"{exch}|{tok}")
            if not keys:
                st.info("No tokens to subscribe. Ensure master mapping exists.")
            else:
                if not st.session_state.ws_mgr:
                    st.warning("Start websocket from Login page or launcher first.")
                else:
                    st.session_state.ws_mgr.subscribe_touchline(keys)
                    st.success(f"Subscribed {len(keys)} tokens")

    # data load
    holdings = st.session_state.get("holdings") or pm.fetch_holdings_table()
    positions = st.session_state.get("positions") or pm.fetch_positions_table()

    # summary metrics
    summary = pm.portfolio_summary()
    cols = st.columns(4)
    cols[0].metric("Total Invested", f"₹ {summary['total_invested']:.2f}")
    cols[1].metric("Current Value", f"₹ {summary['total_current_value']:.2f}")
    cols[2].metric("Today P&L", f"₹ {summary['todays_pnl']:.2f}")
    cols[3].metric("Overall Unrlz", f"₹ {summary['overall_unrealized']:.2f}")

    st.subheader("Holdings")
    if holdings is None or holdings.empty:
        st.info("No holdings returned.")
    else:
        st.dataframe(holdings, use_container_width=True)

        # small charts side-by-side
        a, b = st.columns([1,1])
        with a:
            try:
                fig1, ax1 = plt.subplots(figsize=(4,3))
                labels = holdings["symbol"].astype(str).tolist()
                sizes = holdings["invested"].astype(float).tolist()
                if sum(sizes) > 0:
                    ax1.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140)
                    ax1.axis('equal')
                    st.pyplot(fig1)
                else:
                    st.info("No invested amounts to show pie.")
            except Exception as e:
                st.write("Pie chart error:", e)
        with b:
            try:
                fig2, ax2 = plt.subplots(figsize=(6,3))
                ax2.bar(holdings["symbol"].astype(str).tolist(), holdings["overall_unrealized"].astype(float).tolist())
                ax2.set_title("Unrealized P&L")
                ax2.set_ylabel("₹")
                plt.xticks(rotation=45, ha='right')
                st.pyplot(fig2)
            except Exception as e:
                st.write("Bar chart error:", e)

    st.subheader("Positions")
    if positions is None or positions.empty:
        st.info("No positions returned.")
    else:
        st.dataframe(positions, use_container_width=True)
