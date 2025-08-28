# trading_engine/websocket.py
import json
import threading
import logging
import time
from typing import Dict, Optional, Callable, List
from websocket import WebSocketApp  # pip install websocket-client

logger = logging.getLogger("trading_engine.websocket")
logger.setLevel(logging.INFO)

WS_URL = "wss://trade.definedgesecurities.com/NorenWSTRTP/"

class WebSocketManager:
    """
    Manage single WS connection to broker and maintain LTP cache.
    Key for LTP cache: "EX|TOKEN" e.g. "NSE|12847"
    """
    def __init__(self, uid: Optional[str]=None, actid: Optional[str]=None, susertoken: Optional[str]=None, on_raw: Optional[Callable]=None):
        self.uid = uid
        self.actid = actid or uid
        self.susertoken = susertoken
        self.on_raw = on_raw
        self.ws: Optional[WebSocketApp] = None
        self.thread: Optional[threading.Thread] = None
        self._run = False
        self.ltp_cache: Dict[str, Dict] = {}  # key -> {"lp": float, "ts": float, "raw": dict}
        self.subscribed: set = set()
        self._lock = threading.Lock()

    # -------------------- internal handlers --------------------
    def _on_open(self, ws):
        logger.info("WebSocket opened, sending connect payload...")
        payload = {"t":"c", "uid": self.uid, "actid": self.actid, "source": "TRTP", "susertoken": self.susertoken}
        try:
            ws.send(json.dumps(payload))
        except Exception as e:
            logger.exception("Failed to send connect payload: %s", e)

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
        except Exception:
            data = {"raw": message}
        t = data.get("t")
        # touchline ack or feed
        if t in ("tk","tf"):
            # token may be field 'tk'
            exch = data.get("e")
            tk = data.get("tk")
            lp = data.get("lp") or data.get("lp")
            if exch and tk:
                key = f"{exch}|{tk}"
                try:
                    lp_val = float(lp) if lp is not None else None
                except Exception:
                    lp_val = None
                with self._lock:
                    self.ltp_cache[key] = {"lp": lp_val, "ts": time.time(), "raw": data}
        # allow callback
        if self.on_raw:
            try:
                self.on_raw(data)
            except Exception:
                logger.exception("on_raw callback failed")

    def _on_error(self, ws, err):
        logger.error("WebSocket error: %s", err)

    def _on_close(self, ws, code, reason):
        logger.info("WebSocket closed: code=%s reason=%s", code, reason)
        self._run = False

    # -------------------- public API --------------------
    def start(self):
        """
        Start background websocket thread. Requires susertoken set.
        """
        if not self.susertoken:
            raise RuntimeError("susertoken not set; login first")
        if self.thread and self.thread.is_alive():
            logger.info("WebSocket already running")
            return
        self._run = True
        headers = [f"x-session-token: {self.susertoken}"]
        self.ws = WebSocketApp(WS_URL,
                              on_open=self._on_open,
                              on_message=self._on_message,
                              on_error=self._on_error,
                              on_close=self._on_close,
                              header=headers)
        def run():
            while self._run:
                try:
                    self.ws.run_forever(ping_interval=50, ping_timeout=10)
                except Exception as e:
                    logger.exception("WS run_forever exception: %s", e)
                # brief sleep before reconnect
                time.sleep(2)
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        logger.info("WebSocket thread started")

    def stop(self):
        self._run = False
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass

    def subscribe_touchline(self, token_keys: List[str]):
        """
        token_keys: list like ["NSE|12847","NSE|22"]
        sends subscription message with token list joined by '#'
        """
        if not self.ws:
            logger.warning("WS not started; cannot subscribe yet")
            return
        if not token_keys:
            return
        # build k string: EX|TOKEN#EX|TOKEN...
        k = "#".join(token_keys)
        payload = {"t":"t", "k": k}
        try:
            self.ws.send(json.dumps(payload))
            with self._lock:
                for tk in token_keys:
                    self.subscribed.add(tk)
        except Exception:
            logger.exception("Failed to send subscribe")

    def unsubscribe_touchline(self, token_keys: List[str]):
        if not self.ws:
            return
        if not token_keys:
            return
        k = "#".join(token_keys)
        payload = {"t":"u", "k": k}
        try:
            self.ws.send(json.dumps(payload))
            with self._lock:
                for tk in token_keys:
                    self.subscribed.discard(tk)
        except Exception:
            logger.exception("Failed to send unsubscribe")

    def get_ltp(self, exchange: str, token: str) -> Optional[Dict]:
        key = f"{exchange}|{token}"
        with self._lock:
            return self.ltp_cache.get(key)

    def get_all_ltps(self) -> Dict[str, Dict]:
        with self._lock:
            return dict(self.ltp_cache)
