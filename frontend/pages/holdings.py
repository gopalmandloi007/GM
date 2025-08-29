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

    df = pd.DataFrame(holdings)
    st.dataframe(df, use_container_width=True)

    summary = pm.get_holdings_summary()
    st.subheader("Summary")
    st.metric("Total Invested", f"₹ {summary['invested']:.2f}")
    st.metric("Current Value", f"₹ {summary['current_value']:.2f}")
    st.metric("Today P&L", f"₹ {summary['today_pl']:.2f}")
    st.metric("Unrealized P&L", f"₹ {summary['unrealized']:.2f}")
