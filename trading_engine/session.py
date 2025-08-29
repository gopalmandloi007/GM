# trading_engine/session.py
import os
import logging
from typing import Optional
from .api_client import APIClient

logger = logging.getLogger("trading_engine.session")
logger.setLevel(logging.INFO)

class SessionError(Exception):
    pass

class SessionManager:
    """
    Small wrapper that can run the two-step login or TOTP flow and return an APIClient
    """
    def __init__(self, api_token: Optional[str]=None, api_secret: Optional[str]=None, totp_secret: Optional[str]=None):
        self.api_token = api_token or os.getenv("INTEGRATE_API_TOKEN")
        self.api_secret = api_secret or os.getenv("INTEGRATE_API_SECRET")
        self.totp_secret = totp_secret or os.getenv("TOTP_SECRET")
        self.client: Optional[APIClient] = None

    def login(self, otp: Optional[str]=None, prefer_totp: bool=True):
        """
        If prefer_totp True and totp_secret present, we try to do TOTP (via pyotp) by simulating OTP step.
        Otherwise run step1 (get otp_token) and step2 with provided otp.
        After successful step2, create APIClient with api_session_key and susertoken.
        """
        if not self.api_token or not self.api_secret:
            raise SessionError("API credentials missing")

        client = APIClient(api_token=self.api_token, api_secret=self.api_secret)
        # Step1: GET login to receive otp_token (this triggers OTP to mobile/email). If we want TOTP flow,
        # some brokers accept TOTP directly at step2 - here we still follow docs: step1 then step2
        try:
            step1 = client.auth_step1()
            otp_token = step1.get("otp_token")
        except Exception as e:
            raise SessionError(f"Step1 failed: {e}")

        # If prefer_totp and totp_secret provided, generate totp code
        import pyotp, time
        if prefer_totp and self.totp_secret:
            try:
                totp = pyotp.TOTP(self.totp_secret)
                otp_code = totp.now()
            except Exception:
                otp_code = otp or None
        else:
            otp_code = otp

        if not otp_code:
            raise SessionError("OTP required (either pass otp param or set totp_secret)")

        # Step2
        try:
            step2 = client.auth_step2(otp_token, otp_code)
        except Exception as e:
            raise SessionError(f"Step2 failed: {e}")

        # step2 returns api_session_key and susertoken etc.
        api_session_key = step2.get("api_session_key")
        susertoken = step2.get("susertoken")
        uid = step2.get("uid")
        if not api_session_key:
            raise SessionError("Login succeeded but no api_session_key returned")

        client.api_session_key = api_session_key
        client.susertoken = susertoken
        client.uid = uid
        self.client = client
        logger.info("SessionManager: login successful uid=%s", uid)
        return step2

    def build_client(self):
        if not self.client:
            raise SessionError("No active session. Call login() first")
        return self.client
