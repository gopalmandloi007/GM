# trading_engine/historical.py
import logging
from .api_client import APIClient
from .utils import get_file_path, setup_data_directories
setup_data_directories()
logger = logging.getLogger("trading_engine.historical")
logger.setLevel(logging.INFO)

def save_historical_text(segment: str, token: str, timeframe: str, from_dt: str, to_dt: str, api_client: APIClient):
    """
    Fetch historical CSV text and save to file under data/historical/<SYMBOL>/<file>.csv
    from_dt/to_dt must be ddMMyyyyHHmm strings as per API.
    """
    txt = api_client.get_historical(segment, token, timeframe, from_dt, to_dt)
    filename = f"{token}_{from_dt}_{to_dt}.csv"
    fpath = get_file_path("historical", filename=filename, symbol=token)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(txt)
    logger.info("Saved historical to %s", fpath)
    return fpath
