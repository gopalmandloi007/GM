# trading_engine/utils.py
import time
import os
import sqlite3
import logging
from typing import Optional

logger = logging.getLogger("trading_engine.utils")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.INFO)

def now_ts() -> int:
    return int(time.time())

def ensure_storage_dir(path: str = "storage"):
    os.makedirs(path, exist_ok=True)
    return path

def get_db_path(path: str = "storage/trading.db") -> str:
    ensure_storage_dir(os.path.dirname(path) or ".")
    return path

def get_sqlite_conn(path: Optional[str] = None) -> sqlite3.Connection:
    db_path = get_db_path(path or "storage/trading.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db_schema(conn: Optional[sqlite3.Connection] = None):
    """
    Create / migrate needed tables:
      - sessions (already created elsewhere)
      - orders
      - ltp_cache
      - historical_meta
    """
    c = conn or get_sqlite_conn()
    cur = c.cursor()
    # sessions table if not exists (safe to create again)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        uid TEXT PRIMARY KEY,
        api_session_key TEXT,
        susertoken TEXT,
        uname TEXT,
        last_acquired INTEGER
    )
    """)
    # orders table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        local_id TEXT,
        status TEXT,
        created_at INTEGER,
        updated_at INTEGER,
        filled_qty INTEGER DEFAULT 0,
        avg_price REAL DEFAULT 0,
        raw_response TEXT
    )
    """)
    # ltp_cache table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ltp_cache (
        exchange TEXT,
        token TEXT,
        lp REAL,
        pc REAL,
        ts INTEGER,
        PRIMARY KEY(exchange, token)
    )
    """)
    # historical_meta
    cur.execute("""
    CREATE TABLE IF NOT EXISTS historical_meta (
        segment TEXT,
        token TEXT,
        timeframe TEXT,
        from_ts TEXT,
        to_ts TEXT,
        PRIMARY KEY (segment, token, timeframe)
    )
    """)
    c.commit()
    logger.info("DB schema initialized")
    return c
