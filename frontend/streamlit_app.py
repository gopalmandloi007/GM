# streamlit_app.py (SAFE demo with dry-run toggle + confirm)
import streamlit as st
from trading_engine import SessionManager, OrderManager, WebSocketManager, MarketDataService, set_default_client
import trading_engine as te
import time, json

st.set_page_config(page_title='Definedge Demo (Safe)', layout='wide')
st.title('Definedge Trading Engine — Demo (Safe)')

# Load secrets first (prefer .streamlit/secrets.toml)
api_token = st.secrets.get('DEFINEDGE_API_TOKEN') if st.secrets.get('DEFINEDGE_API_TOKEN') else None
api_secret = st.secrets.get('DEFINEDGE_API_SECRET') if st.secrets.get('DEFINEDGE_API_SECRET') else None
totp_secret = st.secrets.get('DEFINEDGE_TOTP_SECRET') if st.secrets.get('DEFINEDGE_TOTP_SECRET') else None

st.sidebar.header("Settings")
dry_run = st.sidebar.checkbox("Dry-run mode (do not call placeorder)", value=True)
auto_start_ws = st.sidebar.checkbox("Auto-start WebSocket after login", value=False)
show_raw_logs = st.sidebar.checkbox("Show raw API responses", value=False)

# Allow manual override if secrets not present
if not api_token:
    api_token = st.text_input("API token", value="")
if not api_secret:
    api_secret = st.text_input("API secret", value="", type="password")
if not totp_secret:
    totp_secret = st.text_input("TOTP secret (optional)", value="", type="password")

if 'client' not in st.session_state:
    st.session_state['client'] = None
if 'ws' not in st.session_state:
    st.session_state['ws'] = None

col1, col2 = st.columns([1,2])
with col1:
    st.header("Session")
    if st.button("Create Session"):
        if not api_token or not api_secret:
            st.error("Provide API token & secret (in secrets or inputs).")
        else:
            try:
                sm = SessionManager(api_token=api_token.strip(), api_secret=api_secret.strip(), totp_secret=(totp_secret or None))
                client = sm.create_session()
                st.session_state['client'] = client
                set_default_client(client)
                st.success("Session created.")
                st.write({"uid": client.uid, "susertoken_present": bool(client.susertoken)})
                if auto_start_ws and client.susertoken:
                    ws = WebSocketManager(uid=client.uid, actid=client.uid, susertoken=client.susertoken)
                    ws.start()
                    st.session_state['ws'] = ws
                    st.info("WebSocket auto-started.")
            except Exception as e:
                st.error(f"Login failed: {e}")

    if st.session_state['client']:
        if st.button("Start WebSocket"):
            try:
                client = st.session_state['client']
                if not client.susertoken:
                    st.warning("No susertoken in client — WebSocket may fail.")
                ws = WebSocketManager(uid=client.uid, actid=client.uid, susertoken=client.susertoken)
                ws.start()
                st.session_state['ws'] = ws
                st.success("WebSocket started.")
            except Exception as e:
                st.error(f"WS start failed: {e}")

        if st.session_state['ws']:
            if st.button("Stop WebSocket"):
                try:
                    st.session_state['ws'].stop()
                    st.session_state['ws'] = None
                    st.success("WebSocket stopped.")
                except Exception as e:
                    st.error(f"Stop WS failed: {e}")

with col2:
    st.header("Quick Actions")
    client = st.session_state.get('client')
    if client:
        cols = st.columns([1,1,1,1])
        if cols[0].button("Show Holdings"):
            try:
                holdings = client.get_holdings()
                st.write(holdings if show_raw_logs else {"count": len(holdings) if hasattr(holdings,'__len__') else 'unknown'})
            except Exception as e:
                st.error(f"Error fetching holdings: {e}")

        if cols[1].button("Show Positions"):
            try:
                positions = client.get_positions()
                st.write(positions if show_raw_logs else {"count": len(positions) if hasattr(positions,'__len__') else 'unknown'})
            except Exception as e:
                st.error(f"Error fetching positions: {e}")

        if cols[2].button("List Orders"):
            try:
                ords = client.list_orders()
                st.write(ords if show_raw_logs else {"count": len(ords.get('orders', ords) )})
            except Exception as e:
                st.error(f"List orders failed: {e}")

        if cols[3].button("List Trades"):
            try:
                trades = client.get_trades()
                st.write(trades if show_raw_logs else {"count": len(trades) if hasattr(trades,'__len__') else 'unknown'})
            except Exception as e:
                st.error(f"List trades failed: {e}")

        st.markdown("---")
        st.subheader("Place Order (safe)")

        with st.form("order_form"):
            tradingsymbol = st.text_input("Trading Symbol", value="RELIANCE")
            exchange = st.selectbox("Exchange", ["NSE","NFO","BSE"], index=0)
            qty = st.number_input("Quantity", value=1, min_value=1, step=1)
            side = st.selectbox("Side", ["BUY","SELL"], index=0)
            price_type = st.selectbox("Price Type", ["MARKET","LIMIT","SL","SL-M"], index=0)
            price = st.number_input("Price (0 for MARKET)", value=0.0, format="%.2f")
            trigger = st.number_input("Trigger Price (for SL)", value=0.0, format="%.2f")
            require_confirm = st.checkbox("I confirm this is intentional (enable real order)", value=False)
            submit = st.form_submit_button("Submit Order")

        if submit:
            om = OrderManager(client)
            payload_preview = {
                "tradingsymbol": tradingsymbol,
                "exchange": exchange,
                "quantity": int(qty),
                "price_type": price_type,
                "order_type": side,
                "price": float(price),
                "trigger_price": float(trigger) if trigger > 0 else None
            }
            st.write("Order payload preview:", payload_preview)

            if dry_run:
                st.info("DRY-RUN is enabled — order will NOT be sent. Use the toggle in the sidebar to disable dry-run.")
            else:
                if not require_confirm:
                    st.error("You must check the confirmation checkbox to allow a real order.")
                else:
                    try:
                        resp = om.place_order(
                            tradingsymbol=tradingsymbol,
                            exchange=exchange,
                            quantity=int(qty),
                            price_type=price_type,
                            side=side,
                            price=price if price > 0 else 0,
                            trigger_price=trigger if trigger > 0 else None
                        )
                        st.success("Order placed (response logged).")
                        if show_raw_logs:
                            st.write(resp)
                    except Exception as e:
                        st.error(f"Order failed: {e}")
    else:
        st.info("Create a session first to use actions.")

st.markdown("---")
st.caption("This is a demo. Keep dry-run on unless you want to place real orders.")
