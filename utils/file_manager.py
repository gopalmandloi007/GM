# gm/utils/file_manager.py
import os
import json
import pandas as pd
import requests
import zipfile
import io
from datetime import datetime
from typing import Optional, Any

def ensure_folder(path: str):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def ensure_dir(path: str):
    ensure_folder(path)

def read_json_safe(path: str) -> Optional[Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def write_json_safe(path: str, data: Any):
    ensure_folder(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def save_json_log(folder: str, name: str, data: Any, append: bool = True):
    ensure_folder(folder)
    path = os.path.join(folder, f"{name}.json")

    existing = []
    if append and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    entry = {"timestamp": datetime.now().isoformat(), "data": data}
    existing.append(entry)
    write_json_safe(path, existing)

def read_csv_safe(path: str) -> Optional[pd.DataFrame]:
    try:
        if not os.path.exists(path):
            return None
        return pd.read_csv(path)
    except Exception:
        return None

def to_csv_atomic(df: pd.DataFrame, path: str, index=False):
    ensure_folder(os.path.dirname(path) or ".")
    tmp = path + ".tmp"
    df.to_csv(tmp, index=index)
    os.replace(tmp, path)

def save_dataframe(path: str, df: pd.DataFrame, mode: str = "w"):
    ensure_folder(os.path.dirname(path) or ".")
    if mode == "a" and os.path.exists(path):
        df.to_csv(path, mode="a", header=False, index=False)
    else:
        to_csv_atomic(df, path, index=False)

def download_master_zip(url: str, extract_to: str) -> str:
    """
    Download & extract a master ZIP to a folder. Returns extract_to.
    """
    ensure_folder(extract_to)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        z.extractall(extract_to)
    return extract_to

def fetch_historical_data(segment: str, token: str, timeframe: str, from_date: str, to_date: str) -> Optional[pd.DataFrame]:
    url = f"https://data.definedgesecurities.com/sds/history/{segment}/{token}/{timeframe}/{from_date}/{to_date}"
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        # Could be CSV or JSON; try CSV then JSON
        txt = r.text
        from io import StringIO
        try:
            df = pd.read_csv(StringIO(txt))
            return df
        except Exception:
            try:
                j = r.json()
                return pd.DataFrame(j)
            except Exception:
                return None
    except Exception:
        return None

# Convenience logging helpers
def log_order(data: dict, folder: str = "data/logs/orders"):
    save_json_log(folder, "orders", data)

def log_trade(data: dict, folder: str = "data/logs/trades"):
    save_json_log(folder, "trades", data)

def log_position(data: dict, folder: str = "data/logs/positions"):
    save_json_log(folder, "positions", data)

def log_holding(data: dict, folder: str = "data/logs/holdings"):
    save_json_log(folder, "holdings", data)
