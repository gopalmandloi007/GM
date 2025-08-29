# gm/frontend/pages/Portfolio.py
import streamlit as st
import pandas as pd
import json

# Import backend API
try:
    from gm.backend.holdings import get_holdings
except Exception as e:
    st.error(f"Backend import failed: {e}")
    st.stop()

st.title("📊 Portfolio / Holdings")

# Check if logged in
if "client" not in st.session_state or st.session_state.client is None:
    st.warning("Please login first on the Login page.")
    st.stop()

client = st.session_state.client

# Fetch holdings
st.info("Fetching holdings from API...")
try:
    raw_holdings = get_holdings(client)
except Exception as e:
    st.error(f"Failed to fetch holdings: {e}")
    st.stop()

# Display raw JSON if needed (debug)
with st.expander("🔍 Raw holdings from API"):
    st.json(raw_holdings)

# Process JSON to DataFrame
def process_holdings(raw):
    data = raw.get("data", [])
    rows = []
    for item in data:
        base = {
            "DP Qty": item.get("dp_qty"),
            "T1 Qty": item.get("t1_qty"),
            "Holding Used": item.get("holding_used"),
            "Avg Buy Price": item.get("avg_buy_price"),
            "Haircut": item.get("haircut"),
            "Sell Amt": item.get("sell_amt"),
            "Trade Qty": item.get("trade_qty"),
        }
        for ts in item.get("tradingsymbol", []):
            row = base.copy()
            row.update({
                "Exchange": ts.get("exchange"),
                "Symbol": ts.get("tradingsymbol"),
                "Token": ts.get("token"),
                "Lot Size": ts.get("lotsize"),
                "Tick Size": ts.get("ticksize"),
                "ISIN": ts.get("isin"),
            })
            rows.append(row)
    if rows:
        return pd.DataFrame(rows)
    else:
        return pd.DataFrame()

# Convert and show
df_holdings = process_holdings(raw_holdings)

if df_holdings.empty:
    st.warning("⚠️ No valid holdings to display.")
else:
    st.success(f"✅ {len(df_holdings)} holdings loaded.")
    # Compact Excel-style table
    st.dataframe(df_holdings, use_container_width=True)
