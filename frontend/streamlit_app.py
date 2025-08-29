import streamlit as st
import pandas as pd
from trading_engine.session import SessionManager
from trading_engine.holdings import get_holdings
from trading_engine.positions import get_positions
from trading_engine.orders import get_orders
from trading_engine.trades import get_trades

# ---------------------------
# Load credentials from secrets
# ---------------------------
API_TOKEN = st.secrets["DEFINEDGE_API_TOKEN"]
API_SECRET = st.secrets["DEFINEDGE_API_SECRET"]
TOTP_SECRET = st.secrets.get("DEFINEDGE_TOTP_SECRET")

# ---------------------------
# Create session
# ---------------------------
st.set_page_config(page_title="Definedge Trading Dashboard", layout="wide")
st.sidebar.title("📊 Trading Dashboard")

session = SessionManager(API_TOKEN, API_SECRET, TOTP_SECRET)

# Sidebar navigation
page = st.sidebar.radio("Navigate", ["🏠 Home", "📑 Holdings", "📘 Positions", "📝 Orders", "🔄 Trades"])


# ---------------------------
# Page: Home
# ---------------------------
if page == "🏠 Home":
    st.title("Welcome to Definedge Trading Dashboard")
    st.write("Use the sidebar to navigate to different sections.")
    st.info("⚠️ Demo UI. Be careful while placing real orders.")


# ---------------------------
# Page: Holdings
# ---------------------------
elif page == "📑 Holdings":
    st.title("📑 Holdings Overview")
    if st.button("Fetch Holdings"):
        data = get_holdings(session)
        if data and "data" in data:
            holdings_list = []
            for item in data["data"]:
                nse_symbol = next((s for s in item["tradingsymbol"] if s["exchange"] == "NSE"), {})
                holdings_list.append({
                    "Symbol": nse_symbol.get("tradingsymbol", ""),
                    "ISIN": nse_symbol.get("isin", ""),
                    "DP Qty": item["dp_qty"],
                    "Used Qty": item["holding_used"],
                    "Trade Qty": item["trade_qty"],
                    "Avg Buy Price": item["avg_buy_price"],
                    "Sell Amount": item["sell_amt"],
                    "Haircut": item["haircut"]
                })
            df = pd.DataFrame(holdings_list)
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("⚠️ No holdings data found.")


# ---------------------------
# Page: Positions
# ---------------------------
elif page == "📘 Positions":
    st.title("📘 Positions Overview")
    if st.button("Fetch Positions"):
        data = get_positions(session)
        if data and "data" in data:
            df = pd.DataFrame(data["data"])
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("⚠️ No positions data found.")


# ---------------------------
# Page: Orders
# ---------------------------
elif page == "📝 Orders":
    st.title("📝 Orders Overview")
    if st.button("Fetch Orders"):
        data = get_orders(session)
        if data and "data" in data:
            df = pd.DataFrame(data["data"])
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("⚠️ No orders data found.")


# ---------------------------
# Page: Trades
# ---------------------------
elif page == "🔄 Trades":
    st.title("🔄 Trades Overview")
    if st.button("Fetch Trades"):
        data = get_trades(session)
        if data and "data" in data:
            df = pd.DataFrame(data["data"])
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("⚠️ No trades data found.")
