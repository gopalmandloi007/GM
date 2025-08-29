# gm/frontend/pages/Portfolio.py
import streamlit as st
import pandas as pd
import json
from gm.backend.portfolio import get_holdings  # backend module

st.set_page_config(page_title="Portfolio", layout="wide")
st.title("📊 Portfolio")

# Utility function: safe JSON parse
def safe_json_load(s):
    try:
        return json.loads(s) if isinstance(s, str) else s
    except Exception as e:
        st.error(f"JSON parse error: {e}")
        return None

# Fetch holdings
client = st.session_state.get("client")
if client is None:
    st.warning("⚠️ Login first to fetch holdings.")
    st.stop()

try:
    raw_holdings = get_holdings(client)
    if not raw_holdings or "data" not in raw_holdings:
        st.warning("⚠️ No valid holdings to display.")
    else:
        # debug: show raw JSON
        st.subheader("🔍 Raw holdings from API:")
        st.json(raw_holdings)

        # Flatten holdings for table
        table_rows = []
        for item in raw_holdings.get("data", []):
            tradings = item.get("tradingsymbol", [])
            for t in tradings:
                table_rows.append({
                    "Symbol": t.get("tradingsymbol"),
                    "Exchange": t.get("exchange"),
                    "ISIN": t.get("isin"),
                    "Lot Size": t.get("lotsize"),
                    "Avg Buy Price": item.get("avg_buy_price"),
                    "Holding Qty": item.get("dp_qty"),
                    "T1 Qty": item.get("t1_qty"),
                    "Collateral Qty": item.get("collateral_qty"),
                    "Holding Used": item.get("holding_used"),
                    "Trade Qty": item.get("trade_qty"),
                    "Sell Amt": item.get("sell_amt"),
                    "Haircut": item.get("haircut"),
                })

        if table_rows:
            df = pd.DataFrame(table_rows)
            st.subheader("💹 Holdings Table")
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("⚠️ No holdings available after parsing.")

except Exception as e:
    st.error(f"Failed to fetch holdings: {e}")
