# gm/trading_engine/api_client.py
import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("trading_engine.api_client")
logger.setLevel(logging.INFO)

BASE_AUTH = "https://signin.definedgesecurities.com/auth/realms/debroking/dsbpkc"
BASE_API = "https://integrate.definedgesecurities.com/dart/v1"
BASE_DATA = "https://data.definedgesecurities.com/sds"

class APIClient:
    def __init__(self,
                 api_token: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 api_session_key: Optional[str] = None,
                 susertoken: Optional[str] = None,
                 uid: Optional[str] = None):
        self.api_token = api_token
        self.api_secret = api_secret
        self.api_session_key = api_session_key
        self.susertoken = susertoken
        self.uid = uid
        self._timeout = 15

    # ----- Auth endpoints (step1/step2) -----
    def auth_step1(self) -> Dict[str, Any]:
        if not self.api_token:
            raise ValueError("api_token missing")
        url = f"{BASE_AUTH}/login/{self.api_token}"
        headers = {}
        if self.api_secret:
            headers["api_secret"] = self.api_secret
        resp = requests.get(url, headers=headers, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def auth_step2(self, otp_token: str, otp_code: str) -> Dict[str, Any]:
        url = f"{BASE_AUTH}/token"
        payload = {"otp_token": otp_token, "otp": otp_code}
        headers = {}
        # some endpoints expect api_secret in header while exchanging; include if present
        if self.api_secret:
            headers["api_secret"] = self.api_secret
        resp = requests.post(url, json=payload, headers=headers, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    # Generic request helpers (so other modules can call client.get/post/put/delete)
    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if path.startswith("/"):
            return BASE_API + path
        return BASE_API + "/" + path

    def _headers(self) -> Dict[str, str]:
        hdr: Dict[str, str] = {"Content-Type": "application/json"}
        # Per Definedge docs "Authorization: Actual value of api_session_key"
        if self.api_session_key:
            hdr["Authorization"] = str(self.api_session_key)
        return hdr

    def get(self, path: str, params: Optional[Dict] = None, timeout: Optional[int] = None):
        url = self._build_url(path)
        t = timeout or self._timeout
        r = requests.get(url, headers=self._headers(), params=params, timeout=t)
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            return r.text

    def post(self, path: str, json: Optional[Dict] = None, timeout: Optional[int] = None):
        url = self._build_url(path)
        t = timeout or self._timeout
        r = requests.post(url, headers=self._headers(), json=json, timeout=t)
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            return r.text

    def put(self, path: str, json: Optional[Dict] = None, timeout: Optional[int] = None):
        url = self._build_url(path)
        t = timeout or self._timeout
        r = requests.put(url, headers=self._headers(), json=json, timeout=t)
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            return r.text

    def delete(self, path: str, timeout: Optional[int] = None):
        url = self._build_url(path)
        t = timeout or self._timeout
        r = requests.delete(url, headers=self._headers(), timeout=t)
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            return r.text

    # ----- Convenience / specific endpoints -----
    def get_holdings(self):
        return self.get("/holdings")

    def get_positions(self):
        return self.get("/positions")

    def get_quote(self, exchange: str, token: str):
        return self.get(f"/quotes/{exchange}/{token}")

    def place_order(self, payload: Dict[str, Any]):
        return self.post("/placeorder", json=payload)

    def cancel_order(self, orderid: str):
        # docs show /cancel/{orderid} (GET in some examples)
        return self.get(f"/cancel/{orderid}")

    def get_order(self, orderid: str):
        return self.get(f"/order/{orderid}")

    def list_orders(self):
        return self.get("/orders")

    def get_trades(self):
        return self.get("/trades")

    # GTT
    def list_gtt(self):
        return self.get("/gttorders")

    def place_gtt(self, payload: Dict[str, Any]):
        return self.post("/gttplaceorder", json=payload)

    def cancel_gtt(self, alert_id: str):
        return self.get(f"/gttcancel/{alert_id}")

    # OCO
    def place_oco(self, payload: Dict[str, Any]):
        return self.post("/ocoplaceorder", json=payload)

    def cancel_oco(self, alert_id: str):
        return self.get(f"/ococancel/{alert_id}")

    # Historical / master downloader (simple wrapper)
    def download_master(self, url: str, dest_path: str):
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(1024 * 16):
                f.write(chunk)
        return dest_path

    def get_historical_raw(self, segment: str, token: str, timeframe: str, frm: str, to: str):
        url = f"{BASE_DATA}/history/{segment}/{token}/{timeframe}/{frm}/{to}"
        r = requests.get(url, headers=self._headers(), timeout=60)
        r.raise_for_status()
        # sometimes CSV, sometimes JSON — return raw text
        return r.text
