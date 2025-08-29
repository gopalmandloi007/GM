import streamlit as st
import pandas as pd
from trading_engine.orders import OrderManager

om = OrderManager()

def show_orders():
    st.title("📝 Orders Dashboard")

    with st.expander("📌 Place New Order"):
        symbol = st.text_input("Symbol", value="RELIANCE")
        qty = st.number_input("Quantity", min_value=1, value=1)
        side = st.radio("Side", ["BUY", "SELL"], horizontal=True)
        order_type = st.radio("Order Type", ["MARKET", "LIMIT", "SL", "SL-M"], horizontal=True)
        price = st.number_input("Price", min_value=0.0, value=0.0) if order_type != "MARKET" else None
        trigger_price = st.number_input("Trigger Price", min_value=0.0, value=0.0) if order_type in ["SL", "SL-M"] else None

        if st.button("🚀 Place Order"):
            resp = om.place_order(symbol, qty, order_type=order_type, side=side, price=price, trigger_price=trigger_price)
            st.success(resp)

    st.subheader("📒 Order Book")
    orders = om.order_book()
    if orders:
        st.dataframe(pd.DataFrame(orders), use_container_width=True)

    st.subheader("📒 Trade Book")
    trades = om.trade_book()
    if trades:
        st.dataframe(pd.DataFrame(trades), use_container_width=True)
