# gm/frontend/pages/Portfolio.py
import streamlit as st

def show_portfolio():
    st.title("📊 Portfolio")

    client = st.session_state.get("client")

    if not client:
        st.warning("⚠️ Please login first from the Login page.")
        return

    try:
        holdings = client.get_holdings()
        if holdings:
            st.success("Holdings fetched successfully ✅")
            st.dataframe(holdings)  # Streamlit table view
        else:
            st.info("No holdings found.")
    except Exception as e:
        st.error(f"Failed to fetch holdings: {e}")

if __name__ == "__main__":
    show_portfolio()
