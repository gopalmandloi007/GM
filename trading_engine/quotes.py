from .api_client import APIClient

def get_ltp(session, exchange, tradingsymbol):
    endpoint = "/quotes/ltp"
    payload = {"exchange": exchange, "tradingsymbol": tradingsymbol}
    return APIClient(session).get(endpoint, params=payload)

def get_ohlc(session, exchange, tradingsymbol):
    endpoint = "/quotes/ohlc"
    payload = {"exchange": exchange, "tradingsymbol": tradingsymbol}
    return APIClient(session).get(endpoint, params=payload)

def get_market_depth(session, exchange, tradingsymbol):
    endpoint = "/quotes/depth"
    payload = {"exchange": exchange, "tradingsymbol": tradingsymbol}
    return APIClient(session).get(endpoint, params=payload)
