# trading_engine/orders.py
import logging
from typing import Dict, Any, Optional
from .api_client import APIClient

logger = logging.getLogger("trading_engine.orders")
logger.setLevel(logging.INFO)

class OrderManager:
    def __init__(self, api_client: APIClient):
        self.client = api_client

    def place_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.client.place_order(payload)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        return self.client.cancel_order(order_id)

    def modify_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.client.modify_order(payload)

    # Wrapper helpers
    def place_market_order(self, exchange: str, tradingsymbol: str, qty: int, product_type: str, order_type: str):
        payload = {
            "price_type": "MARKET",
            "tradingsymbol": tradingsymbol,
            "quantity": str(qty),
            "price": "0",
            "product_type": product_type,
            "order_type": order_type,
            "exchange": exchange
        }
        return self.place_order(payload)
