# trading_engine/orders.py
import logging
from typing import Dict, Any, Optional
from .api_client import APIClient
from .session import SessionManager
from .utils import get_sqlite_conn, now_ts

logger = logging.getLogger("trading_engine.orders")
logger.setLevel(logging.INFO)

class OrdersClient:
    def __init__(self, api_client: Optional[APIClient] = None):
        self.session = SessionManager.get()
        self.api = api_client or APIClient(self.session)
        self.conn = get_sqlite_conn()
        # ensure orders table exists
        from .utils import init_db_schema
        init_db_schema(self.conn)

    def place_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.api.place_order(payload)
        # persist orders in DB (orders array or single)
        try:
            orders = resp.get("orders") if isinstance(resp, dict) and "orders" in resp else [resp]
            cur = self.conn.cursor()
            for o in orders:
                order_id = o.get("order_id") or o.get("orderid") or o.get("orderId") or ""
                cur.execute("""
                INSERT OR REPLACE INTO orders (order_id, local_id, status, created_at, updated_at, filled_qty, avg_price, raw_response)
                VALUES (?,?,?,?,?,?,?,?)
                """, (
                    order_id,
                    None,
                    o.get("order_status") or o.get("status") or "UNKNOWN",
                    now_ts(),
                    now_ts(),
                    int(o.get("filled_qty") or 0),
                    float(o.get("average_traded_price") or 0.0),
                    str(o)
                ))
            self.conn.commit()
        except Exception as e:
            logger.warning("Failed to persist order: %s", e)
        return resp

    def get_order(self, order_id: str) -> Dict[str, Any]:
        resp = self.api.get_order(order_id)
        # update DB entry
        try:
            cur = self.conn.cursor()
            cur.execute("INSERT OR REPLACE INTO orders (order_id, status, updated_at, raw_response) VALUES (?,?,?,?)",
                        (order_id, resp.get("order_status") or "UNKNOWN", now_ts(), str(resp)))
            self.conn.commit()
        except Exception as e:
            logger.warning("Failed to update order in DB: %s", e)
        return resp

    def get_orders(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        return self.api.get_orders(params=params)

    def modify_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.api.modify_order(payload)
        return resp

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        resp = self.api.cancel_order(order_id)
        # update DB
        try:
            cur = self.conn.cursor()
            cur.execute("UPDATE orders SET status=?, updated_at=? WHERE order_id=?", ("CANCELLED", now_ts(), order_id))
            self.conn.commit()
        except Exception as e:
            logger.warning("Failed to update cancel in DB: %s", e)
        return resp

    # GTT / OCO wrappers
    def place_gtt(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.api.place_gtt(payload)

    def modify_gtt(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.api.modify_gtt(payload)

    def cancel_gtt(self, alert_id: str) -> Dict[str, Any]:
        return self.api.cancel_gtt(alert_id)

    def place_oco(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.api.place_oco(payload)

    def cancel_oco(self, alert_id: str) -> Dict[str, Any]:
        return self.api.cancel_oco(alert_id)

    def slice_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.api.slice_order(payload)

    # Margin / limits
    def get_margin(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        return self.api.get_margin(payload)
