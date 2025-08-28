import streamlit as st
import pandas as pd
from trading_engine.orders import get_orders

st.set_page_config(page_title="Order Book", layout="wide")

st.title("📖 Order Book")

orders = get_orders()

if not orders.empty:
    st.dataframe(
        orders,
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("ℹ️ No orders placed yet.")
