# trading_engine/marketdata.py
import logging
from typing import Optional
from .websocket import WebSocketManager
from .api_client import APIClient
from .historical import get_last_close_from_file
import time

logger = logging.getLogger("trading_engine.marketdata")
logger.setLevel(logging.INFO)

class MarketDataService:
    """
    Provides LTP retrieval with WS-first then REST fallback.
    Requires:
      - ws_mgr: running WebSocketManager (optional)
      - api_client: APIClient instance (for REST quote fallback)
    """
    def __init__(self, api_client: Optional[APIClient]=None, ws_mgr: Optional[WebSocketManager]=None):
        self.api_client = api_client
        self.ws_mgr = ws_mgr

    def get_ltp_for_token(self, token: str, exchange: str = "NSE"):
        """
        Return dict: {"lp": float or None, "source":"ws" or "rest" or "file", "ts": epoch}
        """
        key = f"{exchange}|{token}"
        # Try websocket first
        if self.ws_mgr:
            ws_val = self.ws_mgr.get_ltp(exchange, token)
            if ws_val and ws_val.get("lp") is not None:
                return {"lp": ws_val.get("lp"), "source": "ws", "ts": ws_val.get("ts")}
        # fallback to REST quote (if API client available)
        if self.api_client:
            try:
                # api_client.get_quote returns whatever broker provides; normalize if possible
                q = self.api_client.get_quote(exchange, token)
                # some brokers return nested structure; we attempt safe extraction
                # try common fields
                lp = None
                if isinstance(q, dict):
                    # many APIs return 'lp' or 'last_price' or 'last_traded_price'
                    lp = q.get("lp") or q.get("ltp") or q.get("last_price") or q.get("lastTradedPrice")
                    if lp is None:
                        # sometimes nested
                        for v in ("last_price","ltp","lastTradedPrice"):
                            if v in q:
                                lp = q[v]
                                break
                if lp is not None:
                    try:
                        lp_val = float(lp)
                        return {"lp": lp_val, "source":"rest", "ts": time.time()}
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("REST quote fallback failed: %s", e)
        # final fallback: previous close from historical file
        try:
            prev_close = get_last_close_from_file(token)
            if prev_close is not None:
                return {"lp": float(prev_close), "source":"file", "ts": time.time()}
        except Exception:
            pass
        return {"lp": None, "source": None, "ts": time.time()}
