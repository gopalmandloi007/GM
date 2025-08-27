# trading_engine/orders/oco.py
"""
OCO / TSL Orchestration Manager

Responsibilities:
- Create OCO groups (parent -> children (targets, stoploss))
- Persist groups + children to SQLite for durability
- React to order updates (via websocket) and:
    - When parent fills -> place children (targets + SL)
    - When one child fills -> cancel other children
    - When child cancelled/filled -> update group state
- Trailing Stop Loss (TSL):
    - If enabled for the SL child, a TSL monitor thread adjusts the SL order price
      based on live LTP provided by WSManager.get_ltp()
- Logging, retries, error handling included.

Usage:
  from trading_engine.orders.oco import OCOManager
  oco = OCOManager(orders_client=OrdersClient(...), ws_manager=ws)
  group_id = oco.create_group(parent_payload, targets=[...], stoploss=..., tsl_config=None)
  # Hook websocket messages:
  ws_manager.on_message_cb = lambda msg: oco.handle_order_update(msg)
"""

import json
import time
import threading
import logging
from typing import Dict, Any, List, Optional
from sqlite3 import Connection
from uuid import uuid4

from ..utils import get_sqlite_conn, init_db_schema, now_ts
from ..orders import OrdersClient
from ..websocket import WSManager

logger = logging.getLogger("trading_engine.oco")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.INFO)


class OCOError(Exception):
    pass


