# trading_engine/marketdata.py
from __future__ import annotations
import logging
import time
from typing import Optional, Dict, Any

from .websocket import WebSocketManager
from .historical import get_previous_trading_close
from .api_client import APIClient

logger = logging.getLogger("trading_engine.marketdata")
logger.setLevel(logging.INFO)

class MarketDataService:
    """
    WS-first LTP retrieval with REST/historical fallback.
    Returns dict: {"lp": float|None, "prev_close": float|None, "source": "ws/rest/file", "ts": epoch}
    """
    def __init__(self, api_client: Optional[APIClient] = None, ws_mgr: Optional[WebSocketManager] = None):
        self.api_client = api_client
        self.ws_mgr = ws_mgr

    def _ws_ltp(self, exchange: str, token: str) -> Optional[float]:
        if not self.ws_mgr:
            return None
        data = self.ws_mgr.get_ltp(exchange, token)
        if not data:
            return None
        val = data.get("lp") or data.get("lp")
        try:
            return float(val) if val is not None else None
        except Exception:
            return None

    def _rest_quote_ltp(self, exchange: str, token: str) -> Optional[float]:
        if not self.api_client:
            return None
        try:
            q = self.api_client.get_quote(exchange, token)
            # attempt many possible fields
            if isinstance(q, dict):
                for f in ("lp","ltp","last_price","lastTradedPrice","lastPrice"):
                    if f in q and q[f] not in (None, ""):
                        try:
                            return float(q[f])
                        except Exception:
                            continue
            return None
        except Exception as e:
            logger.debug("REST quote failed for %s|%s: %s", exchange, token, e)
            return None

    def get_ltp_prevclose(self, token: str, exchange: str = "NSE") -> Dict[str, Any]:
        """
        Returns combined info for token:
           { "lp": float|None, "prev_close": float|None, "source": "ws/rest/file", "ts": epoch }
        """
        ts = time.time()
        # 1) WS
        lp = self._ws_ltp(exchange, token)
        if lp is not None:
            # try to get prev close via REST quote if present
            prev = None
            try:
                if self.api_client:
                    q = self.api_client.get_quote(exchange, token)
                    # many broker APIs return prev close under 'c' or 'pc' or 'previous_close'
                    for k in ("previous_close","prevClose","c","pc","close_prev"):
                        if isinstance(q, dict) and k in q and q[k] not in (None, ""):
                            try:
                                prev = float(q[k])
                                break
                            except Exception:
                                prev = None
                # if prev still None, fallback to historical
                if prev is None:
                    prev = get_previous_trading_close(token)
            except Exception:
                prev = get_previous_trading_close(token)
            return {"lp": float(lp), "prev_close": (float(prev) if prev is not None else None), "source": "ws", "ts": ts}

        # 2) REST quote fallback
        lp = self._rest_quote_ltp(exchange, token)
        if lp is not None:
            prev = None
            try:
                q = self.api_client.get_quote(exchange, token)
                for k in ("previous_close","prevClose","c","pc","close_prev"):
                    if isinstance(q, dict) and k in q and q[k] not in (None, ""):
                        try:
                            prev = float(q[k])
                            break
                        except Exception:
                            prev = None
                if prev is None:
                    prev = get_previous_trading_close(token)
            except Exception:
                prev = get_previous_trading_close(token)
            return {"lp": float(lp), "prev_close": (float(prev) if prev is not None else None), "source": "rest", "ts": ts}

        # 3) historical file prev close fallback (no lp)
        prev = get_previous_trading_close(token)
        return {"lp": None, "prev_close": (float(prev) if prev is not None else None), "source": "file", "ts": ts}
