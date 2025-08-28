import os
import time
import json
import requests
import zipfile
import io
from datetime import datetime
from trading_engine.session import SessionManager, SessionError

BASE_URL = "https://integrate.definedgesecurities.com/dart/v1"
HISTORICAL_URL = "https://data.definedgesecurities.com/sds/history/{segment}/{token}/{timeframe}/{from}/{to}"
MASTER_URLS = {
    "NSE_CASH": "https://app.definedgesecurities.com/public/nsecash.zip",
    "NSE_FNO": "https://app.definedgesecurities.com/public/nsefno.zip",
    "BSE_CASH": "https://app.definedgesecurities.com/public/bsecash.zip",
    "BSE_FNO": "https://app.definedgesecurities.com/public/bsefno.zip",
    "MCX_FNO": "https://app.definedgesecurities.com/public/mcxfno.zip",
    "ALL": "https://app.definedgesecurities.com/public/allmaster.zip"
}

class APIClient:
    def __init__(self, api_token: str, api_secret: str, totp_secret: str = None):
        self.api_token = api_token
        self.api_secret = api_secret
        self.totp_secret = totp_secret
        self.session = SessionManager()
        self.api_session_key = None
        self.susertoken = None
        self.ltp_cache = {}

    # ------------------ Authentication ------------------
    def login(self, otp: str = None):
        """
        Login using OTP or TOTP. Stores api_session_key and susertoken in SessionManager.
        """
        url = f"https://signin.definedgesecurities.com/auth/realms/debroking/dsbpkc/login/{self.api_token}"
        payload = {"otp": otp} if otp else {}
        headers = {"api_secret": self.api_secret}
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "api_session_key" not in data or "susertoken" not in data:
            raise SessionError("Login failed: api_session_key or susertoken missing")
        self.api_session_key = data["api_session_key"]
        self.susertoken = data["susertoken"]
        self.session.save_session_key(self.api_session_key)
        return data

    # ------------------ Internal request helpers ------------------
    def _get_headers(self):
        if not self.api_session_key:
            raise SessionError("API session key not found. Login first.")
        return {"Authorization": self.api_session_key, "Content-Type": "application/json"}

    def _get(self, relative_url, params=None):
        url = f"{BASE_URL}{relative_url}"
        resp = requests.get(url, headers=self._get_headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, relative_url, data):
        url = f"{BASE_URL}{relative_url}"
        resp = requests.post(url, headers=self._get_headers(), json=data)
        resp.raise_for_status()
        return resp.json()

    # ------------------ Trading API ------------------
    def get_holdings(self):
        return self._get("/holdings")

    def get_positions(self):
        return self._get("/positions")

    def get_orders(self):
        return self._get("/orders")

    def get_trades(self):
        return self._get("/trades")

    def place_order(self, order_data: dict):
        return self._post("/placeorder", order_data)

    def cancel_order(self, order_id: str):
        return self._post(f"/cancel/{order_id}", {})

    def get_margin(self):
        return self._get("/margin")

    def get_limits(self):
        return self._get("/limits")

    def get_quote(self, exchange, token):
        return self._get(f"/quotes/{exchange}/{token}")

    # ------------------ Master & Historical ------------------
    def download_master(self, segment="ALL", save_path="./data/master.csv"):
        url = MASTER_URLS.get(segment.upper(), MASTER_URLS["ALL"])
        r = requests.get(url)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            z.extractall(os.path.dirname(save_path))
        return save_path

    def get_historical(self, segment, token, timeframe, from_dt, to_dt):
        """
        from_dt and to_dt should be datetime objects.
        """
        from_str = from_dt.strftime("%d%m%Y%H%M")
        to_str = to_dt.strftime("%d%m%Y%H%M")
        url = HISTORICAL_URL.format(segment=segment, token=token, timeframe=timeframe,
                                    from=from_str, to=to_str)
        resp = requests.get(url, headers={"Authorization": self.api_session_key})
        resp.raise_for_status()
        return resp.text

    # ------------------ WebSocket placeholder ------------------
    def subscribe_tokens(self, token_list):
        """
        Placeholder method for subscribing to tokens in WebSocket.
        token_list: list of "EX|TOKEN" strings
        """
        # This will be implemented in websocket.py
        pass
