# gm/trading_engine/portfolio.py
from typing import Tuple, List, Dict, Any, Optional
from .marketdata import get_ltp, MarketDataService
from .historical import get_previous_trading_close
from .api_client import APIClient

def get_holdings_with_pnl(api_client: APIClient, market_service: Optional[MarketDataService] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    raw = api_client.get_holdings()
    if isinstance(raw, dict) and "holdings" in raw:
        holdings = raw.get("holdings") or []
    elif isinstance(raw, list):
        holdings = raw
    else:
        holdings = raw.get("data") if isinstance(raw, dict) and raw.get("data") else []

    portfolio = []
    total_invested = 0.0
    total_current = 0.0
    total_today_pnl = 0.0
    total_overall_pnl = 0.0

    for h in holdings:
        symbol = h.get("tradingsymbol") or h.get("symbol") or h.get("scrip") or h.get("token")
        qty = float(h.get("quantity") or h.get("qty") or 0)
        avg_price = float(h.get("avg_price") or h.get("avgPrice") or h.get("average_price") or 0)

        if market_service:
            md = market_service.get_ltp_prevclose(token=symbol)
            ltp = md.get("lp")
            prev_close = md.get("prev_close")
        else:
            ltp = get_ltp(symbol, api_client=api_client)
            prev_close = get_previous_trading_close(symbol)

        invested = qty * avg_price
        current_value = qty * (ltp or 0)
        overall_pnl = current_value - invested
        today_pnl = ((ltp or 0) - (prev_close or 0)) * qty if prev_close is not None else 0

        portfolio.append({
            "symbol": symbol,
            "qty": qty,
            "avg_price": avg_price,
            "ltp": ltp,
            "prev_close": prev_close,
            "invested": invested,
            "current_value": current_value,
            "overall_pnl": overall_pnl,
            "today_pnl": today_pnl
        })

        total_invested += invested
        total_current += current_value
        total_today_pnl += today_pnl
        total_overall_pnl += overall_pnl

    summary = {
        "total_invested": total_invested,
        "total_current": total_current,
        "total_today_pnl": total_today_pnl,
        "total_overall_pnl": total_overall_pnl
    }

    return portfolio, summary
