import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from trading_engine.positions import get_positions
from trading_engine.historical import get_prev_close

st.set_page_config(page_title="Positions Dashboard", layout="wide")

st.title("📈 Positions Dashboard")

# Fetch Positions
positions = get_positions()
if positions.empty:
    st.warning("No Open Positions Found")
else:
    # Add Previous Close & Calculate Today P&L
    positions["prev_close"] = positions["symbol"].apply(get_prev_close)
    positions["today_pnl"] = (positions["ltp"] - positions["prev_close"]) * positions["quantity"]
    positions["unrealized"] = (positions["ltp"] - positions["avg_price"]) * positions["quantity"]

    total_invested = (positions["avg_price"] * positions["quantity"]).sum()
    current_value = (positions["ltp"] * positions["quantity"]).sum()
    today_pnl = positions["today_pnl"].sum()
    overall_unrealized = positions["unrealized"].sum()

    # Summary Cards
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Invested", f"₹ {total_invested:,.2f}")
    col2.metric("Current Value", f"₹ {current_value:,.2f}")
    col3.metric("Today P&L", f"₹ {today_pnl:,.2f}", delta=f"{today_pnl:,.2f}")
    col4.metric("Overall Unrealized", f"₹ {overall_unrealized:,.2f}", delta=f"{overall_unrealized:,.2f}")

    # Positions Table
    st.subheader("Positions Detail")
    st.dataframe(positions[["symbol", "quantity", "avg_price", "ltp", "prev_close", "today_pnl", "unrealized"]], use_container_width=True)

    # Bar Chart (Compact)
    fig = go.Figure(data=[go.Bar(x=positions["symbol"], y=positions["today_pnl"], marker_color="green")])
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)
