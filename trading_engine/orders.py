# gm/trading_engine/orders.py
import logging
from typing import Optional, Dict, Any
from .api_client import APIClient
from utils.file_manager import log_order, log_trade, save_json_log

logger = logging.getLogger("trading_engine.orders")
logger.setLevel(logging.INFO)

class OrderManager:
    """
    High-level order helper that builds payloads for Definedge endpoints.
    Use an APIClient instance (with api_session_key set).
    """
    def __init__(self, client: APIClient):
        if not isinstance(client, APIClient):
            raise ValueError("client must be APIClient")
        self.client = client

    def place_order(self,
                    tradingsymbol: str,
                    exchange: str,
                    quantity: int,
                    price_type: str = "MARKET",
                    side: str = "BUY",
                    price: Optional[float] = 0,
                    trigger_price: Optional[float] = None,
                    product_type: str = "NORMAL",
                    validity: str = "DAY",
                    variety: str = "REGULAR",
                    disclosed_quantity: int = 0,
                    **extra):
        """
        Build payload and place order via /placeorder endpoint.
        Fields mapping aligns with docs sample.
        """
        payload: Dict[str, Any] = {
            "price_type": price_type,
            "tradingsymbol": tradingsymbol,
            "quantity": str(quantity),
            "price": str(price) if price is not None else "0",
            "product_type": product_type,
            "order_type": side.upper(),
            "exchange": exchange,
            "validity": validity,
            "variety": variety,
            "disclosed_quantity": str(disclosed_quantity)
        }
        if trigger_price is not None:
            payload["trigger_price"] = str(trigger_price)

        payload.update(extra)

        try:
            resp = self.client.post("/placeorder", json=payload)
            # log locally
            log_order(resp)
            return resp
        except Exception as e:
            logger.exception("place_order failed")
            raise

    def cancel_order(self, order_id: str):
        try:
            resp = self.client.get(f"/cancel/{order_id}")
            log_order({"action": "cancel", "order_id": order_id, "response": resp})
            return resp
        except Exception as e:
            logger.exception("cancel failed")
            raise

    def get_order(self, order_id: str):
        try:
            resp = self.client.get(f"/order/{order_id}")
            return resp
        except Exception as e:
            logger.exception("get order failed")
            raise

    def list_orders(self):
        try:
            resp = self.client.get("/orders")
            return resp
        except Exception as e:
            logger.exception("list orders failed")
            raise

    def list_trades(self):
        try:
            resp = self.client.get("/trades")
            return resp
        except Exception as e:
            logger.exception("list trades failed")
            raise

    # GTT helpers
    def list_gtt(self):
        return self.client.get("/gttorders")

    def place_gtt(self, payload: Dict[str, Any]):
        r = self.client.post("/gttplaceorder", json=payload)
        log_order({"gtt_place": r})
        return r

    def cancel_gtt(self, alert_id: str):
        r = self.client.get(f"/gttcancel/{alert_id}")
        log_order({"gtt_cancel": r})
        return r

    # OCO helpers
    def place_oco(self, payload: Dict[str, Any]):
        r = self.client.post("/ocoplaceorder", json=payload)
        log_order({"oco_place": r})
        return r

    def cancel_oco(self, alert_id: str):
        r = self.client.get(f"/ococancel/{alert_id}")
        log_order({"oco_cancel": r})
        return r
