import streamlit as st
from trading_engine.session import SessionManager

def app():
    st.title("🔐 Login")

    if "session" not in st.session_state:
        st.session_state.session = None

    if st.button("Login with Secrets"):
        try:
            sm = SessionManager()
            sm.login_with_secrets()
            st.session_state.session = sm
            st.success("Login successful ✅")
        except Exception as e:
            st.error(f"Login failed: {e}")

if __name__ == "__main__":
    app()
