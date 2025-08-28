# trading_engine/historical.py
from __future__ import annotations
import logging
from datetime import datetime, timedelta
import pandas as pd
import os
from typing import Optional

from utils.file_manager import path_hist_day_nse, read_csv_safe

log = logging.getLogger("trading_engine.historical")
log.setLevel(logging.INFO)

def _last_trading_close_before(token: str, before_date: datetime) -> Optional[float]:
    """
    Return the close price for the last available trading day strictly BEFORE `before_date`.
    If no file or no rows, returns None.
    """
    path = path_hist_day_nse(token)
    df = read_csv_safe(path)
    if df is None or df.empty:
        return None
    # Ensure datetime column
    if "datetime" not in df.columns:
        # try first col as datetime
        df.columns = ["datetime"] + df.columns.tolist()[1:]
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"])
    df = df.sort_values("datetime")
    # keep only dates strictly before the given date (we treat before_date date part)
    cutoff = pd.to_datetime(before_date).normalize()
    df_before = df[df["datetime"] < cutoff]
    if df_before.empty:
        return None
    last_row = df_before.iloc[-1]
    # handle daily format: close column name 'close'
    if "close" in last_row.index:
        return float(last_row["close"])
    # fallback if only 1-column
    vals = last_row.values
    for v in reversed(vals):
        try:
            return float(v)
        except Exception:
            continue
    return None

def get_previous_trading_close(token: str, ref_dt: Optional[datetime] = None) -> Optional[float]:
    """
    Public helper: returns previous trading day's close for token (NSE).
    - ref_dt: reference datetime (defaults to now). We return close for last trading day < ref_dt.date()
    - Uses local historical CSV; does NOT call network.
    """
    if ref_dt is None:
        ref_dt = datetime.now()
    try:
        return _last_trading_close_before(token, ref_dt)
    except Exception as e:
        log.exception("get_previous_trading_close failed for %s: %s", token, e)
        return None
