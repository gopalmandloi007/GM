# trading_engine/historical.py
from __future__ import annotations
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
import requests
import pandas as pd

from utils.file_manager import (
    path_hist_day_nse,
    append_and_dedup_csv,
    read_csv_safe,
)

log = logging.getLogger(__name__)

DATA_BASE = "https://data.definedgesecurities.com/sds/history/{segment}/{token}/{timeframe}/{from_}/{to_}"
SEGMENT = "NSE"  # You asked to keep NSE-only for history

def _fmt_dt_for_api(dt: datetime) -> str:
    # ddMMyyyyHHmm
    return dt.strftime("%d%m%Y%H%M")

def _parse_history_csv(content: str, timeframe: str) -> pd.DataFrame:
    """
    Broker returns CSV without headers.
    For day/minute: DateTime, O,H,L,C,Volume,OI
    We'll add headers and convert dtypes.
    """
    if not content.strip():
        return pd.DataFrame(columns=["datetime","open","high","low","close","volume","oi"])

    # Read without header then assign names
    df = pd.read_csv(pd.compat.StringIO(content), header=None)
    if timeframe in ("day", "minute"):
        df.columns = ["datetime","open","high","low","close","volume","oi"]
        # datetime comes as e.g. 2024-08-27 00:00? (They said no headers; format may be yyyy-mm-dd HH:MM or yyyymmdd)
        # Some feeds give "YYYY-MM-DD HH:MM:SS" or epoch; we handle generically:
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    else:
        # tick format: UTC(seconds), LTP, LTQ, OI
        df.columns = ["utc","ltp","ltq","oi"]
        df["datetime"] = pd.to_datetime(df["utc"], unit="s", utc=True).dt.tz_convert(None)
        df.rename(columns={"ltp":"close"}, inplace=True)  # to be somewhat consistent
    # numeric
    for c in [c for c in ["open","high","low","close"] if c in df.columns]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in [c for c in ["volume","oi","ltq"] if c in df.columns]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype("int64", errors="ignore")

    # Keep only needed columns for day/minute
    if timeframe in ("day","minute"):
        df = df[["datetime","open","high","low","close","volume","oi"]]
    else:
        df = df[["datetime","close","ltq","oi"]]
    df.dropna(subset=["datetime"], inplace=True)
    df.sort_values("datetime", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

def _http_get_history(
    api_session_key: str,
    segment: str,
    token: str,
    timeframe: str,
    from_dt: datetime,
    to_dt: datetime,
    retries: int = 3,
    sleep_sec: float = 0.8,
) -> pd.DataFrame:
    url = DATA_BASE.format(
        segment=segment,
        token=str(token),
        timeframe=timeframe,
        from_=_fmt_dt_for_api(from_dt),
        to_=_fmt_dt_for_api(to_dt),
    )
    headers = {"Authorization": api_session_key}
    last_err = None
    for i in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=45)
            if r.status_code == 204 or (r.text.strip() == ""):
                return pd.DataFrame(columns=["datetime","open","high","low","close","volume","oi"])
            r.raise_for_status()
            return _parse_history_csv(r.text, timeframe)
        except Exception as e:
            last_err = e
            log.warning("History fetch failed (try %d/%d): %s", i + 1, retries, e)
            time.sleep(sleep_sec)
    raise last_err

def _load_existing_last_dt(dest_path: str) -> Optional[pd.Timestamp]:
    old = read_csv_safe(dest_path)
    if old is None or old.empty or "datetime" not in old.columns:
        return None
    try:
        return pd.to_datetime(old["datetime"]).max()
    except Exception:
        return None

def _daterange_chunks(start_dt: datetime, end_dt: datetime, chunk_days: int = 180) -> List[Tuple[datetime, datetime]]:
    """Yield [start,end] chunks to avoid huge responses. 180 days is safe."""
    chunks = []
    cur = start_dt
    while cur <= end_dt:
        nxt = min(cur + timedelta(days=chunk_days), end_dt)
        chunks.append((cur, nxt))
        cur = nxt + timedelta(days=1)
    return chunks

def update_daily_history_nse(
    api_session_key: str,
    token: str,
    lookback_days: int = 548,  # ~1.5 years (365 * 1.5)
) -> pd.DataFrame:
    """
    Incrementally updates daily history CSV for given NSE token.
    - File path: data/historical/NSE/day/{token}.csv
    - No duplication: merges and drops duplicates by 'datetime'
    - If file not present, downloads ~1.5 years.
    """
    dest = path_hist_day_nse(token)
    last_dt = _load_existing_last_dt(dest)
    today = datetime.now()
    # For daily, we'll fetch from last_dt + 1 day; else from today - lookback_days
    if last_dt is not None:
        start_dt = (pd.to_datetime(last_dt) + pd.Timedelta(days=1)).to_pydatetime()
        # if start is after today, nothing to do
        if start_dt.date() > today.date():
            log.info("Up-to-date for token %s", token)
            return read_csv_safe(dest) or pd.DataFrame()
    else:
        start_dt = (today - timedelta(days=lookback_days)).replace(hour=0, minute=0, second=0, microsecond=0)

    # end at today 15:30 (market close) to include the full session
    end_dt = today.replace(hour=15, minute=30, second=0, microsecond=0)

    all_new = []
    for a, b in _daterange_chunks(start_dt, end_dt, chunk_days=180):
        # For daily bars we can use 00:00 to 15:30 to be safe
        a2 = a.replace(hour=0, minute=0)
        b2 = b.replace(hour=15, minute=30)
        df = _http_get_history(
            api_session_key=api_session_key,
            segment=SEGMENT,
            token=token,
            timeframe="day",
            from_dt=a2,
            to_dt=b2,
        )
        if not df.empty:
            all_new.append(df)

    if not all_new:
        # nothing new; just return existing
        return read_csv_safe(dest) or pd.DataFrame(columns=["datetime","open","high","low","close","volume","oi"])

    new_df = pd.concat(all_new, ignore_index=True)
    # Dedup + persist
    final = append_and_dedup_csv(dest, new_df, key_cols=["datetime"], sort_by="datetime")
    return final

def get_last_close_from_file(token: str) -> Optional[float]:
    """Helper for previous close usage in UI when WS is off."""
    path = path_hist_day_nse(token)
    df = read_csv_safe(path)
    if df is None or df.empty:
        return None
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.sort_values("datetime")
    if len(df) < 2:
        # If only one row exists, that close is 'last known'
        return float(df["close"].iloc[-1])
    return float(df["close"].iloc[-1])
