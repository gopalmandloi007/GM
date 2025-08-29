# gm/trading_engine/marketdata.py
import logging
import time
from typing import Optional, Dict, Any
from .websocket import WebSocketManager
from .historical import get_previous_trading_close
from .api_client import APIClient

logger = logging.getLogger("trading_engine.marketdata")
logger.setLevel(logging.INFO)

class MarketDataService:
    def __init__(self, api_client: Optional[APIClient] = None, ws_mgr: Optional[WebSocketManager] = None):
        self.api_client = api_client
        self.ws_mgr = ws_mgr

    def _ws_ltp(self, exchange: str, token: str) -> Optional[float]:
        if not self.ws_mgr:
            return None
        d = self.ws_mgr.get_ltp(exchange, token)
        if not d:
            return None
        return d.get("lp")

    def _rest_quote_ltp(self, exchange: str, token: str) -> Optional[float]:
        if not self.api_client:
            return None
        try:
            q = self.api_client.get_quote(exchange, token)
            if isinstance(q, dict):
                for k in ("lp","ltp","last_price","lastTradedPrice","lastPrice"):
                    if k in q and q[k] not in (None, ""):
                        try:
                            return float(q[k])
                        except Exception:
                            continue
            return None
        except Exception:
            return None

    def get_ltp_prevclose(self, token: str, exchange: str = "NSE") -> Dict[str, Any]:
        ts = time.time()
        # try ws
        lp = self._ws_ltp(exchange, token)
        if lp is not None:
            prev = None
            try:
                if self.api_client:
                    q = self.api_client.get_quote(exchange, token)
                    for k in ("previous_close","prevClose","pc","c","close_prev"):
                        if isinstance(q, dict) and k in q and q[k] not in (None,""):
                            prev = float(q[k])
                            break
            except Exception:
                prev = None
            if prev is None:
                prev = get_previous_trading_close(token)
            return {"lp": float(lp), "prev_close": (float(prev) if prev is not None else None), "source": "ws", "ts": ts}

        # rest fallback
        lp = self._rest_quote_ltp(exchange, token)
        if lp is not None:
            prev = None
            try:
                q = self.api_client.get_quote(exchange, token)
                for k in ("previous_close","prevClose","pc","c","close_prev"):
                    if isinstance(q, dict) and k in q and q[k] not in (None,""):
                        prev = float(q[k])
                        break
            except Exception:
                prev = None
            if prev is None:
                prev = get_previous_trading_close(token)
            return {"lp": float(lp), "prev_close": (float(prev) if prev is not None else None), "source": "rest", "ts": ts}

        prev = get_previous_trading_close(token)
        return {"lp": None, "prev_close": (float(prev) if prev is not None else None), "source": "file", "ts": ts}


# Module-level helper (fixed indentation)
def get_ltp(symbol: str, exchange: str = "NSE", api_client: Optional[APIClient] = None, ws_mgr: Optional[WebSocketManager] = None) -> Optional[float]:
    service = MarketDataService(api_client=api_client, ws_mgr=ws_mgr)
    data = service.get_ltp_prevclose(token=symbol, exchange=exchange)
    return data.get("lp")
