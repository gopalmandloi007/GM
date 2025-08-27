# trading_engine/marketdata.py
import os
import io
import zipfile
import csv
import logging
import requests
from .utils import get_sqlite_conn, now_ts

logger = logging.getLogger("trading_engine.marketdata")
logger.setLevel(logging.INFO)

MASTER_URLS = {
    "nsecash": "https://app.definedgesecurities.com/public/nsecash.zip",
    "nsefno": "https://app.definedgesecurities.com/public/nsefno.zip",
    "all": "https://app.definedgesecurities.com/public/allmaster.zip"
}

class MarketData:
    def __init__(self):
        self.conn = get_sqlite_conn()
        self._init_db()

    def _init_db(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS master_symbols (
            segment TEXT,
            token INTEGER PRIMARY KEY,
            symbol TEXT,
            tradingsym TEXT,
            inst TEXT,
            expiry TEXT,
            ticksize REAL,
            lotsize INTEGER,
            optiontype TEXT,
            strike REAL,
            priceprec INTEGER,
            multiplier INTEGER,
            isin TEXT,
            pricemult REAL,
            company TEXT
        )
        """)
        self.conn.commit()

    def download_and_parse_master(self, which="all"):
        url = MASTER_URLS.get(which, MASTER_URLS["all"])
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        for name in z.namelist():
            if name.lower().endswith(".csv"):
                with z.open(name) as f:
                    reader = csv.reader(io.TextIOWrapper(f))
                    rows = []
                    cur = self.conn.cursor()
                    for row in reader:
                        # Expecting columns in the documented order; guard if row length mismatch
                        try:
                            segment, token, symbol, tradingsym, inst, expiry, ticksize, lotsize, optiontype, strike, priceprec, multiplier, isin, pricemult, company = row[:15]
                        except Exception:
                            continue
                        cur.execute("""
                        INSERT OR REPLACE INTO master_symbols (segment, token, symbol, tradingsym, inst, expiry, ticksize, lotsize, optiontype, strike, priceprec, multiplier, isin, pricemult, company)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (segment, int(token), symbol, tradingsym, inst, expiry, float(ticksize or 0), int(lotsize or 0), optiontype, float(strike or 0), int(priceprec or 0), int(multiplier or 1), isin, float(pricemult or 0), company))
                    self.conn.commit()
        logger.info("Master download & parse complete")
