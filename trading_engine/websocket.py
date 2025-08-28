# trading_engine/websocket.py
import json
import threading
import logging
import time
from typing import Dict, Optional, Callable
from websocket import WebSocketApp  # pip install websocket-client

logger = logging.getLogger("trading_engine.websocket")
logger.setLevel(logging.INFO)

WS_URL = "wss://trade.definedgesecurities.com/NorenWSTRTP/"

class WebSocketManager:
    def __init__(self, uid: str = None, actid: str = None, susertoken: str = None, on_message_cb: Optional[Callable]=None):
        self.uid = uid
        self.actid = actid or uid
        self.susertoken = susertoken
        self.on_message_cb = on_message_cb
        self.ws_app = None
        self.thread = None
        self._stop = True
        self.ltp_cache: Dict[str, Dict] = {}  # key: "EX|TOKEN" -> {"lp":.., "ts":..}
        self.subscribed = set()

    def _on_open(self, ws):
        logger.info("WS open - sending connect")
        connect_msg = {"t":"c","uid": self.uid, "actid": self.actid, "source":"TRTP", "susertoken": self.susertoken}
        ws.send(json.dumps(connect_msg))

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
        except Exception:
            data = {"raw": message}
        t = data.get("t")
        # touchline feed or touchline ack
        if t in ("tk","tf"):
            exch = data.get("e")
            tk = data.get("tk")
            lp = data.get("lp") or data.get("lp")
            if exch and tk:
                key = f"{exch}|{tk}"
                try:
                    lp_val = float(lp) if lp is not None else None
                except Exception:
                    lp_val = None
                self.ltp_cache[key] = {"lp": lp_val, "raw": data, "ts": time.time()}
        # forward raw message to callback as well
        if self.on_message_cb:
            try:
                self.on_message_cb(data)
            except Exception as e:
                logger.exception("on_message_cb error: %s", e)

    def _on_error(self, ws, error):
        logger.error("WS error: %s", error)

    def _on_close(self, ws, code, reason):
        logger.info("WS closed: %s %s", code, reason)
        self._stop = True

    def start(self):
        if not self.susertoken:
            raise RuntimeError("susertoken missing; login first")
        if self.thread and self.thread.is_alive():
            return
        self._stop = False
        self.ws_app = WebSocketApp(WS_URL,
                                  on_open=self._on_open,
                                  on_message=self._on_message,
                                  on_error=self._on_error,
                                  on_close=self._on_close,
                                  header=[f"x-session-token: {self.susertoken}"])
        def run():
            self.ws_app.run_forever(ping_interval=50)
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        logger.info("WebSocket thread started")

    def stop(self):
        self._stop = True
        if self.ws_app:
            try:
                self.ws_app.close()
            except Exception:
                pass

    def subscribe_touchline(self, tokens:list):
        if not self.ws_app:
            logger.warning("WS not started; cannot subscribe yet")
            return
        if not tokens:
            return
        k = "#".join(tokens)
        payload = {"t":"t", "k": k}
        self.ws_app.send(json.dumps(payload))
        for t in tokens:
            self.subscribed.add(t)

    def unsubscribe_touchline(self, tokens:list):
        if not self.ws_app:
            return
        if not tokens:
            return
        k = "#".join(tokens)
        payload = {"t":"u", "k": k}
        self.ws_app.send(json.dumps(payload))
        for t in tokens:
            if t in self.subscribed:
                self.subscribed.remove(t)

    def get_ltp(self, exchange: str, token: str):
        key = f"{exchange}|{token}"
        return self.ltp_cache.get(key)
