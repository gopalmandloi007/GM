# trading_engine/historical.py

import os
import datetime
from trading_engine.api_client import api_client
from utils.file_manager import save_json, load_json

DATA_DIR = "data/historical"

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_historical_data(symbol: str, start_date: str, end_date: str, interval: str = "1d"):
    """
    Fetches historical data for given symbol between dates.
    Stores locally to avoid re-downloads.
    """
    ensure_data_dir()
    file_path = os.path.join(DATA_DIR, f"{symbol}_{interval}.json")

    # Try cached data
    cached = load_json(file_path)
    if cached:
        return cached

    # Otherwise fetch from API
    data = api_client.get_historical(symbol, start_date, end_date, interval)
    save_json(file_path, data)
    return data

def get_previous_close(symbol: str, reference_date=None):
    """
    Get last available trading day's close (skips weekends/holidays).
    """
    ensure_data_dir()
    if reference_date is None:
        reference_date = datetime.date.today()

    # Go back max 10 days to ensure we cover long weekends
    start_date = reference_date - datetime.timedelta(days=10)
    end_date = reference_date - datetime.timedelta(days=1)

    data = api_client.get_historical(
        symbol,
        start_date.strftime("%Y-%m-%d"),
        reference_date.strftime("%Y-%m-%d"),
        interval="1d"
    )

    if not data:
        return None

    # Last valid close
    closes = [d for d in data if "close" in d]
    if not closes:
        return None

    return closes[-1]["close"]
