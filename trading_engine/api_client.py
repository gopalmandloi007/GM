# trading_engine/api_client.py
import requests
import json
import logging
import time
from typing import Optional, Dict, Any
import pyotp  # used if totp_secret is provided

logger = logging.getLogger("trading_engine.api_client")
logger.setLevel(logging.INFO)

# Base URLs
BASE_URL = "https://integrate.definedgesecurities.com/dart/v1"
AUTH_BASE = "https://signin.definedgesecurities.com/auth/realms/debroking/dsbpkc"
HIST_URL_TEMPLATE = "https://data.definedgesecurities.com/sds/history/{segment}/{token}/{timeframe}/{from_dt}/{to_dt}"

MASTER_URLS = {
    "NSE_CASH": "https://app.definedgesecurities.com/public/nsecash.zip",
    "NSE_FNO": "https://app.definedgesecurities.com/public/nsefno.zip",
    "BSE_CASH": "https://app.definedgesecurities.com/public/bsecash.zip",
    "BSE_FNO": "https://app.definedgesecurities.com/public/bsefno.zip",
    "MCX_FNO": "https://app.definedgesecurities.com/public/mcxfno.zip",
    "ALL": "https://app.definedgesecurities.com/public/allmaster.zip"
}

class SessionError(Exception):
    pass

class APIError(Exception):
    pass

class APIClient:
    """
    Centralized API client with endpoints dict.
    """
    ENDPOINTS = {
        "placeorder": "/placeorder",
        "orders": "/orders",
        "order": "/order",              # may be used with /order/{id}
        "trades": "/trades",
        "positions": "/positions",
        "holdings": "/holdings",
        "modify": "/modify",
        "cancel": "/cancel",           # to be used as /cancel/{orderid}
        "quotes": "/quotes",           # use /quotes/{exchange}/{token}
        "securityinfo": "/securityinfo",
        "margin": "/margin",
        "limits": "/limits",
        # GTT/OCO endpoints:
        "gttplace": "/gttplaceorder",
        "gttmodify": "/gttmodify",
        "gttcancel": "/gttcancel",
        "ocoplace": "/ocoplaceorder",
        "ocomodify": "/ocomodify",
        "ococancel": "/ococancel",
    }

    def __init__(self, api_token: str, api_secret: str, totp_secret: Optional[str] = None, timeout: int = 15):
        self.api_token = api_token
        self.api_secret = api_secret
        self.totp_secret = totp_secret
        self.api_session_key: Optional[str] = None
        self.susertoken: Optional[str] = None
        self.uid: Optional[str] = None
        self.timeout = timeout

    # ----------------- Authentication -----------------
    def _gen_totp(self) -> Optional[str]:
        if not self.totp_secret:
            return None
        try:
            totp = pyotp.TOTP(self.totp_secret)
            return totp.now()
        except Exception:
            return None

    def request_otp_step1(self) -> Dict[str, Any]:
        """
        Step 1: GET to /login/{api_token} with header api_secret.
        Returns json like: {"otp_token": "...", "message": "..."}
        """
        url = f"{AUTH_BASE}/login/{self.api_token}"
        headers = {"api_secret": self.api_secret}
        resp = requests.get(url, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def login(self, otp: Optional[str] = None) -> Dict[str, Any]:
        """
        Complete login: if otp not provided and totp_secret present, generate totp.
        Then POST to /token with {"otp_token": "...", "otp": "..."} per docs.
        """
        # Step 1: request otp_token (even if totp used, server still needs otp_token)
        s1 = self.request_otp_step1()
        otp_token = s1.get("otp_token")
        if not otp_token:
            raise SessionError("Failed to obtain otp_token from step1")

        # choose otp: given or generated
        if not otp:
            otp = self._gen_totp()
        if not otp:
            raise SessionError("OTP not provided and TOTP secret missing")

        # Step 2: POST to token endpoint
        url = f"{AUTH_BASE}/token"
        payload = {"otp_token": otp_token, "otp": otp}
        resp = requests.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        # expected to have api_session_key and susertoken
        api_key = data.get("api_session_key")
        susertoken = data.get("susertoken")
        uid = data.get("uid")
        if not api_key or not susertoken:
            # some servers return tokens nested in response; handle gracefully
            raise SessionError(f"Login step2 failed: {data}")

        self.api_session_key = api_key
        self.susertoken = susertoken
        self.uid = uid
        logger.info("Login success uid=%s", uid)
        return data

    def _check_auth(self):
        if not self.api_session_key:
            raise SessionError("Not authenticated. Call login() first.")

    def _headers(self) -> Dict[str, str]:
        self._check_auth()
        return {"Authorization": self.api_session_key, "Content-Type": "application/json"}

    # ----------------- Generic helpers -----------------
    def _get(self, rel: str, params: Dict = None):
        url = BASE_URL + rel
        resp = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, rel: str, payload: Dict):
        url = BASE_URL + rel
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    # ----------------- Trading endpoints -----------------
    def get_holdings(self):
        return self._get(self.ENDPOINTS["holdings"])

    def get_positions(self):
        return self._get(self.ENDPOINTS["positions"])

    def get_orders(self):
        return self._get(self.ENDPOINTS["orders"])

    def get_trades(self):
        return self._get(self.ENDPOINTS["trades"])

    def place_order(self, order_payload: Dict):
        return self._post(self.ENDPOINTS["placeorder"], order_payload)

    def modify_order(self, payload: Dict):
        return self._post(self.ENDPOINTS["modify"], payload)

    def cancel_order(self, order_id: str):
        return self._post(f"{self.ENDPOINTS['cancel']}/{order_id}", {})

    # GTT/ OCO wrappers
    def gtt_place(self, payload: Dict):
        return self._post(self.ENDPOINTS["gttplace"], payload)

    def oco_place(self, payload: Dict):
        return self._post(self.ENDPOINTS["ocoplace"], payload)

    # Quotes
    def get_quote(self, exchange: str, token: str):
        return self._get(f"{self.ENDPOINTS['quotes']}/{exchange}/{token}")

    def get_security_info(self, exchange: str, token: str):
        return self._get(f"{self.ENDPOINTS['securityinfo']}/{exchange}/{token}")

    # Margin/limits
    def get_margin(self):
        return self._get(self.ENDPOINTS["margin"])

    def get_limits(self):
        return self._get(self.ENDPOINTS["limits"])

    # Master / Historical utilities
    def download_master(self, key: str = "ALL"):
        url = MASTER_URLS.get(key.upper(), MASTER_URLS["ALL"])
        r = requests.get(url, timeout=self.timeout)
        r.raise_for_status()
        return r.content  # raw zip bytes; caller can extract and save

    def get_historical(self, segment: str, token: str, timeframe: str, from_dt: str, to_dt: str):
        """
        from_dt & to_dt: strings in ddMMyyyyHHmm format as per docs
        timeframe: 'day'|'minute'|'tick'
        """
        url = HIST_URL_TEMPLATE.format(segment=segment, token=token, timeframe=timeframe, from_dt=from_dt, to_dt=to_dt)
        resp = requests.get(url, headers={"Authorization": self.api_session_key}, timeout=self.timeout)
        resp.raise_for_status()
        return resp.text
