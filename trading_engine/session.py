# gm/trading_engine/session.py
import time
import pyotp
import logging
from typing import Optional
from .api_client import APIClient

logger = logging.getLogger("trading_engine.session")
logger.setLevel(logging.INFO)

class SessionError(Exception):
    pass

class SessionManager:
    """
    Manages login flow using Definedge endpoints.
    Usage:
        sm = SessionManager(api_token=..., api_secret=..., totp_secret=...)
        client = sm.create_session()  # returns APIClient with api_session_key set
    """
    def __init__(self, api_token: Optional[str] = None, api_secret: Optional[str] = None, totp_secret: Optional[str] = None):
        self.api_token = api_token
        self.api_secret = api_secret
        self.totp_secret = totp_secret

        self.api_session_key = None
        self.susertoken = None
        self.uid = None
        self.actid = None

    def create_session(self, otp_code: Optional[str] = None) -> APIClient:
        """
        Run login flow:
         1) GET /login/{api_token} with header api_secret -> expect an otp_token or info
         2) POST /token with { otp_token, otp } -> expect api_session_key + susertoken
        If totp_secret provided, otp is generated automatically.
        Returns an APIClient instance with session details set.
        """
        if not self.api_token:
            raise SessionError("api_token required for session creation")
        if not self.api_secret:
            raise SessionError("api_secret required for session creation")

        client = APIClient(api_token=self.api_token, api_secret=self.api_secret)

        # step1
        try:
            step1 = client.auth_step1()
        except Exception as e:
            logger.exception("auth_step1 failed")
            raise SessionError(f"auth_step1 failed: {e}")

        # try to extract otp_token from response
        otp_token = None
        if isinstance(step1, dict):
            for k in ("otp_token", "otpToken", "otp_request_token", "otpRequestToken", "request_token"):
                if k in step1:
                    otp_token = step1.get(k)
                    break

        # generate otp if totp_secret provided
        if self.totp_secret:
            try:
                otp_code = pyotp.TOTP(self.totp_secret).now()
            except Exception as e:
                logger.exception("TOTP generation failed")
                raise SessionError(f"TOTP generation failed: {e}")

        if not otp_code:
            raise SessionError("OTP code required. Provide totp_secret or pass otp_code to create_session()")

        # step2
        try:
            resp = client.auth_step2(otp_token=otp_token or "", otp_code=str(otp_code))
        except Exception as e:
            logger.exception("auth_step2 failed")
            raise SessionError(f"auth_step2 failed: {e}")

        # extract session key and susertoken
        if isinstance(resp, dict):
            self.api_session_key = resp.get("api_session_key") or resp.get("api_session_key".lower()) or resp.get("apiKey") or resp.get("api_key") or resp.get("apiSessionKey")
            self.susertoken = resp.get("susertoken") or resp.get("susertoken".lower()) or resp.get("susertoken")
            self.uid = resp.get("uid") or resp.get("user") or resp.get("actid")
            self.actid = resp.get("actid") or resp.get("actid".lower()) or self.uid

        if not self.api_session_key:
            raise SessionError(f"Login did not return api_session_key. Response: {resp}")

        # create APIClient with session key & susertoken set
        final_client = APIClient(
            api_token=self.api_token,
            api_secret=self.api_secret,
            api_session_key=self.api_session_key,
            susertoken=self.susertoken,
            uid=self.uid
        )

        logger.info("Session created successfully for uid=%s actid=%s", self.uid, self.actid)
        return final_client
