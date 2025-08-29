# frontend/pages/login.py
import streamlit as st
import sys, os
from typing import Optional

# Ensure project root is importable (frontend/pages -> go two levels up to GM/)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Import backend SessionManager (you moved trading_engine -> backend)
try:
    from backend.session import SessionManager, SessionError
    from backend.api_client import APIClient
except Exception as e:
    st.error("Backend import failed. Make sure `backend` package exists and has session.py and api_client.py.")
    st.stop()

st.title("🔐 Login — Definedge")

st.markdown(
    """
    This page logs you into Definedge using credentials stored in `.streamlit/secrets.toml`.
    - Make sure `INTEGRATE_API_TOKEN` and `INTEGRATE_API_SECRET` are present in secrets.
    - `INTEGRATE_TOTP_SECRET` is optional. If present, TOTP will be used automatically.
    """
)

# -- load secrets --
API_TOKEN = st.secrets.get("INTEGRATE_API_TOKEN")
API_SECRET = st.secrets.get("INTEGRATE_API_SECRET")
TOTP_SECRET = st.secrets.get("INTEGRATE_TOTP_SECRET")  # optional

if not API_TOKEN or not API_SECRET:
    st.error("Missing secrets. Add INTEGRATE_API_TOKEN and INTEGRATE_API_SECRET to .streamlit/secrets.toml")
    st.stop()

# Persistent client in session_state
if "client" not in st.session_state:
    st.session_state.client = None
if "login_resp" not in st.session_state:
    st.session_state.login_resp = None
if "otp_requested" not in st.session_state:
    st.session_state.otp_requested = False

col1, col2 = st.columns([2, 3])

with col1:
    st.subheader("Login (auto via secrets)")
    st.write("TOTP secret detected: ", bool(TOTP_SECRET))
    if st.button("Login now (use secrets)"):
        try:
            sm = SessionManager(api_token=API_TOKEN, api_secret=API_SECRET, totp_secret=(TOTP_SECRET or None))
            # create_session will use TOTP if totp_secret provided, otherwise expect otp_code parameter
            client = sm.create_session()  # may raise if OTP required and totp not provided
            st.session_state.client = client
            st.session_state.login_resp = {"status": "ok"}
            st.success("✅ Logged in successfully.")
            st.write({"uid": getattr(client, "uid", None), "susertoken_present": bool(getattr(client, "susertoken", None))})
        except Exception as e:
            # If OTP required or other error, show helpful message and enable manual OTP flow
            st.error(f"Login failed: {e}")
            st.info("If your broker sends SMS OTP (not TOTP), use the manual OTP flow below: click Request OTP then paste the OTP you received.")

with col2:
    st.subheader("Manual OTP (SMS) flow")
    st.write("Use this if your broker sends SMS OTP instead of TOTP.")
    if st.button("Request OTP (trigger auth_step1)"):
        try:
            # create lightweight api client and call auth_step1 to trigger OTP send
            ac = APIClient(api_token=API_TOKEN, api_secret=API_SECRET)
            step1 = ac.auth_step1()
            st.session_state.otp_requested = True
            st.success("OTP requested. Check your phone and paste OTP below.")
            st.write("Server response (step1):")
            st.write(step1)
        except Exception as e:
            st.error(f"Request OTP failed: {e}")

    otp_code = st.text_input("Paste OTP received via SMS", value="", key="sms_otp")
    if st.button("Complete OTP Login"):
        if not otp_code:
            st.warning("Enter OTP before clicking 'Complete OTP Login'.")
        else:
            try:
                sm2 = SessionManager(api_token=API_TOKEN, api_secret=API_SECRET, totp_secret=None)
                client = sm2.create_session(otp_code=str(otp_code))
                st.session_state.client = client
                st.success("✅ Logged in with manual OTP.")
                st.write({"uid": getattr(client, "uid", None), "susertoken_present": bool(getattr(client, "susertoken", None))})
            except Exception as e:
                st.error(f"Manual OTP login failed: {e}")

# Show current session status
st.markdown("---")
st.subheader("Session status")
if st.session_state.client is None:
    st.warning("Not logged in.")
else:
    client = st.session_state.client
    st.success("Logged in")
    st.write("UID:", getattr(client, "uid", None))
    st.write("Session key present:", bool(getattr(client, "api_session_key", None)))
    st.write("Websocket token present:", bool(getattr(client, "susertoken", None)))

    # convenience: logout button
    if st.button("Logout"):
        st.session_state.client = None
        st.session_state.login_resp = None
        st.session_state.otp_requested = False
        st.success("Logged out.")
