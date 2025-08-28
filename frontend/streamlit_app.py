# frontend/streamlit_app.py
import sys, os, time, threading
# ensure project root in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from trading_engine.session import SessionManager, SessionError
from trading_engine.api_client import APIClient, SessionError as APIClientSessionError
from trading_engine.websocket import WebSocketManager
from trading_engine.symbols import autocomplete_symbols, download_master
from trading_engine.utils import setup_data_directories
from trading_engine.orders import OrderManager

# Ensure data dirs
setup_data_directories()

st.set_page_config(page_title="Definedge - Phase1", layout="wide")
st.title("Definedge — Live Monitor & Order Window (Phase-1)")

# Sidebar - secrets (prefer .streamlit/secrets.toml or env)
st.sidebar.header("Credentials & Controls")
api_token = st.sidebar.text_input("INTEGRATE_API_TOKEN", type="password")
api_secret = st.sidebar.text_input("INTEGRATE_API_SECRET", type="password")
totp_secret = st.sidebar.text_input("TOTP_SECRET (optional)", type="password")

sm = None
if "session_mgr" not in st.session_state:
    st.session_state.session_mgr = SessionManager(api_token=api_token, api_secret=api_secret, totp_secret=totp_secret)

session_mgr: SessionManager = st.session_state.session_mgr

# Login area
st.sidebar.subheader("Login")
otp = st.sidebar.text_input("Enter OTP (leave blank to use TOTP)", type="password")
if st.sidebar.button("Login"):
    try:
        resp = session_mgr.login(otp=otp, prefer_totp=True)
        st.sidebar.success("Login successful")
        st.sidebar.json({"uid": resp.get("uid"), "api_session_key_present": bool(resp.get("api_session_key"))})
        # Build API client and order manager
        client = session_mgr.build_client()
        st.session_state.api_client = client
        st.session_state.order_manager = OrderManager(client)
    except Exception as e:
        st.sidebar.error(f"Login failed: {e}")

st.sidebar.markdown("---")
st.sidebar.markdown("Make sure tokens are set in `.streamlit/secrets.toml` or environment variables.")
st.sidebar.markdown("Run `streamlit run frontend/streamlit_app.py` from project root.")

# Main UI: WS control + holdings + order window
col1, col2 = st.columns([2,1])

with col1:
    st.header("Holdings & Positions (REST + LTP from WS)")
    if "api_client" in st.session_state:
        client: APIClient = st.session_state.api_client
        # holdings & positions
        if st.button("Refresh Holdings/Positions"):
            try:
                holdings = client.get_holdings()
                positions = client.get_positions()
                st.subheader("Holdings")
                st.json(holdings)
                st.subheader("Positions")
                st.json(positions)
            except Exception as e:
                st.error(f"Holdings error: {e}")
    else:
        st.info("Login to fetch holdings/positions.")

    st.markdown("---")
    st.header("WebSocket - Live LTP")
    if "ws_mgr" not in st.session_state:
        st.session_state.ws_mgr = None

    if "api_client" in st.session_state and st.session_state.ws_mgr is None:
        client: APIClient = st.session_state.api_client
        if st.button("Start WebSocket"):
            try:
                ws = WebSocketManager(uid=client.uid, actid=client.uid, susertoken=client.susertoken)
                # start ws in thread
                def start_ws():
                    ws.start()
                t = threading.Thread(target=start_ws, daemon=True)
                t.start()
                st.session_state.ws_mgr = ws
                st.success("WebSocket start requested.")
            except Exception as e:
                st.error(f"WS start failed: {e}")

    if st.session_state.ws_mgr:
        st.write("WS subscription tokens:", list(st.session_state.ws_mgr.subscribed)[:10])
        st.write("LTP cache (sample):")
        # show first 8 entries
        sample = dict(list(st.session_state.ws_mgr.ltp_cache.items())[:8])
        st.json(sample)

with col2:
    st.header("Order Window (attractive input)")
    st.write("Type 3+ characters of symbol to autocomplete (from downloaded master files).")
    symbol_input = st.text_input("Symbol (type 3+ chars to autocomplete)")
    suggestions = []
    if len(symbol_input.strip()) >= 3:
        suggestions = autocomplete_symbols(symbol_input.strip(), limit=10)
    if suggestions:
        # show clickable suggestions
        for s,t in suggestions:
            if st.button(f"{s} | {t}", key=f"sugg-{s}"):
                symbol_input = s
                st.experimental_set_query_params(symbol=s)  # not necessary but helpful
    # fields
    exchange = st.selectbox("Exchange", ["NSE","BSE","NFO","MCX"])
    price_type = st.radio("Price Type", ["MARKET","LIMIT","SL","SL-M"], horizontal=False)
    qty = st.number_input("Quantity", min_value=1, value=1)
    product_type = st.selectbox("Product Type", ["NORMAL","INTRADAY"])
    order_type = st.selectbox("Order Type", ["BUY","SELL"])

    # show LTP if ws running and token known
    ltp_display = None
    if st.session_state.get("ws_mgr") and symbol_input:
        # master tokens are often numeric token not symbol; for basic show try fetch quotes via REST
        if "api_client" in st.session_state:
            client: APIClient = st.session_state.api_client
            try:
                # attempt a quotes call (some APIs require token not symbol)
                # Here we attempt using symbol as token — if fails, it's optional.
                q = client.get_quote(exchange, symbol_input)
                ltp_display = q
            except Exception:
                ltp = None
                # fallback to ws ltp cache: try common pattern EX|TOKEN - we don't have token mapping here so skip
                ltp = None
                ltp_display = {"note":"LTP not available for raw symbol via ws without token mapping."}
    else:
        ltp_display = {"info":"Start WS & select symbol/token to get LTP"}

    st.json(ltp_display)

    st.markdown("### Place Order")
    if st.button("Place Order"):
        if "order_manager" not in st.session_state:
            st.error("Login first to create order manager.")
        else:
            om: OrderManager = st.session_state.order_manager
            # Build payload - this assumes API accepts these keys; adapt if needed
            payload = {
                "price_type": price_type,
                "tradingsymbol": symbol_input,
                "quantity": str(qty),
                "price": "0" if price_type == "MARKET" else "0",  # if LIMIT, you should collect price field
                "product_type": product_type,
                "order_type": order_type,
                "exchange": exchange
            }
            try:
                resp = om.place_order(payload)
                st.success("Order placed")
                st.json(resp)
            except Exception as e:
                st.error(f"Order failed: {e}")

st.markdown("---")
st.info("Phase-1 base: monitoring + manual order placement. Later we'll add auto triggers, better token mapping, and OCO/TSL orchestration.")
