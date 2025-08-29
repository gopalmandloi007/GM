# gm/frontend/pages/Portfolio.py
import streamlit as st
import sys
import os
import json
import pandas as pd

# ----------- DEBUG: Add project root to sys.path ----------
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
st.write("📂 Current Working Directory:", os.getcwd())
st.write("🐍 sys.path before adding ROOT:", sys.path)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
st.write("✅ ROOT added to sys.path:", ROOT)
st.write("🐍 sys.path after adding ROOT:", sys.path)

# ----------- Import backend safely ----------
try:
    from backend.holdings import get_holdings
    st.write("✅ Backend import successful")
except Exception as e:
    st.error(f"Backend import failed: {e}")
    st.stop()

# ----------- Debugging function to safely load JSON ----------
def safe_json_load(s):
    try:
        return json.loads(s) if isinstance(s, str) else s
    except Exception as e:
        st.error(f"❌ JSON parse error: {e}")
        st.write("Raw data:", s)
        return None

# ----------- Main Portfolio Display ----------
st.title("📊 Portfolio")

client = st.session_state.get("client", None)
if client is None:
    st.warning("Please login first via the Login page.")
    st.stop()

# Fetch holdings from backend
try:
    raw_holdings = get_holdings(client)
    st.subheader("🔍 Raw holdings from API:")
    st.write(raw_holdings)
except Exception as e:
    st.error(f"Failed to fetch holdings: {e}")
    st.stop()

# Parse and display in table
holdings_data = safe_json_load(raw_holdings)
if holdings_data and "data" in holdings_data and holdings_data["data"]:
    rows = []
    for h in holdings_data["data"]:
        for ts in h.get("tradingsymbol", []):
            rows.append({
                "Symbol": ts.get("tradingsymbol"),
                "Exchange": ts.get("exchange"),
                "Qty (DP)": h.get("dp_qty"),
                "Qty (Trade)": h.get("trade_qty"),
                "Holding Used": h.get("holding_used"),
                "Avg Buy Price": h.get("avg_buy_price"),
                "Sell Amt": h.get("sell_amt"),
                "Haircut": h.get("haircut")
            })
    df = pd.DataFrame(rows)
    st.subheader("💹 Portfolio Table")
    st.dataframe(df)
else:
    st.warning("⚠️ No valid holdings to display.")
