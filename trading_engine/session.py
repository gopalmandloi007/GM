# trading_engine/session.py
import os
import time
import json
import logging
from typing import Optional, Dict, Any
import requests
import pyotp
from .utils import get_sqlite_conn, now_ts

logger = logging.getLogger("trading_engine.session")
logger.setLevel(logging.INFO)

SIGNIN_BASE = "https://signin.definedgesecurities.com/auth/realms/debroking/dsbpkc"
STEP1 = lambda token: f"{SIGNIN_BASE}/login/{token}"
STEP2 = f"{SIGNIN_BASE}/token"

# Secret names (Streamlit secrets or env)
ENV_TOKEN = "INTEGRATE_API_TOKEN"
ENV_SECRET = "INTEGRATE_API_SECRET"
ENV_TOTP = "TOTP_SECRET"  # note name: match your secrets.toml (INTEGRATE vs earlier)

class SessionError(Exception):
    pass

class SessionManager:
    """
    Single-session manager. Stores session in SQLite 'sessions' table and in-memory.
    Use SessionManager.get() to obtain singleton instance.
    """

    _instance = None

    def __init__(self, api_token: Optional[str] = None, api_secret: Optional[str] = None, totp_secret: Optional[str] = None):
        self.api_token = api_token or os.getenv(ENV_TOKEN)
        self.api_secret = api_secret or os.getenv(ENV_SECRET)
        self.totp_secret = totp_secret or os.getenv(ENV_TOTP)

        if not self.api_token or not self.api_secret:
            raise SessionError("API token/secret not configured (INTEGRATE_API_TOKEN / INTEGRATE_API_SECRET).")

        # session values
        self.api_session_key: Optional[str] = None
        self.susertoken: Optional[str] = None
        self.uid: Optional[str] = None
        self.uname: Optional[str] = None
        self.last_acquired: Optional[int] = None

        # DB init
        self.conn = get_sqlite_conn()
        self._init_db()
        # try load
        self._load_from_db()

    @classmethod
    def get(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = cls(*args, **kwargs)
        return cls._instance

    def _init_db(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            uid TEXT PRIMARY KEY,
            api_session_key TEXT,
            susertoken TEXT,
            uname TEXT,
            last_acquired INTEGER
        )
        """)
        self.conn.commit()

    def _load_from_db(self):
        cur = self.conn.cursor()
        cur.execute("SELECT uid, api_session_key, susertoken, uname, last_acquired FROM sessions LIMIT 1")
        row = cur.fetchone()
        if row:
            self.uid, self.api_session_key, self.susertoken, self.uname, self.last_acquired = row
            logger.info("Loaded session from DB (uid=%s)", self.uid)

    def save_to_db(self):
        if not self.api_session_key or not self.susertoken:
            return
        cur = self.conn.cursor()
        cur.execute("INSERT OR REPLACE INTO sessions (uid, api_session_key, susertoken, uname, last_acquired) VALUES (?,?,?,?,?)",
                    (self.uid or "uid", self.api_session_key, self.susertoken, self.uname or "", int(time.time())))
        self.conn.commit()
        logger.info("Session saved to DB")

    def is_valid(self) -> bool:
        # basic TTL: treat as valid for 23.5 hours (session is approx 24h)
        if not self.api_session_key or not self.susertoken or not self.last_acquired:
            return False
        return (time.time() - self.last_acquired) < (23.5 * 3600)

    def step1_request_otp(self) -> Dict[str, Any]:
        url = STEP1(self.api_token)
        headers = {"api_secret": self.api_secret}
        try:
            r = requests.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
            logger.info("Step1 success")
            return data
        except requests.RequestException as e:
            logger.error("Step1 failed: %s", e)
            raise SessionError(f"Step1 failed: {e}")

    def _generate_totp(self) -> str:
        if not self.totp_secret:
            raise SessionError("TOTP_SECRET not configured")
        return pyotp.TOTP(self.totp_secret).now()

    def step2_verify_otp(self, otp_token: str, otp: Optional[str] = None) -> Dict[str, Any]:
        if otp is None:
            otp = self._generate_totp()
        payload = {"otp_token": otp_token, "otp": otp}
        try:
            r = requests.post(STEP2, json=payload, timeout=15)
            r.raise_for_status()
            data = r.json()
            # extract keys
            self.api_session_key = data.get("api_session_key")
            self.susertoken = data.get("susertoken") or data.get("susertokenspl")
            self.uid = data.get("uid")
            self.uname = data.get("uname")
            self.last_acquired = int(time.time())
            if not self.api_session_key or not self.susertoken:
                raise SessionError(f"Step2 succeeded but session keys missing: {data}")
            self.save_to_db()
            logger.info("Step2 success (session stored).")
            return data
        except requests.RequestException as e:
            logger.error("Step2 failed: %s", e)
            raise SessionError(f"Step2 failed: {e}")

    def get_auth_headers(self) -> Dict[str, str]:
        if not self.api_session_key:
            raise SessionError("Not logged in. Call step1/step2.")
        return {"Authorization": self.api_session_key}

    def force_logout(self):
        # clear DB
        cur = self.conn.cursor()
        cur.execute("DELETE FROM sessions")
        self.conn.commit()
        self.api_session_key = None
        self.susertoken = None
        self.uid = None
        self.uname = None
        self.last_acquired = None
        logger.info("Session cleared")
