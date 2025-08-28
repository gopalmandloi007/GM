# trading_engine/symbols.py
from __future__ import annotations
import logging
import zipfile
import io
from typing import Optional, Tuple, List
import requests
import pandas as pd

from utils.file_manager import (
    path_symbols_nse_cash,
    path_symbols_nse_fno,
    to_csv_atomic,
    read_csv_safe,
)

log = logging.getLogger(__name__)

# Official master ZIPs (we'll fetch NSE only, as requested)
NSE_CASH_ZIP = "https://app.definedgesecurities.com/public/nsecash.zip"
NSE_FNO_ZIP  = "https://app.definedgesecurities.com/public/nsefno.zip"

# CSV columns as per documentation
EXPECTED_COLS = [
    "SEGMENT","TOKEN","SYMBOL","TRADINGSYM","INSTRUMENT TYPE","EXPIRY",
    "TICKSIZE","LOTSIZE","OPTIONTYPE","STRIKE","PRICEPREC","MULTIPLIER",
    "ISIN","PRICEMULT","COMPANY"
]

def _download_zip(url: str) -> bytes:
    log.info("Downloading master zip: %s", url)
    r = requests.get(url, timeout=45)
    r.raise_for_status()
    return r.content

def _extract_first_csv(zip_bytes: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        # take the first CSV in the archive
        candidates = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if not candidates:
            raise RuntimeError("No CSV found inside the ZIP.")
        with z.open(candidates[0]) as f:
            df = pd.read_csv(f)
    return df

def _normalize_master(df: pd.DataFrame) -> pd.DataFrame:
    # Ensure expected columns exist (broker sometimes changes casing/order)
    # We'll gently align col names without breaking if extra cols exist.
    col_map = {c.lower(): c for c in df.columns}
    # Standardize to upper-case names we expect
    def get(col: str) -> Optional[str]:
        for c in df.columns:
            if c.strip().lower() == col.strip().lower():
                return c
        return None

    renamed = {}
    for col in EXPECTED_COLS:
        actual = get(col)
        if actual and actual != col:
            renamed[actual] = col

    if renamed:
        df = df.rename(columns=renamed)

    # Basic type coercion
    if "TOKEN" in df.columns:
        df["TOKEN"] = df["TOKEN"].astype(str)

    if "SEGMENT" in df.columns:
        df["SEGMENT"] = df["SEGMENT"].astype(str)

    return df

def update_master_symbols(nse_cash: bool = True, nse_fno: bool = False) -> dict:
    """
    Downloads NSE master files (cash and/or FNO). Saves to data/symbols/*.csv
    Returns dict with summary info.
    """
    out = {}
    if nse_cash:
        z = _download_zip(NSE_CASH_ZIP)
        df = _extract_first_csv(z)
        df = _normalize_master(df)
        # Filter SEGMENT == NSE (should already be)
        if "SEGMENT" in df.columns:
            df = df[df["SEGMENT"].str.upper() == "NSE"].copy()
        to_csv_atomic(df, path_symbols_nse_cash())
        out["nse_cash_rows"] = len(df)

    if nse_fno:
        z = _download_zip(NSE_FNO_ZIP)
        df = _extract_first_csv(z)
        df = _normalize_master(df)
        # Filter SEGMENT == NFO; we keep it optional
        if "SEGMENT" in df.columns:
            df = df[df["SEGMENT"].str.upper().isin(["NFO"])].copy()
        to_csv_atomic(df, path_symbols_nse_fno())
        out["nse_fno_rows"] = len(df)

    return out

def load_nse_cash() -> Optional[pd.DataFrame]:
    return read_csv_safe(path_symbols_nse_cash())

def load_nse_fno() -> Optional[pd.DataFrame]:
    return read_csv_safe(path_symbols_nse_fno())

def symbol_lookup(query: str, limit: int = 20) -> pd.DataFrame:
    """
    Simple autocomplete from NSE cash master.
    Returns TOKEN + TRADINGSYM + SYMBOL + COMPANY for UI dropdowns.
    """
    df = load_nse_cash()
    if df is None or df.empty:
        return pd.DataFrame(columns=["TOKEN","TRADINGSYM","SYMBOL","COMPANY"])
    q = query.strip().lower()
    # match in TRADINGSYM / SYMBOL / COMPANY
    cols = [c for c in ["TRADINGSYM","SYMBOL","COMPANY"] if c in df.columns]
    mask = False
    for c in cols:
        mask = (mask | df[c].astype(str).str.lower().str.contains(q))
    out = df.loc[mask, [c for c in ["TOKEN","TRADINGSYM","SYMBOL","COMPANY"] if c in df.columns]].head(limit).copy()
    return out.reset_index(drop=True)
