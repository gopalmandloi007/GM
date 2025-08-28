# utils/file_manager.py
from __future__ import annotations
import os
import io
import logging
from typing import Optional
import pandas as pd

log = logging.getLogger(__name__)

# ---- Base data dirs (you can change if you like) ----
DATA_DIR = os.path.join("data")
SYMBOLS_DIR = os.path.join(DATA_DIR, "symbols")
HIST_DIR = os.path.join(DATA_DIR, "historical")

def ensure_dir(path: str) -> None:
    """Create directory (and parents) if not present."""
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def write_bytes_atomic(dest_path: str, content: bytes) -> None:
    """Atomic write to prevent partial files on crashes."""
    ensure_dir(os.path.dirname(dest_path))
    tmp_path = dest_path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(content)
    os.replace(tmp_path, dest_path)
    log.debug("Wrote file: %s", dest_path)

def write_text_atomic(dest_path: str, text: str) -> None:
    write_bytes_atomic(dest_path, text.encode("utf-8"))

def read_csv_safe(path: str, **kwargs) -> Optional[pd.DataFrame]:
    """Read CSV if exists, else return None."""
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, **kwargs)
        return df
    except Exception as e:
        log.warning("Failed to read csv %s: %s", path, e)
        return None

def to_csv_atomic(df: pd.DataFrame, dest_path: str, **kwargs) -> None:
    """Write DataFrame to CSV atomically."""
    ensure_dir(os.path.dirname(dest_path))
    buf = io.StringIO()
    df.to_csv(buf, index=False, **kwargs)
    write_text_atomic(dest_path, buf.getvalue())

def append_and_dedup_csv(
    dest_path: str,
    new_df: pd.DataFrame,
    key_cols: list[str],
    sort_by: Optional[str] = None,
) -> pd.DataFrame:
    """
    Append to existing CSV and deduplicate by key_cols. Returns final dataframe.
    If file doesn't exist, it will be created.
    """
    old = read_csv_safe(dest_path)
    if old is None or old.empty:
        final = new_df.copy()
    else:
        final = pd.concat([old, new_df], ignore_index=True)

    final.drop_duplicates(subset=key_cols, keep="last", inplace=True)
    if sort_by and sort_by in final.columns:
        final.sort_values(by=sort_by, inplace=True)
    final.reset_index(drop=True, inplace=True)
    to_csv_atomic(final, dest_path)
    return final

# Path helpers (NSE only by your preference)
def path_symbols_nse_cash() -> str:
    ensure_dir(SYMBOLS_DIR)
    return os.path.join(SYMBOLS_DIR, "nse_cash.csv")

def path_symbols_nse_fno() -> str:
    ensure_dir(SYMBOLS_DIR)
    return os.path.join(SYMBOLS_DIR, "nse_fno.csv")

def path_hist_day_nse(token: str) -> str:
    """One csv per token for daily timeframe."""
    p = os.path.join(HIST_DIR, "NSE", "day")
    ensure_dir(p)
    return os.path.join(p, f"{token}.csv")
