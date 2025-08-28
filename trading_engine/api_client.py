import requests
import logging
from datetime import datetime, timedelta

# Exceptions
class SessionError(Exception):
    pass

class APIError(Exception):
    pass

class APIClient:
    BASE_URL = "https://integrate.definedgesecurities.com/dart/v1"
    HISTORICAL_URL = "https://data.definedgesecurities.com/sds/history"
    MASTER_URLS = {
        "NSE_CASH": "https://app.definedgesecurities.com/public/nsecash.zip",
        "NSE_FNO": "https://app.definedgesecurities.com/public/nsefno.zip",
        "BSE_CASH": "https://app.definedgesecurities.com/public/bsecash.zip",
        "BSE_FNO": "https://app.definedgesecurities.com/public/bsefno.zip",
        "MCX_FNO": "https://app.definedgesecurities.com/public/mcxfno.zip",
        "ALL": "https://app.definedgesecurities.com/public/allmaster.zip"
    }

    def __init__(self, api_token: str, api_secret: str, totp_secret: str = None):
        self.api_token = api_token
        self.api_secret = api_secret
        self.totp_secret = totp_secret
        self.api_session_key = None
        self.susertoken = None
        self.uid = None
        self.headers = {}
        logging.basicConfig(level=logging.INFO)

    # ------------------- LOGIN & SESSION -------------------
    def login(self, otp_code: str = None):
        """Perform login using OTP/TOTP"""
        auth_url = f"https://signin.definedgesecurities.com/auth/realms/debroking/dsbpkc/login/{self.api_token}"
        data = {"otp": otp_code or self.generate_totp()}
        headers = {"api_secret": self.api_secret}

        resp = requests.post(auth_url, json=data, headers=headers)
        if resp.status_code != 200:
            raise SessionError(f"Login failed: {resp.text}")

        res = resp.json()
        self.api_session_key = res.get("api_session_key")
        self.susertoken = res.get("susertoken")
        self.uid = res.get("uid")
        if not self.api_session_key:
            raise SessionError("Login failed, api_session_key missing")

        self.headers = {"Authorization": self.api_session_key, "Content-Type": "application/json"}
        logging.info(f"Login successful for UID {self.uid}")
        return res

    def generate_totp(self):
        # TODO: Implement TOTP generation if needed
        return "000000"

    # ------------------- CORE GETTERS -------------------
    def get_holdings(self):
        url = f"{self.BASE_URL}/holdings"
        resp = requests.get(url, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    def get_positions(self):
        url = f"{self.BASE_URL}/positions"
        resp = requests.get(url, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    def get_orders(self):
        url = f"{self.BASE_URL}/orders"
        resp = requests.get(url, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    def get_trades(self):
        url = f"{self.BASE_URL}/trades"
        resp = requests.get(url, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    # ------------------- PLACE / MODIFY / CANCEL -------------------
    def place_order(self, payload: dict):
        url = f"{self.BASE_URL}/placeorder"
        resp = requests.post(url, json=payload, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    def modify_order(self, order_id: str, payload: dict):
        url = f"{self.BASE_URL}/modify"
        payload["order_id"] = order_id
        resp = requests.post(url, json=payload, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    def cancel_order(self, order_id: str):
        url = f"{self.BASE_URL}/cancel/{order_id}"
        resp = requests.post(url, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    # ------------------- GTT / OCO -------------------
    def gtt_place(self, payload: dict):
        url = f"{self.BASE_URL}/gttplaceorder"
        resp = requests.post(url, json=payload, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    def gtt_modify(self, alert_id: str, payload: dict):
        url = f"{self.BASE_URL}/gttmodify"
        payload["alert_id"] = alert_id
        resp = requests.post(url, json=payload, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    def gtt_cancel(self, alert_id: str):
        url = f"{self.BASE_URL}/gttcancel/{alert_id}"
        resp = requests.post(url, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    def oco_place(self, payload: dict):
        url = f"{self.BASE_URL}/ocoplaceorder"
        resp = requests.post(url, json=payload, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    def oco_modify(self, payload: dict):
        url = f"{self.BASE_URL}/ocomodify"
        resp = requests.post(url, json=payload, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    def oco_cancel(self, alert_id: str):
        url = f"{self.BASE_URL}/ococancel/{alert_id}"
        resp = requests.post(url, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    # ------------------- QUOTES -------------------
    def get_quote(self, exchange: str, token: str):
        url = f"{self.BASE_URL}/quotes/{exchange}/{token}"
        resp = requests.get(url, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    def get_security_info(self, exchange: str, token: str):
        url = f"{self.BASE_URL}/securityinfo/{exchange}/{token}"
        resp = requests.get(url, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    # ------------------- MARGIN / LIMITS -------------------
    def get_margin(self):
        url = f"{self.BASE_URL}/margin"
        resp = requests.get(url, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()

    def get_limits(self):
        url = f"{self.BASE_URL}/limits"
        resp = requests.get(url, headers=self.headers)
        if resp.status_code != 200:
            raise APIError(resp.text)
        return resp.json()
