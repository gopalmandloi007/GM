import logging
from trading_engine.api_client import APIClient
from trading_engine.session import get_session

logger = logging.getLogger(__name__)

class OrderManager:
    def __init__(self):
        self.client = APIClient()
        self.session = get_session()

    def place_order(self, symbol, qty, order_type="MARKET", side="BUY", product="CNC", price=None, trigger_price=None):
        """
        Place a new order (Normal + SL + SL-M + GTT).
        """
        payload = {
            "symbol": symbol,
            "quantity": qty,
            "order_type": order_type,
            "transaction_type": side,
            "product": product,
        }

        if price:
            payload["price"] = price
        if trigger_price:
            payload["trigger_price"] = trigger_price

        resp = self.client.post("/orders", payload)
        return resp

    def modify_order(self, order_id, price=None, qty=None, trigger_price=None):
        payload = {}
        if price:
            payload["price"] = price
        if qty:
            payload["quantity"] = qty
        if trigger_price:
            payload["trigger_price"] = trigger_price

        resp = self.client.put(f"/orders/{order_id}", payload)
        return resp

    def cancel_order(self, order_id):
        return self.client.delete(f"/orders/{order_id}")

    def order_book(self):
        return self.client.get("/orders")

    def trade_book(self):
        return self.client.get("/trades")

    def gtt_orders(self):
        return self.client.get("/gtt")

    def place_gtt(self, symbol, qty, trigger_price, price, side="BUY"):
        payload = {
            "symbol": symbol,
            "quantity": qty,
            "trigger_price": trigger_price,
            "price": price,
            "transaction_type": side,
            "type": "GTT",
        }
        return self.client.post("/gtt", payload)