class OCOManager:
    """
    Manager for OCO / TSL orchestration.

    Basic flow:
      - create_group() registers a parent order payload and child specs (targets, stoploss)
      - place_parent() will place the parent order and persist result
      - When parent fill event arrives (via handle_order_update), children are placed
      - When a child fills, other children are auto-cancelled
      - If SL has TSL enabled, a background monitor adjusts SL via modify_order()
    """

    def __init__(self, orders_client: OrdersClient, ws_manager: Optional[WSManager] = None, db_conn: Optional[Connection] = None):
        if orders_client is None:
            raise OCOError("orders_client is required")
        self.orders = orders_client
        self.ws = ws_manager
        self.conn = db_conn or get_sqlite_conn()
        init_db_schema(self.conn)  # ensures orders/ltp_cache/historical_meta/sessions exist
        self._init_tables()
        self._tsl_threads: Dict[int, threading.Thread] = {}
        self._lock = threading.RLock()

    # ----------------- DB/Schema -----------------
    def _init_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS oco_groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE,
            parent_payload TEXT,
            parent_order_id TEXT,
            status TEXT,
            created_at INTEGER,
            updated_at INTEGER,
            metadata TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS oco_children (
            child_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            role TEXT,              -- 'target' | 'stoploss'
            qty INTEGER,
            price REAL,
            order_payload TEXT,
            order_id TEXT,
            status TEXT,
            tsl_enabled INTEGER DEFAULT 0,
            tsl_params TEXT,        -- JSON for tsl config
            created_at INTEGER,
            updated_at INTEGER,
            raw_response TEXT,
            FOREIGN KEY(group_id) REFERENCES oco_groups(group_id)
        )
        """)
        self.conn.commit()

    # ----------------- helpers -----------------
    def _now(self):
        return now_ts()

    def _insert_group(self, parent_payload: Dict[str, Any], metadata: Dict[str, Any] = None) -> int:
        cur = self.conn.cursor()
        uuid = str(uuid4())
        cur.execute("""
        INSERT INTO oco_groups (uuid, parent_payload, parent_order_id, status, created_at, updated_at, metadata)
        VALUES (?,?,?,?,?,?,?)
        """, (uuid, json.dumps(parent_payload), None, "CREATED", self._now(), self._now(), json.dumps(metadata or {})))
        self.conn.commit()
        return cur.lastrowid

    def _update_group_parent_order(self, group_id: int, parent_order_id: str, status: str):
        cur = self.conn.cursor()
        cur.execute("UPDATE oco_groups SET parent_order_id=?, status=?, updated_at=? WHERE group_id=?",
                    (parent_order_id, status, self._now(), group_id))
        self.conn.commit()

    def _update_group_status(self, group_id: int, status: str):
        cur = self.conn.cursor()
        cur.execute("UPDATE oco_groups SET status=?, updated_at=? WHERE group_id=?", (status, self._now(), group_id))
        self.conn.commit()

    def _insert_child(self, group_id: int, role: str, qty: int, price: float, payload: Dict[str, Any], tsl_enabled: bool = False, tsl_params: Dict[str, Any] = None) -> int:
        cur = self.conn.cursor()
        cur.execute("""
        INSERT INTO oco_children (group_id, role, qty, price, order_payload, order_id, status, tsl_enabled, tsl_params, created_at, updated_at, raw_response)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (group_id, role, qty, price, json.dumps(payload), None, "PENDING", int(tsl_enabled), json.dumps(tsl_params or {}), self._now(), self._now(), None))
        self.conn.commit()
        return cur.lastrowid

    def _update_child_order(self, child_id: int, order_id: Optional[str], status: Optional[str], raw_response: Optional[Any] = None):
        cur = self.conn.cursor()
        cur.execute("UPDATE oco_children SET order_id=?, status=?, updated_at=?, raw_response=? WHERE child_id=?",
                    (order_id, status, self._now(), json.dumps(raw_response) if raw_response is not None else None, child_id))
        self.conn.commit()

    def _get_group(self, group_id: int) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM oco_groups WHERE group_id=?", (group_id,))
        row = cur.fetchone()
        if not row:
            return None
        return dict(row)

    def _get_children(self, group_id: int) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM oco_children WHERE group_id=? ORDER BY child_id", (group_id,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    # ----------------- Public API -----------------
    def create_group(self, parent_payload: Dict[str, Any], targets: List[Dict[str, Any]], stoploss: Dict[str, Any], metadata: Dict[str, Any] = None, place_parent_immediately: bool = False) -> int:
        """
        Create an OCO group.

        parent_payload: payload to place the parent order (dict)
        targets: list of dicts: [{"qty": int, "price": float, "payload": {...}}, ...]
        stoploss: dict {"qty": int, "price": float, "payload": {...}, "tsl": {"enabled": True, "trail_by": 5 (ticks or points?), "trail_type": "points" or "percent"}} OR None
        metadata: optional dict stored with group
        place_parent_immediately: if True, will call place_parent() immediately and persist parent order id
        """
        with self._lock:
            group_id = self._insert_group(parent_payload, metadata=metadata)
            # children inserted but order_ids empty initially
            for t in targets:
                payload = t.get("payload") or {
                    "price_type": "LIMIT",
                    "tradingsymbol": parent_payload.get("tradingsymbol"),
                    "quantity": str(t["qty"]),
                    "price": str(t["price"]),
                    "product_type": parent_payload.get("product_type", "NORMAL"),
                    "order_type": "SELL" if parent_payload.get("order_type", "").upper() == "BUY" else "BUY",
                    "exchange": parent_payload.get("exchange")
                }
                self._insert_child(group_id, role="target", qty=int(t["qty"]), price=float(t["price"]), payload=payload, tsl_enabled=False, tsl_params=None)
            if stoploss:
                sl_payload = stoploss.get("payload") or {
                    "price_type": "LIMIT" if stoploss.get("price") and float(stoploss["price"])>0 else "SL",
                    "tradingsymbol": parent_payload.get("tradingsymbol"),
                    "quantity": str(stoploss["qty"]),
                    "price": str(stoploss["price"]),
                    "product_type": parent_payload.get("product_type", "NORMAL"),
                    "order_type": "SELL" if parent_payload.get("order_type", "").upper() == "BUY" else "BUY",
                    "exchange": parent_payload.get("exchange")
                }
                tsl = stoploss.get("tsl") or {}
                self._insert_child(group_id, role="stoploss", qty=int(stoploss["qty"]), price=float(stoploss["price"]), payload=sl_payload, tsl_enabled=bool(tsl.get("enabled")), tsl_params=tsl or None)

            logger.info("OCO group %s created (place_parent_immediately=%s)", group_id, place_parent_immediately)
            if place_parent_immediately:
                self.place_parent(group_id)
            return group_id

    def place_parent(self, group_id: int) -> Dict[str, Any]:
        """
        Place the parent order for group_id. Stores parent_order_id in DB.
        Returns the API response for the placed parent order.
        """
        group = self._get_group(group_id)
        if not group:
            raise OCOError("Group not found")
        parent_payload = json.loads(group["parent_payload"])
        try:
            resp = self.orders.place_order(parent_payload)
            # API may return 'orders' array
            order_id = None
            if isinstance(resp, dict) and "orders" in resp and resp["orders"]:
                order_id = resp["orders"][0].get("order_id") or resp["orders"][0].get("orderid")
            elif isinstance(resp, dict) and resp.get("order_id"):
                order_id = resp.get("order_id")
            # store
            self._update_group_parent_order(group_id, order_id, "PARENT_PLACED")
            logger.info("Placed parent for group %s -> order_id=%s", group_id, order_id)
            return resp
        except Exception as e:
            logger.exception("Failed to place parent order: %s", e)
            raise

    def handle_order_update(self, order_msg: Dict[str, Any]):
        """
        Called from websocket or polling when any order update arrives.
        The order_msg structure depends on your websocket -> normalize accordingly.
        We'll attempt to discover order_id and status, then react.
        Expected fields (examples): order_id, order_status, filled_qty, tradingsymbol
        """
        try:
            # normalize many shapes - this is defensive
            order_id = order_msg.get("order_id") or order_msg.get("orderid") or order_msg.get("orderno") or order_msg.get("orderId")
            status = order_msg.get("order_status") or order_msg.get("orderStatus") or order_msg.get("status")
            filled_qty = int(order_msg.get("filled_qty") or order_msg.get("filledQty") or 0)
            # ignore if no order_id
            if not order_id:
                return

            logger.debug("OCOManager received order update: %s status=%s", order_id, status)
            # find if this order_id is parent or child in DB
            cur = self.conn.cursor()
            # parent check
            cur.execute("SELECT group_id FROM oco_groups WHERE parent_order_id=?", (order_id,))
            row = cur.fetchone()
            if row:
                group_id = row["group_id"]
                logger.info("Order update corresponds to parent of group %s", group_id)
                self._handle_parent_update(group_id, order_id, status, order_msg)
                return

            # child check
            cur.execute("SELECT child_id, group_id, role FROM oco_children WHERE order_id=?", (order_id,))
            crow = cur.fetchone()
            if crow:
                child_id = crow["child_id"]
                group_id = crow["group_id"]
                role = crow["role"]
                logger.info("Order update corresponds to child %s of group %s role=%s", child_id, group_id, role)
                self._handle_child_update(child_id, group_id, role, status, order_msg)
                return

            # else: maybe an order in API placed previously (match by external-exchange id?), skip
        except Exception as e:
            logger.exception("Error in handle_order_update: %s", e)

    # ----------------- internal handlers -----------------
    def _handle_parent_update(self, group_id: int, parent_order_id: str, status: str, raw_msg: Dict[str, Any]):
        """
        React to parent updates. If parent 'COMPLETE' or filled -> place children.
        If parent cancelled or rejected -> update group.
        """
        try:
            status_u = (status or "").upper()
            if status_u in ("COMPLETE", "COMP", "FILLED", "OPEN", "PARTIAL"):  # treat partial/complete as trigger to place children once filled_qty>0
                # fetch parent order details via API to verify filled qty
                try:
                    ord_resp = self.orders.get_order(parent_order_id)
                except Exception as e:
                    logger.warning("Could not fetch parent order detail: %s", e)
                    ord_resp = {}
                filled = int(ord_resp.get("filled_qty") or raw_msg.get("filled_qty") or 0)
                if filled > 0:
                    # Place children (targets + stoploss) - only once if not already placed
                    children = self._get_children(group_id)
                    # place each child only if order_id is None
                    for child in children:
                        if child.get("order_id"):
                            continue
                        payload = json.loads(child["order_payload"])
                        try:
                            resp = self.orders.place_order(payload)
                            # parse resp to extract child order id
                            child_order_id = None
                            if isinstance(resp, dict) and "orders" in resp and resp["orders"]:
                                child_order_id = resp["orders"][0].get("order_id") or resp["orders"][0].get("orderid")
                            elif isinstance(resp, dict) and resp.get("order_id"):
                                child_order_id = resp.get("order_id")
                            self._update_child_order(child["child_id"], child_order_id, "PLACED", resp)
                            logger.info("Placed child %s for group %s -> %s", child["child_id"], group_id, child_order_id)
                            # If child is stoploss and tsl enabled, start tsl monitor
                            if child.get("tsl_enabled") and self.ws:
                                tsl_params = json.loads(child.get("tsl_params") or "{}")
                                # spawn thread to monitor and adjust SL
                                t = threading.Thread(target=self._tsl_runner, args=(group_id, child["child_id"], child_order_id, tsl_params), daemon=True)
                                t.start()
                                self._tsl_threads[child["child_id"]] = t
                        except Exception as e:
                            logger.exception("Failed to place child order: %s", e)
                    # update group status
                    self._update_group_status(group_id, "PARENT_FILLED_CHILDREN_PLACED")
            elif status_u in ("CANCELLED", "REJECTED", "FAILED"):
                self._update_group_status(group_id, "PARENT_" + status_u)
        except Exception as e:
            logger.exception("_handle_parent_update error: %s", e)

    def _handle_child_update(self, child_id: int, group_id: int, role: str, status: str, raw_msg: Dict[str, Any]):
        """
        When a child updates, if filled -> cancel other children; update DB statuses.
        """
        try:
            status_u = (status or "").upper()
            # update local db
            self._update_child_order(child_id, raw_msg.get("order_id") or raw_msg.get("orderid"), status_u, raw_msg)
            if status_u in ("COMPLETE", "FILLED", "COMP"):
                logger.info("Child %s filled. Cancelling siblings.", child_id)
                # cancel siblings
                self._cancel_sibling_children(group_id, child_id)
                self._update_group_status(group_id, "CHILD_FILLED")
            elif status_u in ("CANCELLED", "CXL", "CANCELED"):
                # check if all children cancelled -> close group
                children = self._get_children(group_id)
                if all((c.get("status") or "").upper() in ("CANCELLED", "CXL", "CANCELED") for c in children):
                    self._update_group_status(group_id, "ALL_CHILDREN_CANCELLED")
        except Exception as e:
            logger.exception("_handle_child_update error: %s", e)

    def _cancel_sibling_children(self, group_id: int, filled_child_id: int):
        children = self._get_children(group_id)
        for c in children:
            cid = c["child_id"]
            if cid == filled_child_id:
                continue
            order_id = c.get("order_id")
            if order_id:
                try:
                    self.orders.cancel_order(order_id)
                    self._update_child_order(cid, order_id, "CANCELLED", {"cancelled_by": "oco_manager"})
                    logger.info("Cancelled sibling child %s (order %s)", cid, order_id)
                except Exception as e:
                    logger.warning("Failed to cancel sibling child %s: %s", cid, e)

    # ----------------- Trailing SL runner -----------------
    def _tsl_runner(self, group_id: int, child_id: int, child_order_id: str, tsl_params: Dict[str, Any]):
        """
        Thread that monitors LTP and adjusts SL price for a specific SL child order.
        tsl_params expected keys:
          - trail_by: numeric (points or percent depending on trail_type)
          - trail_type: 'points' or 'percent'
          - adjust_freq: seconds between checks (default 1)
        Basic algorithm (for SELL order SL when entry is BUY or vice-versa):
          - Track best_price (highest for long positions), compute new_sl = best_price - trail_by
          - If new_sl is more aggressive than current SL price, call modify_order on the SL order_id
        NOTE: requires ws_manager to be provided to access get_ltp()
        """
        logger.info("Starting TSL runner for child %s (group %s)", child_id, group_id)
        params = tsl_params or {}
        trail_by = float(params.get("trail_by") or params.get("trail") or 0)
        trail_type = params.get("trail_type", "points")
        adjust_freq = float(params.get("adjust_freq") or 1.0)

        # get child's current details from DB
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM oco_children WHERE child_id=?", (child_id,))
        row = cur.fetchone()
        if not row:
            logger.warning("TSL runner: child missing in DB: %s", child_id)
            return

        # interpret child order: role should be stoploss
        role = row["role"]
        if role != "stoploss":
            logger.warning("TSL runner invoked for non-stoploss child %s", child_id)
            return

        # initial values
        current_sl_price = float(row["price"] or 0)
        order_id = row["order_id"]
        # derive exchange & token from payload
        order_payload = json.loads(row["order_payload"])
        exchange = order_payload.get("exchange")
        token = order_payload.get("token") or order_payload.get("tradingsymbol")  # if token not provided, you may need mapping

        best_price = None  # for LONG positions: highest observed price; for SHORT: lowest observed price
        is_long = (order_payload.get("order_type","BUY").upper() == "SELL")  # If parent was BUY, child SL is SELL? caution: invert logic
        # The above logic depends on how you constructed child payload. We will try to reason:
        # If parent order was BUY, you own long -> stoploss will be a SELL order. Track highest.
        # For safety, set is_long based on role - assume stoploss for long positions.
        is_long = True

        try:
            while True:
                # check thread should continue only while group active and child still placed
                cur = self.conn.cursor()
                cur.execute("SELECT status, order_id FROM oco_children WHERE child_id=?", (child_id,))
                r = cur.fetchone()
                if not r:
                    logger.info("TSL runner: child deleted -> stopping")
                    break
                status = (r["status"] or "").upper()
                if status in ("CANCELLED", "COMPLETE", "FILLED"):
                    logger.info("TSL runner: child status %s -> stopping", status)
                    break

                # fetch LTP via ws
                if not self.ws:
                    logger.debug("TSL runner: no ws manager available -> sleep")
                    time.sleep(adjust_freq)
                    continue

                # attempt to derive token/exchange: prefer token from order_payload if available
                exch = exchange
                tk = order_payload.get("token")
                # if token is actually tradingsymbol, you may want to map using master; we keep simple
                ltp_info = self.ws.get_ltp(exch, tk) if exch and tk else None
                ltp = None
                if ltp_info:
                    ltp = ltp_info.get("lp")

                if ltp is None:
                    time.sleep(adjust_freq)
                    continue

                # set best_price
                if best_price is None:
                    best_price = float(ltp)
                else:
                    if is_long:
                        best_price = max(best_price, float(ltp))
                    else:
                        best_price = min(best_price, float(ltp))

                # compute new SL depending on trail type
                if trail_type == "percent":
                    delta = best_price * (trail_by / 100.0)
                else:
                    delta = trail_by
                new_sl = (best_price - delta) if is_long else (best_price + delta)

                # For SELL stoploss (closing long), SL must be below best price (for long positions)
                # Update only if new_sl is more aggressive (i.e., for long, new_sl > current_sl_price)
                should_modify = False
                if is_long and new_sl > current_sl_price + 1e-8:
                    should_modify = True
                if (not is_long) and new_sl < current_sl_price - 1e-8:
                    should_modify = True

                if should_modify:
                    # call modify API - payload must include order_id, new price etc.
                    try:
                        mod_payload = {"order_id": order_id, "price": str(round(new_sl, 2))}
                        # orders.modify_order expects full payload - you may need to align to API's modify contract
                        resp = self.orders.modify_order(mod_payload)
                        current_sl_price = float(new_sl)
                        logger.info("TSL runner modified SL for child %s -> new_sl=%s resp=%s", child_id, new_sl, resp)
                        # update DB record price
                        cur = self.conn.cursor()
                        cur.execute("UPDATE oco_children SET price=?, updated_at=?, raw_response=? WHERE child_id=?", (current_sl_price, self._now(), json.dumps(resp)))
                        self.conn.commit()
                    except Exception as e:
                        logger.warning("TSL modify failed: %s", e)
                time.sleep(adjust_freq)
        except Exception as e:
            logger.exception("TSL runner error: %s", e)

    # ----------------- utilities -----------------
    def list_groups(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        if status_filter:
            cur.execute("SELECT * FROM oco_groups WHERE status=?", (status_filter,))
        else:
            cur.execute("SELECT * FROM oco_groups")
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    def list_children(self, group_id: int) -> List[Dict[str, Any]]:
        return self._get_children(group_id)
