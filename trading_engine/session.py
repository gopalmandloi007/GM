# trading_engine/session.py
import logging
import os
from typing import Optional
from .api_client import APIClient, SessionError

logger = logging.getLogger("trading_engine.session")
logger.setLevel(logging.INFO)

# Session storage file (simple)
SESSION_FILE = os.path.join(os.getcwd(), ".session_store.json")

class SessionManager:
    """
    Thin wrapper that holds the APIClient and session keys.
    Persist session keys locally to re-use during dev/testing.
    """
    def __init__(self, api_token: Optional[str] = None, api_secret: Optional[str] = None, totp_secret: Optional[str] = None):
        self.api_token = api_token or os.getenv("INTEGRATE_API_TOKEN")
        self.api_secret = api_secret or os.getenv("INTEGRATE_API_SECRET")
        self.totp_secret = totp_secret or os.getenv("TOTP_SECRET")
        self.client: Optional[APIClient] = None

    def build_client(self):
        if not self.client:
            if not self.api_token or not self.api_secret:
                raise SessionError("API token/secret not set.")
            self.client = APIClient(api_token=self.api_token, api_secret=self.api_secret, totp_secret=self.totp_secret)
        return self.client

    def login(self, otp: Optional[str] = None, prefer_totp: bool = True):
        """
        High level login that tries TOTP if preferred and available.
        Returns login response dict.
        """
        client = self.build_client()
        if prefer_totp and self.totp_secret and not otp:
            # client.login will use totp if otp is None but totp_secret present
            resp = client.login(otp=None)
        else:
            resp = client.login(otp=otp)
        logger.info("SessionManager: login successful for uid=%s", resp.get("uid"))
        return resp

    def is_logged_in(self):
        try:
            return bool(self.client and self.client.api_session_key)
        except Exception:
            return False
