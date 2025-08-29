import streamlit as st
import pandas as pd
from trading_engine.portfolio import get_holdings
from trading_engine.session import SessionManager

# Secrets se load
API_TOKEN = st.secrets["DEFINEDGE_API_TOKEN"]
API_SECRET = st.secrets["DEFINEDGE_API_SECRET"]
TOTP_SECRET = st.secrets.get("DEFINEDGE_TOTP_SECRET")

# Session init
session = SessionManager(API_TOKEN, API_SECRET, TOTP_SECRET)

st.title("📊 Holdings Dashboard")

if st.button("Fetch Holdings"):
    data = get_holdings(session)

    if data and "data" in data:
        holdings_list = []

        for item in data["data"]:
            # Sirf NSE ka symbol show karenge for clarity
            nse_symbol = next((s for s in item["tradingsymbol"] if s["exchange"] == "NSE"), {})
            holdings_list.append({
                "Symbol": nse_symbol.get("tradingsymbol", ""),
                "ISIN": nse_symbol.get("isin", ""),
                "DP Qty": item["dp_qty"],
                "Used Qty": item["holding_used"],
                "Trade Qty": item["trade_qty"],
                "Avg Buy Price": item["avg_buy_price"],
                "Sell Amount": item["sell_amt"],
                "Haircut": item["haircut"]
            })

        df = pd.DataFrame(holdings_list)

        st.subheader("📑 Compact Holdings Table")
        st.dataframe(df, use_container_width=True)  # Excel-type table
    else:
        st.warning("⚠️ No holdings data found.")
