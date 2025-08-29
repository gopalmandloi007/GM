import streamlit as st
from trading_engine.holdings import get_holdings

def app():
    st.title("💼 Portfolio")
    session = st.session_state.get("session")

    if not session:
        st.warning("Please login first.")
        return

    try:
        data = get_holdings(session)
        st.dataframe(data, use_container_width=True)
    except Exception as e:
        st.error(f"Error fetching portfolio: {e}")

if __name__ == "__main__":
    app()
