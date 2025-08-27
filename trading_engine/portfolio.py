# trading_engine/portfolio.py
import logging
from .api_client import APIClient
from .session import SessionManager
from .websocket import WSManager

logger = logging.getLogger("trading_engine.portfolio")
logger.setLevel(logging.INFO)

class PortfolioManager:
    def __init__(self, api_client: APIClient = None, ws: WSManager = None):
        self.session = SessionManager.get()
        self.api = api_client or APIClient(self.session)
        self.ws = ws or WSManager(self.session)

    def get_holdings(self):
        return self.api.get_holdings()

    def get_positions(self):
        return self.api.get_positions()

    def get_live_holdings_with_pnl(self):
        """
        Return holdings with attached LTP and computed P&L (uses ws.get_ltp).
        holdings API expected to return structure per Definedge docs.
        """
        h = self.get_holdings()
        holdings = h if isinstance(h, dict) else {}
        out = []
        # support response where holdings might be in holdings['holdings'] or similar
        records = holdings.get("holdings") if isinstance(holdings, dict) and "holdings" in holdings else holdings
        if not records:
            return {"holdings": [], "raw": h}
        for rec in records:
            try:
                exch = rec.get("exchange") or rec.get("exch") or "NSE"
                token = rec.get("token") or rec.get("tokenid") or rec.get("tradingsymbol")
                # token may be string or int
                ltp_info = self.ws.get_ltp(exch, token)
                lp = ltp_info.get("lp") if ltp_info else None
                avg_buy = float(rec.get("avg_price") or rec.get("average_price") or rec.get("buy_price") or 0)
                qty = float(rec.get("quantity") or rec.get("qty") or rec.get("netqty") or 0)
                unreal_pnl = None
                if lp is not None:
                    unreal_pnl = (float(lp) - avg_buy) * qty
                out.append({
                    "tradingsymbol": rec.get("tradingsymbol") or rec.get("symbol"),
                    "exchange": exch,
                    "token": token,
                    "qty": qty,
                    "avg_buy": avg_buy,
                    "ltp": lp,
                    "unreal_pnl": unreal_pnl,
                    "raw": rec
                })
            except Exception as e:
                logger.debug("Holdings parse error: %s", e)
        return {"holdings": out}
