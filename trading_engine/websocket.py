# trading_engine/websocket.py
import json
import threading
import time
import logging
from typing import Callable, Optional, Set, Dict, Any
from websocket import WebSocketApp  # websocket-client
from .session import SessionManager
from .utils import get_sqlite_conn, init_db_schema, now_ts

logger = logging.getLogger("trading_engine.websocket")
logger.setLevel(logging.INFO)

WS_URL = "wss://trade.definedgesecurities.com/NorenWSTRTP/"

class WSManager:
    def __init__(self, session: Optional[SessionManager] = None):
        self.session = session or SessionManager.get()
        self.ws: Optional[WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = True
        self.subscribed: Set[str] = set()  # tokens subscribed in EXCH|TOKEN format
        self.on_message_cb: Optional[Callable[[dict], None]] = None
        self._ltp_cache: Dict[str, Dict[str, Any]] = {}  # key "EX|TOKEN" -> {lp, pc, ts}
        # DB
        self.conn = get_sqlite_conn()
        init_db_schema(self.conn)

    def _on_open(self, ws):
        logger.info("WS opened, sending connect payload")
        payload = {
            "t": "c",
            "uid": self.session.uid,
            "actid": self.session.uid,
            "source": "TRTP",
            "susertoken": self.session.susertoken
        }
        ws.send(json.dumps(payload))

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
        except Exception:
            data = {"raw": message}
        # if touchline feed ack or feed update, parse
        t = data.get("t")
        if t in ("tk", "tf"):  # subscription ack or feed
            # feed may contain tk (token) and lp (LTP), exchange 'e'
            exch = data.get("e")
            tk = data.get("tk")
            lp = data.get("lp") or data.get("lp")
            pc = data.get("pc")
            ts = now_ts()
            if exch and tk:
                key = f"{exch}|{str(tk)}"
                # update in-memory
                self._ltp_cache[key] = {"lp": float(lp) if lp else None, "pc": float(pc) if pc else None, "ts": ts}
                # persist to DB
                try:
                    cur = self.conn.cursor()
                    cur.execute("INSERT OR REPLACE INTO ltp_cache (exchange, token, lp, pc, ts) VALUES (?,?,?,?,?)",
                                (exch, str(tk), float(lp) if lp else None, float(pc) if pc else None, ts))
                    self.conn.commit()
                except Exception as e:
                    logger.debug("Failed writing ltp to DB: %s", e)
        # call user callback for all messages
        if self.on_message_cb:
            try:
                self.on_message_cb(data)
            except Exception as e:
                logger.exception("on_message_cb error: %s", e)

    def _on_error(self, ws, err):
        logger.error("WS error: %s", err)

    def _on_close(self, ws, code, msg):
        logger.info("WS closed: %s %s", code, msg)
        if not self._stop:
            time.sleep(2)
            self.start()  # auto reconnect

    def start(self, on_message: Optional[Callable[[dict], None]] = None):
        if not self.session.susertoken:
            raise RuntimeError("Session susertoken missing; login first.")
        if self.ws:
            return
        self.on_message_cb = on_message
        self._stop = False
        self.ws = WebSocketApp(
            WS_URL,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            header=[f"x-session-token: {self.session.susertoken}"]
        )
        self._thread = threading.Thread(target=self.ws.run_forever, kwargs={"ping_interval": 50}, daemon=True)
        self._thread.start()
        logger.info("WS thread started")

    def stop(self):
        self._stop = True
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None

    def subscribe_touchline(self, tokens: list):
        if not tokens:
            return
        k = "#".join(tokens)
        payload = {"t": "t", "k": k}
        if self.ws:
            self.ws.send(json.dumps(payload))
            self.subscribed.update(tokens)
            logger.info("Subscribed to %d tokens", len(tokens))

    def unsubscribe_touchline(self, tokens: list):
        if not tokens:
            return
        k = "#".join(tokens)
        payload = {"t": "u", "k": k}
        if self.ws:
            self.ws.send(json.dumps(payload))
            for t in tokens:
                self.subscribed.discard(t)
            logger.info("Unsubscribed tokens")

    def get_ltp(self, exchange: str, token: str):
        key = f"{exchange}|{token}"
        # check in-memory first
        v = self._ltp_cache.get(key)
        if v:
            return v
        # fallback to DB
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT lp, pc, ts FROM ltp_cache WHERE exchange=? AND token=?", (exchange, str(token)))
            row = cur.fetchone()
            if row:
                return {"lp": row["lp"], "pc": row["pc"], "ts": row["ts"]}
        except Exception:
            pass
        return None

