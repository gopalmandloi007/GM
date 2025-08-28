# trading_engine/symbols.py
import os
import csv
import zipfile
import io
import logging
from .utils import setup_data_directories, get_file_path
from .api_client import MASTER_URLS
import requests

logger = logging.getLogger("trading_engine.symbols")
logger.setLevel(logging.INFO)

setup_data_directories()

def download_master(key="ALL") -> str:
    """
    Download master zip and extract CSV into data/symbols/*.csv and return path.
    key can be 'ALL' or 'NSE_CASH' etc.
    """
    url = MASTER_URLS.get(key.upper(), MASTER_URLS["ALL"])
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    out_dir = os.path.join("data", "symbols")
    z.extractall(out_dir)
    logger.info("Master extracted to %s", out_dir)
    # Return first csv path
    for name in z.namelist():
        if name.lower().endswith(".csv"):
            return os.path.join(out_dir, os.path.basename(name))
    return out_dir

def load_symbols_from_csv(csv_path: str) -> list:
    """Returns list of dicts with CSV rows"""
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for r in reader:
            if not r: continue
            rows.append(r)
    return rows

def autocomplete_symbols(substr: str, limit: int = 20) -> list:
    """
    Simple substring search across all csvs in data/symbols.
    Returns list of tuples (symbol, tradingsymbol) ; crude but works for autocomplete.
    """
    out = []
    base = os.path.join("data", "symbols")
    if not os.path.isdir(base):
        return out
    substr = substr.lower()
    for fname in os.listdir(base):
        if not fname.lower().endswith(".csv"):
            continue
        try:
            with open(os.path.join(base, fname), newline='', encoding='utf-8') as f:
                for row in f:
                    try:
                        # Many masters have fields: SEGMENT,TOKEN,SYMBOL,TRADINGSYM,...
                        # We do a safe read
                        if len(row) >= 3:
                            symbol = row[2]
                            tradingsym = row[3] if len(row) > 3 else symbol
                        else:
                            continue
                        if substr in symbol.lower() or substr in tradingsym.lower():
                            out.append((symbol, tradingsym))
                            if len(out) >= limit:
                                return out
                    except Exception:
                        continue
        except Exception:
            continue
    return out
