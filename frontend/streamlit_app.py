# streamlit_app.py
import os, sys
# Ensure project root is on path so local package (gm/trading_engine) imports work
ROOT = os.path.abspath(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Prefer installed package name "trading_engine", otherwise use "gm.trading_engine"
try:
    from trading_engine.session import SessionManager
    from trading_engine.api_client import APIClient
    from trading_engine.orders import OrderManager
    from trading_engine.positions import get_positions_with_pnl
    from trading_engine.portfolio import get_holdings_with_pnl
except Exception:
    # fallback to gm.trading_engine if you kept package under gm/
    try:
        from gm.trading_engine.session import SessionManager
        from gm.trading_engine.api_client import APIClient
        from gm.trading_engine.orders import OrderManager
        from gm.trading_engine.positions import get_positions_with_pnl
        from gm.trading_engine.portfolio import get_holdings_with_pnl
    except Exception as e:
        raise

import streamlit as st
import pandas as pd
import time
from typing import Dict, Any, List, Optional

st.set_page_config(page_title="Definedge Dashboard (Table View)", layout="wide")
st.title("Definedge Trading Dashboard — Compact Tables")

# -------------------------
# Load secrets securely
# -------------------------
# Must have these keys in .streamlit/secrets.toml:
# DEFINEDGE_API_TOKEN, DEFINEDGE_API_SECRET, (optional) DEFINEDGE_TOTP_SECRET
API_TOKEN = st.secrets.get("DEFINEDGE_API_TOKEN")
API_SECRET = st.secrets.get("DEFINEDGE_API_SECRET")
TOTP_SECRET = st.secrets.get("DEFINEDGE_TOTP_SECRET")  # optional

if not API_TOKEN or not API_SECRET:
    st.error("API credentials missing in Streamlit secrets. Put DEFINEDGE_API_TOKEN and DEFINEDGE_API_SECRET in .streamlit/secrets.toml")
    st.stop()

# persistent session in session_state
if "client" not in st.session_state:
    st.session_state.client = None
if "last_login" not in st.session_state:
    st.session_state.last_login = None

# -------------------------
# Helpers: parse JSON -> DataFrame
# -------------------------
def holdings_to_df(json_resp: Dict[str, Any]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    if not json_resp:
        return pd.DataFrame(rows)
    data = json_resp.get("data") or json_resp.get("holdings") or []
    for item in data:
        dp_qty = item.get("dp_qty") or item.get("dpQty") or item.get("quantity") or 0
        t1_qty = item.get("t1_qty") or item.get("t1Qty") or 0
        trade_qty = item.get("trade_qty") or item.get("tradeQty") or 0
        avg_buy = item.get("avg_buy_price") or item.get("avgPrice") or item.get("avg_buy") or ""
        sell_amt = item.get("sell_amt") or item.get("sellAmt") or 0
        haircut = item.get("haircut") or ""
        tradings = item.get("tradingsymbol") or []
        if isinstance(tradings, dict):
            tradings = [tradings]
        for t in tradings:
            rows.append({
                "Exchange": t.get("exchange") or "",
                "Symbol": t.get("tradingsymbol") or t.get("symbol") or "",
                "ISIN": t.get("isin") or "",
                "Token": t.get("token") or "",
                "DP Qty": int(dp_qty or 0),
                "T1 Qty": int(t1_qty or 0),
                "Trade Qty": int(trade_qty or 0),
                "Avg Buy Price": float(avg_buy) if str(avg_buy).strip() else None,
                "Sell Amount": float(sell_amt) if str(sell_amt).strip() else 0.0,
                "Haircut": haircut
            })
    df = pd.DataFrame(rows)
    # compact Excel-like formatting: reorder columns
    cols = ["Exchange","Symbol","ISIN","Token","DP Qty","T1 Qty","Trade Qty","Avg Buy Price","Sell Amount","Haircut"]
    return df[cols] if not df.empty else df

def positions_to_df(positions_resp: Any, api_client: Optional[APIClient] = None) -> pd.DataFrame:
    # Try to use get_positions_with_pnl if available (returns portfolio, summary)
    try:
        # If positions_resp already from get_positions_with_pnl, it's tuple
        if isinstance(positions_resp, tuple) and len(positions_resp) == 2:
            portfolio, summary = positions_resp
            return pd.DataFrame(portfolio)
    except Exception:
        pass

    # fallback: raw API list
    rows = []
    data = None
    if isinstance(positions_resp, dict):
        data = positions_resp.get("data") or positions_resp.get("positions") or []
    elif isinstance(positions_resp, list):
        data = positions_resp
    else:
        data = []

    for p in data:
        symbol = p.get("tradingsymbol") or p.get("symbol") or p.get("scrip") or ""
        qty = p.get("quantity") or p.get("qty") or 0
        avg_price = p.get("avg_price") or p.get("avgPrice") or p.get("buy_price") or 0
        ltp = p.get("ltp") or p.get("last_price") or None
        rows.append({
            "Symbol": symbol,
            "Qty": float(qty),
            "Avg Price": float(avg_price or 0),
            "LTP": float(ltp) if ltp is not None else None,
            "Product": p.get("product_type") or p.get("product") or "",
            "Exchange": p.get("exchange") or ""
        })
    return pd.DataFrame(rows)

def orders_to_df(json_resp: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    data = json_resp.get("orders") or json_resp.get("data") or []
    for o in data:
        rows.append({
            "OrderID": o.get("order_id") or o.get("orderId") or o.get("id"),
            "Symbol": o.get("tradingsymbol") or o.get("symbol"),
            "Exchange": o.get("exchange"),
            "Qty": int(o.get("quantity") or o.get("qty") or 0),
            "Filled": int(o.get("filled_qty") or o.get("filledQty") or 0),
            "Status": o.get("order_status") or o.get("status") or o.get("orderStatus"),
            "Price": float(o.get("price") or 0),
            "Avg Traded Price": float(o.get("average_traded_price") or 0)
        })
    return pd.DataFrame(rows)

def trades_to_df(json_resp: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    data = json_resp.get("trades") or json_resp.get("data") or json_resp
    if isinstance(data, dict):
        data = data.get("trades") or data.get("data") or []
    for t in data:
        rows.append({
            "TradeID": t.get("trade_id") or t.get("id"),
            "OrderID": t.get("order_id"),
            "Symbol": t.get("tradingsymbol") or t.get("symbol"),
            "Qty": int(t.get("quantity") or t.get("qty") or 0),
            "Price": float(t.get("price") or t.get("avg_price") or 0),
            "Time": t.get("exchange_time") or t.get("trade_time") or ""
        })
    return pd.DataFrame(rows)

# -------------------------
# Session creation UI
# -------------------------
st.sidebar.header("Account")
if st.session_state.client is None:
    st.sidebar.write("Not logged in")
    if st.sidebar.button("Login (use secrets)"):
        # If TOTP secret present, SessionManager will use it automatically
        try:
            sm = SessionManager(api_token=API_TOKEN, api_secret=API_SECRET, totp_secret=TOTP_SECRET)
            client = sm.create_session()
            st.session_state.client = client
            st.session_state.last_login = time.time()
            st.success("Logged in successfully.")
        except Exception as e:
            # If OTP required manually (SMS), offer manual input flow
            st.error(f"Login failed: {e}")
            st.sidebar.info("If your broker sends SMS OTP, click Request OTP below and paste OTP.")
            if st.sidebar.button("Request OTP"):
                try:
                    sm_tmp = SessionManager(api_token=API_TOKEN, api_secret=API_SECRET, totp_secret=None)
                    step1 = sm_tmp  # we used SessionManager only to trigger auth_step1 in create_session normally
                    # Instead call APIClient.auth_step1 directly
                    # create temporary APIClient
                    try:
                        # try both import flavors
                        from trading_engine.api_client import APIClient as AC
                    except Exception:
                        from gm.trading_engine.api_client import APIClient as AC
                    ac = AC(api_token=API_TOKEN, api_secret=API_SECRET)
                    resp1 = ac.auth_step1()
                    st.sidebar.write("OTP requested. Paste the OTP you received below and click 'Complete OTP Login'.")
                    otp_input = st.sidebar.text_input("OTP (from SMS)", value="", key="sms_otp")
                    if st.sidebar.button("Complete OTP Login"):
                        otp = st.sidebar.session_state.get("sms_otp") or otp_input
                        try:
                            client = sm_tmp.create_session(otp_code=otp)
                            st.session_state.client = client
                            st.success("Logged in with manual OTP.")
                        except Exception as e2:
                            st.error(f"Manual OTP login failed: {e2}")
                except Exception as e3:
                    st.error(f"Failed to request OTP: {e3}")
else:
    client = st.session_state.client
    st.sidebar.write(f"UID: {getattr(client,'uid', 'unknown')}")
    st.sidebar.write(f"Last login: {time.ctime(st.session_state.last_login)}")

# -------------------------
# Main tabs for tables
# -------------------------
tabs = st.tabs(["Home","Holdings","Positions","Orders","Trades"])

# Home
with tabs[0]:
    st.header("Home")
    st.write("Use tabs to view compact tables. Login using sidebar (secrets).")

# Holdings
with tabs[1]:
    st.header("Holdings")
    if st.button("Fetch Holdings (API)"):
        try:
            cli = st.session_state.client
            raw = cli.get_holdings()
            df = holdings_to_df(raw)
            if df.empty:
                st.info("No holdings")
            else:
                # Display compact Excel-like table
                st.dataframe(df.style.format({
                    "Avg Buy Price": "{:.2f}",
                    "Sell Amount": "{:.2f}"
                }), width=1200)
        except Exception as e:
            st.error(f"Fetch holdings failed: {e}")

# Positions
with tabs[2]:
    st.header("Positions")
    if st.button("Fetch Positions (API)"):
        try:
            cli = st.session_state.client
            raw = cli.get_positions()
            # try to compute pnl via helper
            try:
                from trading_engine.positions import get_positions_with_pnl as helper_pos
            except Exception:
                from gm.trading_engine.positions import get_positions_with_pnl as helper_pos
            try:
                portfolio, summary = helper_pos(cli)
                df = pd.DataFrame(portfolio)
            except Exception:
                df = positions_to_df(raw)
            if df.empty:
                st.info("No positions")
            else:
                st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Fetch positions failed: {e}")

# Orders
with tabs[3]:
    st.header("Orders")
    if st.button("Fetch Orders (API)"):
        try:
            cli = st.session_state.client
            raw = cli.list_orders()
            df = orders_to_df(raw)
            if df.empty:
                st.info("No orders")
            else:
                st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Fetch orders failed: {e}")

    st.markdown("---")
    st.subheader("Place Order (dry-run ON by default)")
    dry_run = st.checkbox("Dry-run (do not actually place)", value=True)
    with st.form("order_form"):
        sym = st.text_input("Tradingsymbol", value="RELIANCE")
        exch = st.selectbox("Exchange", ["NSE","NFO","BSE"], index=0)
        qty = st.number_input("Quantity", min_value=1, value=1)
        side = st.selectbox("Side", ["BUY","SELL"], index=0)
        ptype = st.selectbox("Price Type", ["MARKET","LIMIT","SL","SL-M"], index=0)
        price = st.number_input("Price (for LIMIT)", value=0.0, format="%.2f")
        triger = st.number_input("Trigger Price (for SL)", value=0.0, format="%.2f")
        confirm = st.checkbox("I confirm this is intentional (allow real order)", value=False)
        submitted = st.form_submit_button("Submit")
    if submitted:
        om = OrderManager(client)
        payload = {
            "price_type": ptype,
            "tradingsymbol": sym,
            "quantity": str(int(qty)),
            "price": str(price if price else "0"),
            "product_type": "NORMAL",
            "order_type": side,
            "exchange": exch,
        }
        if triger:
            payload["trigger_price"] = str(triger)
        st.write("Payload preview:", payload)
        if dry_run:
            st.info("Dry-run ON — order not sent.")
        else:
            if not confirm:
                st.error("Check the confirmation checkbox to allow real order.")
            else:
                try:
                    resp = om.place_order(tradingsymbol=sym, exchange=exch, quantity=int(qty),
                                           price_type=ptype, side=side, price=price if price else 0,
                                           trigger_price=triger if triger else None)
                    st.success("Order placed (see response table/logs)")
                    st.json(resp)
                except Exception as e:
                    st.error(f"Place order failed: {e}")

# Trades
with tabs[4]:
    st.header("Trades")
    if st.button("Fetch Trades (API)"):
        try:
            cli = st.session_state.client
            raw = cli.get_trades()
            df = trades_to_df(raw)
            if df.empty:
                st.info("No trades")
            else:
                st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Fetch trades failed: {e}")
