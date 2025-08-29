import streamlit as st
from backend.session import SessionManager

def show_login():
    st.title("Login")

    if "session" not in st.session_state:
        st.session_state.session = None

    if st.session_state.session is None:
        if st.button("Login"):
            try:
                session_manager = SessionManager()
                session_manager.login()
                st.session_state.session = session_manager
                st.success("Login successful!")
            except Exception as e:
                st.error(f"Login failed: {e}")
    else:
        st.success("Already logged in.")

if __name__ == "__main__":
    show_login()
