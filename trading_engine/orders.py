import pandas as pd
import os
from utils.file_manager import ensure_folder

ORDERS_FILE = "data/orders.csv"
SYMBOLS_FILE = "data/symbols.csv"

def ensure_orders_file():
    ensure_folder("data")
    if not os.path.exists(ORDERS_FILE):
        df = pd.DataFrame(columns=["symbol", "side", "quantity", "price", "type", "status"])
        df.to_csv(ORDERS_FILE, index=False)

def place_order(symbol, side, qty, price, order_type="MARKET"):
    """
    Place Order -> For now it just logs into CSV (later can integrate broker API)
    """
    ensure_orders_file()
    try:
        df = pd.read_csv(ORDERS_FILE)
        new_order = {
            "symbol": symbol,
            "side": side,
            "quantity": qty,
            "price": price,
            "type": order_type,
            "status": "OPEN"
        }
        df = pd.concat([df, pd.DataFrame([new_order])], ignore_index=True)
        df.to_csv(ORDERS_FILE, index=False)
        return {"status": "success", "message": "Order logged"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_all_symbols():
    """
    Return symbol list for dropdown (from symbols.csv or default NIFTY50)
    """
    if os.path.exists(SYMBOLS_FILE):
        df = pd.read_csv(SYMBOLS_FILE)
        return df["symbol"].tolist()
    return ["RELIANCE", "HDFCBANK", "INFY", "TCS", "SBIN"]
