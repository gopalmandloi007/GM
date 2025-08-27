# trading_engine/api_client.py
import time
import logging
from typing import Optional, Dict, Any
import requests
from .session import SessionManager, SessionError

logger = logging.getLogger("trading_engine.api_client")
logger.setLevel(logging.INFO)

CORE_BASE = "https://integrate.definedgesecurities.com/dart/v1"
HIST_BASE = "https://data.definedgesecurities.com/sds/history"
MASTER_BASE = "https://app.definedgesecurities.com/public"

class APIClient:
    def __init__(self, session: Optional[SessionManager] = None, timeout: int = 10):
        self.session = session or SessionManager.get()
        self.timeout = timeout

    def _headers(self, include_auth: bool = True) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if include_auth:
            # SessionManager.get_auth_headers returns {"Authorization": api_session_key}
            headers.update(self.session.get_auth_headers())
        return headers

    def _request(self, method: str, url: str, *, params: dict = None, json_body: dict = None, include_auth: bool = True) -> Any:
        try:
            r = requests.request(method, url, headers=self._headers(include_auth), params=params, json=json_body, timeout=self.timeout)
            if r.status_code == 401:
                # bubble up so caller can refresh
                logger.warning("401 Unauthorized from API: %s", url)
                raise SessionError("Unauthorized (401)")
            r.raise_for_status()
            try:
                return r.json()
            except ValueError:
                return r.text
        except requests.RequestException as e:
            logger.error("API request failed (%s): %s", url, e)
            raise

    # Core endpoints
    def place_order(self, payload: dict) -> dict:
        url = CORE_BASE + "/placeorder"
        return self._request("POST", url, json_body=payload)

    def get_orders(self, params: dict = None) -> dict:
        url = CORE_BASE + "/orders"
        return self._request("GET", url, params=params)

    def get_order(self, order_id: str) -> dict:
        url = CORE_BASE + f"/order/{order_id}"
        return self._request("GET", url)

    def modify_order(self, payload: dict) -> dict:
        url = CORE_BASE + "/modify"
        return self._request("POST", url, json_body=payload)

    def cancel_order(self, order_id: str) -> dict:
        url = CORE_BASE + f"/cancel/{order_id}"
        return self._request("POST", url)

    def slice_order(self, payload: dict) -> dict:
        url = CORE_BASE + "/sliceorder"
        return self._request("POST", url, json_body=payload)

    # GTT endpoints
    def get_gtts(self) -> dict:
        url = CORE_BASE + "/gttorders"
        return self._request("GET", url)

    def place_gtt(self, payload: dict) -> dict:
        url = CORE_BASE + "/gttplaceorder"
        return self._request("POST", url, json_body=payload)

    def modify_gtt(self, payload: dict) -> dict:
        url = CORE_BASE + "/gttmodify"
        return self._request("POST", url, json_body=payload)

    def cancel_gtt(self, alert_id: str) -> dict:
        url = CORE_BASE + f"/gttcancel/{alert_id}"
        return self._request("POST", url)

    # OCO endpoints
    def place_oco(self, payload: dict) -> dict:
        url = CORE_BASE + "/ocoplaceorder"
        return self._request("POST", url, json_body=payload)

    def modify_oco(self, payload: dict) -> dict:
        url = CORE_BASE + "/ocomodify"
        return self._request("POST", url, json_body=payload)

    def cancel_oco(self, alert_id: str) -> dict:
        url = CORE_BASE + f"/ococancel/{alert_id}"
        return self._request("POST", url)

    # Margin / limits
    def get_limits(self) -> dict:
        url = CORE_BASE + "/limits"
        return self._request("GET", url)

    def get_margin(self, payload: dict = None) -> dict:
        url = CORE_BASE + "/margin"
        # some implementations accept POST for margin with body, but docs show GET - support both
        if payload:
            return self._request("POST", url, json_body=payload)
        return self._request("GET", url)

    def spancalculator(self, payload: dict) -> dict:
        url = CORE_BASE + "/spancalculator"
        return self._request("POST", url, json_body=payload)

    # Quotes / security info
    def get_quote(self, exchange: str, token: str) -> dict:
        url = CORE_BASE + f"/quotes/{exchange}/{token}"
        return self._request("GET", url)

    def get_security_info(self, exchange: str, token: str) -> dict:
        url = CORE_BASE + f"/securityinfo/{exchange}/{token}"
        return self._request("GET", url)

    # Historical
    def get_historical(self, segment: str, token: str, timeframe: str, frm: str, to: str) -> str:
        url = f"{HIST_BASE}/{segment}/{token}/{timeframe}/{frm}/{to}"
        # historical API requires Authorization header too:
        return self._request("GET", url)
