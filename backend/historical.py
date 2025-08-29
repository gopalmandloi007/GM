# gm/trading_engine/historical.py
import os
from datetime import datetime, timedelta
import pandas as pd
from typing import Optional
from utils.file_manager import read_csv_safe, ensure_folder

HIST_DIR = "data/historical/day/NSE"
ensure_folder(HIST_DIR)

def path_hist_day_nse(token: str) -> str:
    return os.path.join(HIST_DIR, f"{token}.csv")

def get_previous_trading_close(token: str, ref_dt: Optional[datetime] = None) -> Optional[float]:
    """
    Return last available trading day's close strictly before ref_dt (or today if not passed).
    Looks for CSV at data/historical/day/NSE/{token}.csv
    CSV expected to have a date/datetime column and close column (close).
    """
    if ref_dt is None:
        ref_dt = datetime.now()
    path = path_hist_day_nse(token)
    df = read_csv_safe(path)
    if df is None or df.empty:
        return None
    # try common datetime column names
    dt_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower()]
    if not dt_cols:
        # assume first column is date-like
        df.columns = ["datetime"] + df.columns.tolist()[1:]
        dt_cols = ["datetime"]
    dtc = dt_cols[0]
    df[dtc] = pd.to_datetime(df[dtc], errors="coerce")
    df = df.dropna(subset=[dtc])
    df = df.sort_values(dtc)
    cutoff = pd.to_datetime(ref_dt).normalize()
    df_before = df[df[dtc] < cutoff]
    if df_before.empty:
        return None
    last = df_before.iloc[-1]
    if "close" in last.index:
        try:
            return float(last["close"])
        except Exception:
            return None
    # fallback: try last numeric column
    for v in reversed(last.values):
        try:
            return float(v)
        except Exception:
            continue
    return None
