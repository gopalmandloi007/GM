# trading_engine/portfolio.py

from trading_engine.marketdata import get_ltp
from trading_engine.historical import get_previous_close
from trading_engine.api_client import api_client

def get_holdings_with_pnl():
    holdings = api_client.get_holdings()
    portfolio = []
    total_invested = 0
    total_current = 0
    total_today_pnl = 0
    total_overall_pnl = 0

    for h in holdings:
        symbol = h["symbol"]
        qty = h["quantity"]
        avg_price = h["avg_price"]

        ltp = get_ltp(symbol)
        prev_close = get_previous_close(symbol)

        invested = qty * avg_price
        current_value = qty * ltp
        overall_pnl = current_value - invested
        today_pnl = (ltp - prev_close) * qty if prev_close else 0

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
