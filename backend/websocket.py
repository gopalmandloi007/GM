# gm/trading_engine/websocket.py
import json
import threading
import time
import logging
from typing import Dict, Optional, Callable, List
from websocket import WebSocketApp

logger = logging.getLogger("trading_engine.websocket")
logger.setLevel(logging.INFO)

WS_URL = "wss://trade.definedgesecurities.com/NorenWSTRTP/"

class WebSocketManager:
    def __init__(self, uid: Optional[str] = None, actid: Optional[str] = None, susertoken: Optional[str] = None, on_raw: Optional[Callable] = None):
        self.uid = uid
        self.actid = actid or uid
        self.susertoken = susertoken
        self.on_raw = on_raw
        self.ws: Optional[WebSocketApp] = None
        self.run_thread: Optional[threading.Thread] = None
        self.heartbeat_thread: Optional[threading.Thread] = None
        self.running = False
        self.ltp_cache: Dict[str, Dict] = {}
        self.subscribed = set()
        self._lock = threading.Lock()

    def _on_open(self, ws):
        logger.info("WS open. sending connect.")
        payload = {"t": "c", "uid": self.uid, "actid": self.actid, "source": "TRTP", "susertoken": self.susertoken}
        try:
            ws.send(json.dumps(payload))
        except Exception as e:
            logger.exception("send connect failed: %s", e)

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
        except Exception:
            return
        t = data.get("t")
        if t in ("tk", "tf"):
            exch = data.get("e")
            tk = data.get("tk")
            lp = data.get("lp") or data.get("ltp") or data.get("last_price") or data.get("lp")
            if exch and tk:
                key = f"{exch}|{tk}"
                try:
                    lp_val = float(lp) if lp is not None else None
                except Exception:
                    lp_val = None
                with self._lock:
                    self.ltp_cache[key] = {"lp": lp_val, "ts": time.time(), "raw": data}
        if self.on_raw:
            try:
                self.on_raw(data)
            except Exception:
                logger.exception("on_raw callback failed")

    def _on_error(self, ws, err):
        logger.error("WS error: %s", err)

    def _on_close(self, ws, code, reason):
        logger.info("WS closed: %s %s", code, reason)
        self.running = False

    def start(self):
        if not self.susertoken:
            raise RuntimeError("susertoken required to start WS")
        if self.running:
            return
        headers = [f"x-session-token: {self.susertoken}"]
        self.ws = WebSocketApp(WS_URL,
                              on_open=self._on_open,
                              on_message=self._on_message,
                              on_error=self._on_error,
                              on_close=self._on_close,
                              header=headers)
        self.running = True

        def run_ws():
            while self.running:
                try:
                    self.ws.run_forever()
                except Exception as e:
                    logger.exception("WS run error: %s", e)
                time.sleep(2)

        def heartbeat_loop():
            # send json heartbeat {"t":"h"} every 50 seconds as required
            while self.running:
                try:
                    if self.ws and getattr(self.ws, "sock", None) and getattr(self.ws.sock, "connected", False):
                        try:
                            self.ws.send(json.dumps({"t": "h"}))
                        except Exception:
                            logger.exception("heartbeat send failed")
                    time.sleep(50)
                except Exception:
                    time.sleep(5)

        self.run_thread = threading.Thread(target=run_ws, daemon=True)
        self.run_thread.start()

        self.heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

        logger.info("WS threads started")

    def stop(self):
        self.running = False
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass

    def subscribe_touchline(self, token_keys: List[str]):
        if not self.ws:
            logger.warning("WS not running")
            return
        if not token_keys:
            return
        k = "#".join(token_keys)
        payload = {"t": "t", "k": k}
        try:
            self.ws.send(json.dumps(payload))
            with self._lock:
                for tk in token_keys:
                    self.subscribed.add(tk)
        except Exception:
            logger.exception("subscribe failed")

    def unsubscribe_touchline(self, token_keys: List[str]):
        if not self.ws:
            return
        if not token_keys:
            return
        k = "#".join(token_keys)
        payload = {"t": "u", "k": k}
        try:
            self.ws.send(json.dumps(payload))
            with self._lock:
                for tk in token_keys:
                    self.subscribed.discard(tk)
        except Exception:
            logger.exception("unsubscribe failed")

    def get_ltp(self, exchange: str, token: str) -> Optional[Dict]:
        key = f"{exchange}|{token}"
        with self._lock:
            return self.ltp_cache.get(key)
