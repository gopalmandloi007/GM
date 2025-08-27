# frontend/streamlit_app.py
import streamlit as st
from trading_engine.session import SessionManager, SessionError
from trading_engine.api_client import APIClient
from trading_engine.websocket import WSManager
from trading_engine.orders import OrdersClient
from trading_engine.orders.oco import OCOManager
from trading_engine.portfolio import PortfolioManager
from trading_engine.utils import init_db_schema, get_sqlite_conn

st.set_page_config(page_title="Definedge Live Demo", layout="wide")
st.title("Definedge Live Demo (Holdings, WS, Orders, OCO)")

# secrets loader
def get_secret(key):
    if key in st.secrets:
        return st.secrets[key]
    import os
    return os.getenv(key)

api_token = get_secret("INTEGRATE_API_TOKEN")
api_secret = get_secret("INTEGRATE_API_SECRET")
totp_secret = get_secret("TOTP_SECRET")

# ensure DB schema
conn = get_sqlite_conn()
init_db_schema(conn)

# init session manager
if "sm" not in st.session_state:
    try:
        st.session_state.sm = SessionManager(api_token=api_token, api_secret=api_secret, totp_secret=totp_secret)
    except Exception as e:
        st.error(f"Session init error: {e}")
        st.stop()

sm: SessionManager = st.session_state.sm

st.sidebar.subheader("Credentials")
st.sidebar.write(f"API token present: {'✅' if api_token else '❌'}")
st.sidebar.write(f"TOTP present: {'✅' if totp_secret else '❌'}")

# Initialize OrdersClient and OCOManager first (without WS)
orders_client = OrdersClient(APIClient(sm))
if "oco" not in st.session_state:
    st.session_state.oco = OCOManager(orders_client=orders_client, ws_manager=None)

oco: OCOManager = st.session_state.oco

# WS manager: pass oco_manager so WS forwards order updates to OCO
if "ws" not in st.session_state:
    st.session_state.ws = WSManager(sm, oco_manager=oco)
    # make sure OCO has a reference to ws for TSL operations
    oco.ws = st.session_state.ws

ws = st.session_state.ws

# ---- Login / session area ----
st.header("Login / Session")
col1, col2 = st.columns(2)
with col1:
    if st.button("Step 1: Request OTP"):
        try:
            d = sm.step1_request_otp()
            st.success("OTP requested (check mobile/email)")
            st.session_state["otp_token"] = d.get("otp_token")
            if d.get("message"):
                st.info(d.get("message"))
        except SessionError as e:
            st.error(f"Step1 failed: {e}")

with col2:
    otp_input = st.text_input("Enter OTP (leave blank to use TOTP)", type="password")
    if st.button("Step 2: Verify OTP"):
        try:
            otp_token = st.session_state.get("otp_token")
            if not otp_token:
                st.warning("Run Step 1 first.")
            else:
                d = sm.step2_verify_otp(otp_token, otp_input or None)
                st.success("Login successful")
                st.json({"uid": sm.uid, "api_session_key_present": bool(sm.api_session_key)})
        except SessionError as e:
            st.error(f"Step2 failed: {e}")

st.divider()
st.subheader("WebSocket (start/subscribe)")

colws1, colws2 = st.columns(2)
with colws1:
    if st.button("Start WS"):
        try:
            ws.start()
            st.success("WS started (connect message sent).")
        except Exception as e:
            st.error(f"WS start error: {e}")
with colws2:
    sub_list = st.text_input("Subscribe tokens (EX|TOKEN#EX|TOKEN...)", value="")
    if st.button("Subscribe tokens"):
        tokens = [t.strip() for t in sub_list.split("#") if t.strip()]
        try:
            ws.subscribe_touchline(tokens)
            st.success(f"Subscribed {len(tokens)}")
        except Exception as e:
            st.error(f"Subscribe error: {e}")

st.divider()
st.subheader("OCO Groups")
# list groups
try:
    groups = oco.list_groups()
    if not groups:
        st.info("No OCO groups found.")
    else:
        for g in groups:
            gid = g["group_id"]
            col_a, col_b = st.columns([3,1])
            with col_a:
                st.markdown(f"**Group {gid}** — UUID: {g.get('uuid')} — Status: {g.get('status')}")
                st.json({"metadata": g.get("metadata"), "parent_order_id": g.get("parent_order_id")})
                children = oco.list_children(gid)
                st.markdown("Children:")
                for c in children:
                    st.write(f"- child_id={c['child_id']}, role={c['role']}, qty={c['qty']}, price={c['price']}, order_id={c['order_id']}, status={c['status']}")
            with col_b:
                if st.button(f"Cancel Group {gid}", key=f"cancel_{gid}"):
                    try:
                        res = oco.cancel_group(gid)
                        st.success(f"Cancel requested for group {gid}")
                        st.json(res)
                    except Exception as e:
                        st.error(f"Cancel failed: {e}")
except Exception as e:
    st.error(f"OCO list error: {e}")

st.divider()
st.subheader("Live Holdings (uses WS LTP cache)")
if st.button("Refresh holdings (attach LTP)"):
    try:
        pm = PortfolioManager(APIClient(sm), ws)
        live = pm.get_live_holdings_with_pnl()
        st.write("Holdings with live LTP and unreal P&L:")
        st.table(live["holdings"])
    except Exception as e:
        st.error(f"Holdings error: {e}")

st.divider()
st.subheader("Place Order (demo)")
orders = OrdersClient(APIClient(sm))
with st.form("order_form"):
    exchange = st.selectbox("Exchange", ["NSE", "NFO", "BSE", "MCX"])
    tradingsymbol = st.text_input("Tradingsymbol", value="NIFTY23FEB23F")
    qty = st.text_input("Quantity", "1")
    price_type = st.selectbox("Price Type", ["MARKET", "LIMIT", "SL"])
    price = st.text_input("Price", "0")
    product_type = st.selectbox("Product Type", ["NORMAL", "INTRADAY"])
    order_type = st.selectbox("Order Type", ["BUY", "SELL"])
    submitted = st.form_submit_button("Place Order")
    if submitted:
        payload = {
            "price_type": price_type,
            "tradingsymbol": tradingsymbol,
            "quantity": qty,
            "price": price,
            "product_type": product_type,
            "order_type": order_type,
            "exchange": exchange
        }
        try:
            resp = orders.place_order(payload)
            st.success("Order placed (response below)")
            st.json(resp)
        except Exception as e:
            st.error(f"Order failed: {e}")
