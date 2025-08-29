# gm/frontend/pages/login.py
import streamlit as st
from GM.backend.session import SessionManager

def show_login():
    st.title("Login")

    if "session" not in st.session_state:
        st.session_state.session = None

    if st.session_state.session is None:
        if st.button("Login"):
            try:
                # SessionManager ko secrets se initialize karo
                session_manager = SessionManager(
                    api_token=st.secrets["INTEGRATE_API_TOKEN"],
                    api_secret=st.secrets["INTEGRATE_API_SECRET"],
                    totp_secret=st.secrets.get("TOTP_SECRET")
                )
                
                # Yeh actually login karega
                client = session_manager.create_session()
                
                st.session_state.session = session_manager
                st.session_state.client = client

                st.success(f"Login successful! UID: {session_manager.uid}")
            except Exception as e:
                st.error(f"Login failed: {e}")
    else:
        st.success(f"Already logged in. UID: {st.session_state.session.uid}")

if __name__ == "__main__":
    show_login()
