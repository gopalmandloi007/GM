# trading_engine/api_client.py
import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("trading_engine.api_client")
logger.setLevel(logging.INFO)

BASE_AUTH = "https://signin.definedgesecurities.com/auth/realms/debroking/dsbpkc"
BASE_API = "https://integrate.definedgesecurities.com/dart/v1"
BASE_DATA = "https://data.definedgesecurities.com/sds"

class APIClient:
    def __init__(self, api_token: Optional[str]=None, api_secret: Optional[str]=None, api_session_key: Optional[str]=None, susertoken: Optional[str]=None, uid: Optional[str]=None):
        self.api_token = api_token
        self.api_secret = api_secret
        self.api_session_key = api_session_key
        self.susertoken = susertoken
        self.uid = uid

    # ----- Auth endpoints (step1/step2) -----
    def auth_step1(self) -> Dict[str,Any]:
        if not self.api_token:
            raise ValueError("api_token missing")
        url = f"{BASE_AUTH}/login/{self.api_token}"
        headers = {"api_secret": self.api_secret} if self.api_secret else {}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def auth_step2(self, otp_token: str, otp_code: str) -> Dict[str,Any]:
        url = f"{BASE_AUTH}/token"
        payload = {"otp_token": otp_token, "otp": otp_code}
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ----- OMS token (if required) -----
    def get_oms_token(self, jwt: Dict[str,Any]) -> Dict[str,Any]:
        url = f"{BASE_API}/token"  # per docs
        resp = requests.post(url, json=jwt, timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ----- Trading endpoints -----
    def _headers(self):
        hdr = {}
        if self.api_session_key:
            hdr["Authorization"] = f"Bearer {self.api_session_key}"
        return hdr

    def get_holdings(self) -> Dict[str,Any]:
        url = f"{BASE_API}/holdings"
        resp = requests.get(url, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_positions(self) -> Dict[str,Any]:
        url = f"{BASE_API}/positions"
        resp = requests.get(url, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_quote(self, exchange: str, token: str) -> Dict[str,Any]:
        url = f"{BASE_API}/quotes/{exchange}/{token}"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def place_order(self, payload: Dict[str,Any]) -> Dict[str,Any]:
        url = f"{BASE_API}/placeorder"
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def cancel_order(self, orderid: str) -> Dict[str,Any]:
        url = f"{BASE_API}/cancel/{orderid}"
        resp = requests.get(url, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_order(self, orderid: str) -> Dict[str,Any]:
        url = f"{BASE_API}/order/{orderid}"
        resp = requests.get(url, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    # Historical / master downloader (simple wrapper)
    def download_master(self, url: str, dest_path: str):
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(1024*16):
                f.write(chunk)
        return dest_path

    def get_historical_csv(self, segment: str, token: str, timeframe: str, frm: str, to: str) -> str:
        url = f"{BASE_DATA}/history/{segment}/{token}/{timeframe}/{frm}/{to}"
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.text
