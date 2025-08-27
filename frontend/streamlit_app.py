# frontend/streamlit_app.py

import streamlit as st
import threading
import time
from trading_engine.session import SessionManager, SessionError
from trading_engine.websocket import WSClient
from trading_engine.orders import OCOManager

# ----------------------
# Streamlit App Config
# ----------------------
st.set_page_config(page_title="Definedge Trading Bot", layout="wide")

# ----------------------
# Sidebar - Login
# ----------------------
st.sidebar.title("Login / Session")

api_token = st.sidebar.text_input("API Token")
api_secret = st.sidebar.text_input("API Secret", type="password")
totp_code = st.sidebar.text_input("TOTP / OTP")

login_btn = st.sidebar.button("Login")

if "session" not in st.session_state:
    st.session_state.session = None

if login_btn:
    try:
        session = SessionManager(api_token, api_secret)
        session.login(otp_code=totp_code)
        st.session_state.session = session
        st.success("Login successful!")
    except SessionError as e:
        st.error(f"Login failed: {str(e)}")

# ----------------------
# WebSocket Setup
# ----------------------
if st.session_state.session:
    if "ws_client" not in st.session_state:
        st.session_state.ws_client = WSClient(
            uid=st.session_state.session.uid,
            actid=st.session_state.session.actid,
            susertoken=st.session_state.session.susertoken
        )
        ws_client = st.session_state.ws_client

        # Start websocket in background thread
        def start_ws():
            ws_client.connect()
            ws_client.run_forever()

        ws_thread = threading.Thread(target=start_ws, daemon=True)
        ws_thread.start()

# ----------------------
# Holdings Panel
# ----------------------
st.title("Holdings & Positions")
holdings_placeholder = st.empty()
positions_placeholder = st.empty()

def update_holdings_panel():
    while True:
        if st.session_state.session and st.session_state.ws_client:
            holdings_data = st.session_state.ws_client.get_holdings()
            positions_data = st.session_state.ws_client.get_positions()

            holdings_placeholder.dataframe(holdings_data)
            positions_placeholder.dataframe(positions_data)

        time.sleep(2)  # update interval

if st.session_state.session and "holdings_thread" not in st.session_state:
    holdings_thread = threading.Thread(target=update_holdings_panel, daemon=True)
    holdings_thread.start()
    st.session_state.holdings_thread = holdings_thread

# ----------------------
# OCO Panel
# ----------------------
st.subheader("OCO Orders / Trailing Stop Loss")

oco_manager = OCOManager(session=st.session_state.session)

oco_form = st.form("oco_form")
with oco_form:
    exchange = st.selectbox("Exchange", ["NSE", "BSE", "NFO", "MCX"])
    symbol = st.text_input("Trading Symbol")
    quantity = st.number_input("Quantity", min_value=1, value=1)
    target_price = st.number_input("Target Price", min_value=0.0, value=0.0)
    stoploss_price = st.number_input("Stop Loss Price", min_value=0.0, value=0.0)
    submit_oco = st.form_submit_button("Create OCO Group")

if submit_oco:
    try:
        group_id = oco_manager.create_group(
            exchange=exchange,
            symbol=symbol,
            quantity=quantity,
            target_price=target_price,
            stoploss_price=stoploss_price
        )
        st.success(f"OCO Group Created: {group_id}")
    except Exception as e:
        st.error(f"Failed to create OCO group: {str(e)}")

# Display existing OCO groups with cancel option
st.subheader("Existing OCO Groups")
oco_groups = oco_manager.get_all_groups()
for group in oco_groups:
    col1, col2 = st.columns([4,1])
    col1.write(f"Group ID: {group['id']} | Symbol: {group['symbol']} | Qty: {group['quantity']} | Status: {group['status']}")
    if col2.button(f"Cancel {group['id']}", key=f"cancel_{group['id']}"):
        try:
            oco_manager.cancel_group(group["id"])
            st.success(f"Cancelled OCO Group {group['id']}")
        except Exception as e:
            st.error(f"Failed to cancel group: {str(e)}")

# ----------------------
# Footer / Info
# ----------------------
st.info("Live update every 2 sec | WebSocket connected | OCO auto management active")
