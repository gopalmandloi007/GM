import streamlit as st
import pandas as pd
from trading_engine.orders import OrderManager

om = OrderManager()

def show_gtt_orders():
    st.title("⏳ GTT Orders Dashboard")

    with st.expander("📌 Place New GTT Order"):
        symbol = st.text_input("Symbol", value="RELIANCE")
        qty = st.number_input("Quantity", min_value=1, value=1)
        side = st.radio("Side", ["BUY", "SELL"], horizontal=True)
        trigger_price = st.number_input("Trigger Price", min_value=0.0, value=0.0)
        price = st.number_input("Order Price", min_value=0.0, value=0.0)

        if st.button("🚀 Place GTT Order"):
            resp = om.place_gtt(symbol, qty, trigger_price, price, side=side)
            if "error" in str(resp).lower():
                st.error(resp)
            else:
                st.success(resp)

    st.subheader("📒 Active GTT Orders")
    gtts = om.gtt_orders()
    if gtts:
        df = pd.DataFrame(gtts)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No active GTT orders found.")
