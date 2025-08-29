import streamlit as st
import pandas as pd
from trading_engine.portfolio import PortfolioManager

pm = PortfolioManager()

def show_holdings():
    st.title("📊 Holdings Dashboard")

    holdings = pm.get_holdings()
    if not holdings:
        st.warning("No holdings found.")
        return

    # Show Holdings Table
    df = pd.DataFrame(holdings)
    st.dataframe(df, use_container_width=True)

    # Get Portfolio Summary
    summary = pm.get_holdings_summary()
    st.subheader("Summary")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Total Invested", f"₹ {summary['invested']:.2f}")
    col2.metric("📈 Current Value", f"₹ {summary['current_value']:.2f}")

    # Today P&L with color indication
    today_pl = summary['today_pl']
    col3.metric("📊 Today P&L", f"₹ {today_pl:.2f}", delta=f"{today_pl:.2f}")

    # Unrealized P&L with % return
    unrealized = summary['unrealized']
    invested = summary['invested']
    percent_return = (unrealized / invested * 100) if invested > 0 else 0
    col4.metric("📉 Unrealized P&L", f"₹ {unrealized:.2f}", delta=f"{percent_return:.2f}%")
