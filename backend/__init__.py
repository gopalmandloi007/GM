# gm/trading_engine/__init__.py

from .api_client import APIClient
from .session import SessionManager, SessionError
from .orders import OrderManager
from .websocket import WebSocketManager
from .marketdata import MarketDataService, get_ltp
from .positions import get_positions_with_pnl
from .portfolio import get_holdings_with_pnl

# default global client (optional convenience)
_default_client = None

def set_default_client(client: APIClient):
    global _default_client
    _default_client = client

def get_default_client() -> APIClient:
    return _default_client
