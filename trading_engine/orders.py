# trading_engine/orders.py

import logging
from trading_engine.api_client import APIClient
from utils.file_manager import save_json_log

logger = logging.getLogger(__name__)


class OrderManager:
    def __init__(self, client: APIClient):
        self.client = client

    def place_order(self, symbol: str, qty: int, side: str, order_type: str,
                    price: float = None, stop_loss: float = None,
                    product_type: str = "MIS", validity: str = "DAY"):
        """
        Place a new order.

        :param symbol: Trading symbol (NSE only for now)
        :param qty: Quantity
        :param side: BUY or SELL
        :param order_type: MARKET / LIMIT / SL / SL-M
        :param price: Price (only for LIMIT / SL orders)
        :param stop_loss: Trigger price (for SL / SL-M)
        :param product_type: MIS / CNC / NRML
        :param validity: DAY / IOC
        """
        payload = {
            "symbol": symbol,
            "qty": qty,
            "side": side.upper(),
            "type": order_type.upper(),
            "product": product_type.upper(),
            "validity": validity.upper()
        }

        if order_type.upper() in ["LIMIT", "SL"]:
            if not price:
                raise ValueError("Price is required for LIMIT/SL order")
            payload["price"] = price

        if order_type.upper() in ["SL", "SL-M"]:
            if not stop_loss:
                raise ValueError("Stop loss trigger price required for SL/SL-M order")
            payload["trigger_price"] = stop_loss

        try:
            response = self.client.post("/orders", json=payload)
            logger.info(f"Order placed: {response}")
            save_json_log("orders", "placed_order", response)
            return response
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            raise

    def modify_order(self, order_id: str, qty: int = None,
                     price: float = None, stop_loss: float = None,
                     validity: str = None):
        """
        Modify existing order.
        """
        payload = {}
        if qty: payload["qty"] = qty
        if price: payload["price"] = price
        if stop_loss: payload["trigger_price"] = stop_loss
        if validity: payload["validity"] = validity.upper()

        try:
            response = self.client.put(f"/orders/{order_id}", json=payload)
            logger.info(f"Order modified: {response}")
            save_json_log("orders", "modified_order", response)
            return response
        except Exception as e:
            logger.error(f"Order modification failed: {e}")
            raise

    def cancel_order(self, order_id: str):
        """
        Cancel an existing order.
        """
        try:
            response = self.client.delete(f"/orders/{order_id}")
            logger.info(f"Order cancelled: {response}")
            save_json_log("orders", "cancelled_order", response)
            return response
        except Exception as e:
            logger.error(f"Order cancellation failed: {e}")
            raise

    def get_order_status(self, order_id: str):
        """
        Get order status/details.
        """
        try:
            response = self.client.get(f"/orders/{order_id}")
            logger.debug(f"Order status: {response}")
            return response
        except Exception as e:
            logger.error(f"Fetch order status failed: {e}")
            raise

    def list_orders(self, status: str = None):
        """
        List all orders (optionally filter by status).
        """
        try:
            response = self.client.get("/orders")
            orders = response.get("data", [])
            if status:
                orders = [o for o in orders if o.get("status") == status.upper()]
            return orders
        except Exception as e:
            logger.error(f"List orders failed: {e}")
            raise
