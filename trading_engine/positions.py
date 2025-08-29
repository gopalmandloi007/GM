# trading_engine/positions.py
# simple wrapper if you need direct access (optional)
from .portfolio import PortfolioManager
from .api_client import APIClient
def get_positions_with_client(api_client: APIClient):
    pm = PortfolioManager(api_client=api_client)
    return pm.fetch_positions_table()
