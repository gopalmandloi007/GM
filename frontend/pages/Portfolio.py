# gm/frontend/pages/Portfolio.py
import streamlit as st
import sys, os
import json
import pandas as pd

# -------------------------
# DEBUG / IMPORT FIX
# -------------------------
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
    st.write(f"✅ ROOT added to sys.path: {ROOT}")

try:
    from backend.portfolio import get_holdings  # backend module
except Exception as e:
    st.error(f"Backend import failed: {e}")
    st.stop()

# -------------------------
# HELPER: safe JSON load
# -------------------------
def safe_json_load(s):
    try:
        if isinstance(s, str):
            return json.loads(s)
        return s
    except Exception as e:
        st.error(f"JSON parse error: {e}")
        return None

# -------------------------
# PAGE TITLE
# -------------------------
st.title("📊 Portfolio")

# -------------------------
# Check login / client
# -------------------------
client = st.session_state.get("client")
if not client:
    st.warning("Please login first on Login page.")
    st.stop()

# -------------------------
# Fetch holdings
# -------------------------
try:
    raw = get_holdings(client)
    st.subheader("🔍 Raw holdings from API:")
    st.code(raw, language="json")
except Exception as e:
    st.error(f"Failed to fetch holdings: {e}")
    st.stop()

# -------------------------
# Parse and display table
# -------------------------
data = safe_json_load(raw)
if not data or "data" not in data or not data["data"]:
    st.warning("⚠️ No valid holdings to display.")
else:
    rows = []
    for item in data["data"]:
        dp_qty = item.get("dp_qty")
        avg_price = item.get("avg_buy_price")
        holding_used = item.get("holding_used")
        sell_amt = item.get("sell_amt")
        trade_qty = item.get("trade_qty")
        haircut = item.get("haircut")
        t1_qty = item.get("t1_qty")
        
        # Iterate over all tradingsymbols
        for ts in item.get("tradingsymbol", []):
            rows.append({
                "Symbol": ts.get("tradingsymbol"),
                "Exchange": ts.get("exchange"),
                "Token": ts.get("token"),
                "DP Qty": dp_qty,
                "T1 Qty": t1_qty,
                "Holding Used": holding_used,
                "Avg Buy Price": avg_price,
                "Trade Qty": trade_qty,
                "Sell Amount": sell_amt,
                "Haircut": haircut
            })
    df = pd.DataFrame(rows)
    st.subheader("💹 Holdings Table")
    st.dataframe(df, use_container_width=True)
