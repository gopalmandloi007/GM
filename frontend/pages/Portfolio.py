import streamlit as st
import pandas as pd
from backend.holdings import get_holdings

st.set_page_config(page_title="Portfolio", layout="wide")

st.title("📊 Portfolio Overview")

# Check login
if "session" not in st.session_state:
    st.error("Please login first.")
    st.stop()

session = st.session_state.session

try:
    holdings_data = get_holdings(session)
except Exception as e:
    st.error(f"Error fetching holdings: {e}")
    st.stop()

if not holdings_data:
    st.info("No holdings found.")
else:
    # Convert to dataframe
    df = pd.DataFrame(holdings_data)

    # Ensure readable column names
    rename_map = {
        "symbol": "Symbol",
        "qty": "Quantity",
        "avg_price": "Avg. Price",
        "ltp": "LTP",
        "pnl": "P&L",
        "net_value": "Net Value"
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

    # Calculate P&L if missing
    if "P&L" not in df.columns and {"Quantity", "Avg. Price", "LTP"}.issubset(df.columns):
        df["P&L"] = (df["LTP"] - df["Avg. Price"]) * df["Quantity"]

    # Style
    def highlight_pnl(val):
        color = "green" if val > 0 else "red"
        return f"color: {color}; font-weight: bold"

    st.dataframe(
        df.style.format({"Avg. Price": "{:.2f}", "LTP": "{:.2f}", "P&L": "{:.2f}", "Net Value": "{:.2f}"})
                 .applymap(highlight_pnl, subset=["P&L"])
    )
