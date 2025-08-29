import streamlit as st
from trading_engine.session import SessionManager
from trading_engine.holdings import get_holdings
from trading_engine.positions import get_positions
from trading_engine.orders import get_orderbook, place_order
from trading_engine.trades import get_trades
import pandas as pd

st.set_page_config(page_title="Definedge Trading Engine", layout="wide")

st.title("📈 Definedge Trading Engine - Dashboard")

# Session
if "session" not in st.session_state:
    st.session_state.session = None

if st.session_state.session is None:
    st.info("🔑 Creating session from Streamlit secrets...")
    token = st.secrets["DEFINEDGE_API_TOKEN"]
    secret = st.secrets["DEFINEDGE_API_SECRET"]
    totp = st.secrets.get("DEFINEDGE_TOTP_SECRET", None)

    st.session_state.session = SessionManager(api_token=token, api_secret=secret, totp_secret=totp)

session = st.session_state.session

tab1, tab2, tab3, tab4 = st.tabs(["Holdings", "Positions", "Orders", "Trades"])

with tab1:
    st.subheader("📊 Holdings")
    data = get_holdings(session)
    if data:
        df = pd.json_normalize(data)
        st.dataframe(df, use_container_width=True)

with tab2:
    st.subheader("📈 Positions")
    data = get_positions(session)
    if data:
        df = pd.json_normalize(data)
        st.dataframe(df, use_container_width=True)

with tab3:
    st.subheader("📑 Orders")
    data = get_orderbook(session)
    if data:
        df = pd.json_normalize(data)
        st.dataframe(df, use_container_width=True)

    st.markdown("### ➕ Place Order")
    symbol = st.text_input("Symbol", "HINDWAREAP-EQ")
    qty = st.number_input("Quantity", 1, 1000, 1)
    side = st.radio("Side", ["BUY", "SELL"])
    if st.button("Place Order"):
        res = place_order(session, symbol=symbol, qty=qty, side=side)
        st.json(res)

with tab4:
    st.subheader("💹 Trades")
    data = get_trades(session)
    if data:
        df = pd.json_normalize(data)
        st.dataframe(df, use_container_width=True)
