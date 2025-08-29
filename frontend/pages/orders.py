import streamlit as st
from trading_engine.orders import place_order

def app():
    st.title("📝 Place Order")
    session = st.session_state.get("session")

    if not session:
        st.warning("Please login first.")
        return

    symbol = st.text_input("Symbol", "NIFTY")
    qty = st.number_input("Quantity", min_value=1, value=1)
    price = st.number_input("Price", min_value=0.0, value=0.0)
    side = st.selectbox("Side", ["BUY", "SELL"])

    if st.button("Submit Order"):
        try:
            resp = place_order(session, symbol, qty, price, side)
            st.success(f"Order placed: {resp}")
        except Exception as e:
            st.error(f"Failed: {e}")
