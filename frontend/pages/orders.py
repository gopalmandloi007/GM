import streamlit as st
from trading_engine.orders import place_order, get_all_symbols

st.set_page_config(page_title="Orders Dashboard", layout="wide")

st.title("📝 Place Order")

# Fetch All Symbols (from local db / api)
symbols = get_all_symbols()

# Order Form
with st.form("order_form", clear_on_submit=True):
    side = st.radio("Order Side", ["BUY", "SELL"], horizontal=True)
    symbol = st.selectbox("Select Symbol", symbols, index=0)
    qty = st.number_input("Quantity", min_value=1, step=1)
    price = st.number_input("Price (₹)", min_value=0.0, step=0.05, format="%.2f")
    order_type = st.selectbox("Order Type", ["MARKET", "LIMIT"])

    submitted = st.form_submit_button("🚀 Place Order")

    if submitted:
        result = place_order(symbol, side, qty, price, order_type)
        if result.get("status") == "success":
            st.success(f"✅ Order Placed: {side} {qty} {symbol} @ {price if order_type=='LIMIT' else 'MKT'}")
        else:
            st.error(f"❌ Failed: {result.get('message')}")
