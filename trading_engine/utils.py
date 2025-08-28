# trading_engine/utils.py
import os
from datetime import datetime
import logging

logger = logging.getLogger("trading_engine.utils")
logger.setLevel(logging.INFO)

DATA_DIR = os.path.join(os.getcwd(), "data")
FOLDERS = ["symbols", "historical", "trades", "orders", "portfolio", "logs"]

def setup_data_directories():
    os.makedirs(DATA_DIR, exist_ok=True)
    for f in FOLDERS:
        path = os.path.join(DATA_DIR, f)
        os.makedirs(path, exist_ok=True)
    logger.info("Data directories ensured at %s", DATA_DIR)
    return DATA_DIR

def get_file_path(category: str, filename: str = None, symbol: str = None):
    """Return a path for saving files. Auto-creates subfolders for historical symbol folders."""
    today = datetime.now().strftime("%Y-%m-%d")
    base = os.path.join(DATA_DIR, category)
    if category == "historical" and symbol:
        folder = os.path.join(base, symbol.upper())
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, filename or f"{symbol}_{today}.csv")
    return os.path.join(base, filename or f"{category}_{today}.csv")
