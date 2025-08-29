import streamlit as st
from trading_engine.positions import get_positions

def app():
    st.title("📌 Positions")
    session = st.session_state.get("session")

    if not session:
        st.warning("Please login first.")
        return

    try:
        data = get_positions(session)
        st.dataframe(data, use_container_width=True)
    except Exception as e:
        st.error(f"Error fetching positions: {e}")
