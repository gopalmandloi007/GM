import streamlit as st
import sys, os

# Debug: show sys.path and cwd
st.write("📂 Current Working Directory:", os.getcwd())
st.write("🐍 sys.path:", sys.path)

try:
    from gm.backend.session import SessionManager
    st.write("✅ Import successful: gm.backend.session")
except Exception as e:
    st.error(f"❌ Import failed: {e}")
    raise

def show_login():
    st.title("Login (Debug Mode)")

    if "session" not in st.session_state:
        st.session_state.session = None

    if st.session_state.session is None:
        if st.button("Login"):
            try:
                st.write("🔑 Creating SessionManager...")

                session_manager = SessionManager(
                    api_token=st.secrets["INTEGRATE_API_TOKEN"],
                    api_secret=st.secrets["INTEGRATE_API_SECRET"],
                    totp_secret=st.secrets.get("TOTP_SECRET")
                )
                
                st.write("⚡ Calling create_session() ...")
                client = session_manager.create_session()
                
                st.session_state.session = session_manager
                st.session_state.client = client

                st.success(f"Login successful! UID: {session_manager.uid}")
            except Exception as e:
                import traceback
                st.error(f"❌ Login failed: {e}")
                st.text(traceback.format_exc())
    else:
        st.success(f"Already logged in. UID: {st.session_state.session.uid}")

if __name__ == "__main__":
    show_login()
