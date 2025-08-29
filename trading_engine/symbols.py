# gm/trading_engine/symbols.py
import os
import zipfile
import pandas as pd
from typing import List
from .api_client import APIClient
from utils.file_manager import ensure_folder, download_master_zip

MASTER_DIR = "data/symbols"
ensure_folder(MASTER_DIR)
MASTER_ALL_ZIP = os.path.join(MASTER_DIR, "allmaster.zip")
MASTER_CSV = os.path.join(MASTER_DIR, "allmaster.csv")

def save_master_zip(api_client: APIClient, url: str):
    dest_folder = MASTER_DIR
    download_master_zip(url, dest_folder)
    # attempt to find csv
    for f in os.listdir(dest_folder):
        if f.lower().endswith(".csv"):
            src = os.path.join(dest_folder, f)
            dst = MASTER_CSV
            try:
                os.replace(src, dst)
            except Exception:
                try:
                    os.rename(src, dst)
                except Exception:
                    pass
            break
    return MASTER_CSV

def load_master_symbols() -> pd.DataFrame:
    if os.path.exists(MASTER_CSV):
        return pd.read_csv(MASTER_CSV)
    return pd.DataFrame()

def get_all_symbols_list() -> List[str]:
    df = load_master_symbols()
    if df.empty:
        return ["RELIANCE","TCS","INFY","HDFCBANK","LT"]
    if "SYMBOL" in df.columns:
        return df["SYMBOL"].astype(str).tolist()
    if "tradingsymbol" in df.columns:
        return df["tradingsymbol"].astype(str).tolist()
    return df.iloc[:,0].astype(str).tolist()
