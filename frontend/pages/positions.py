import streamlit as st
import pandas as pd
from trading_engine.positions import PositionsManager

pm = PositionsManager()

def show_positions():
    st.title("📊 Positions Dashboard")

    positions = pm.get_positions()
    if not positions:
        st.warning("No active positions.")
        return

    df = pd.DataFrame(positions)
    st.dataframe(df, use_container_width=True)

    summary = pm.get_positions_summary()
    st.subheader("Summary")
    st.metric("Total Buy Value", f"₹ {summary['buy_value']:.2f}")
    st.metric("Total Sell Value", f"₹ {summary['sell_value']:.2f}")
    st.metric("MTM P&L", f"₹ {summary['mtm']:.2f}")
