import pandas as pd
import os
from datetime import datetime, timedelta
from utils.file_manager import ensure_folder

DATA_DIR = "data/historical"

def get_prev_close(symbol: str) -> float:
    """
    Get previous close for symbol from stored historical data.
    Auto-adjusts for weekends/holidays.
    """
    ensure_folder(DATA_DIR)
    file_path = os.path.join(DATA_DIR, f"{symbol}.csv")

    if not os.path.exists(file_path):
        return 0.0  # fallback

    df = pd.read_csv(file_path, parse_dates=["date"])
    df.sort_values("date", inplace=True)

    today = datetime.today().date()
    prev_day = today - timedelta(days=1)

    # Adjust for weekends/holidays
    while prev_day not in df["date"].dt.date.values:
        prev_day -= timedelta(days=1)

    prev_close = df.loc[df["date"].dt.date == prev_day, "close"].values
    return float(prev_close[0]) if len(prev_close) else 0.0
