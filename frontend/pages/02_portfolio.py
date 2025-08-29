import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from trading_engine.portfolio import get_holdings
from trading_engine.historical import get_prev_close

st.set_page_config(page_title="Portfolio Dashboard", layout="wide")

st.title("📊 Portfolio Dashboard")

# Fetch Holdings
holdings = get_holdings()
if holdings.empty:
    st.warning("No Holdings Found")
else:
    # Add Previous Close & Calculate Today P&L
    holdings["prev_close"] = holdings["symbol"].apply(get_prev_close)
    holdings["today_pnl"] = (holdings["ltp"] - holdings["prev_close"]) * holdings["quantity"]
    holdings["unrealized"] = (holdings["ltp"] - holdings["avg_price"]) * holdings["quantity"]

    total_invested = (holdings["avg_price"] * holdings["quantity"]).sum()
    current_value = (holdings["ltp"] * holdings["quantity"]).sum()
    today_pnl = holdings["today_pnl"].sum()
    overall_unrealized = holdings["unrealized"].sum()

    # Summary Cards
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Invested", f"₹ {total_invested:,.2f}")
    col2.metric("Current Value", f"₹ {current_value:,.2f}")
    col3.metric("Today P&L", f"₹ {today_pnl:,.2f}", delta=f"{today_pnl:,.2f}")
    col4.metric("Overall Unrealized", f"₹ {overall_unrealized:,.2f}", delta=f"{overall_unrealized:,.2f}")

    # Holdings Table
    st.subheader("Holdings Detail")
    st.dataframe(holdings[["symbol", "quantity", "avg_price", "ltp", "prev_close", "today_pnl", "unrealized"]], use_container_width=True)

    # Pie Chart (Compact)
    fig = go.Figure(data=[go.Pie(labels=holdings["symbol"], values=holdings["ltp"] * holdings["quantity"], hole=0.5)])
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)
