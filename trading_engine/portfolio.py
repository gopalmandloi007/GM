# trading_engine/portfolio.py
import logging
from typing import Dict, Any, Optional
import pandas as pd
from .api_client import APIClient
from .marketdata import MarketDataService

logger = logging.getLogger("trading_engine.portfolio")
logger.setLevel(logging.INFO)

DEFAULT_CAPITAL = 1_400_000

class PortfolioManager:
    def __init__(self, api_client: APIClient, marketdata: Optional[MarketDataService]=None, capital: float = DEFAULT_CAPITAL):
        self.client = api_client
        self.marketdata = marketdata or MarketDataService(api_client=api_client)
        self.capital = capital

    def fetch_holdings_table(self) -> pd.DataFrame:
        try:
            resp = self.client.get_holdings()
        except Exception as e:
            logger.exception("Failed to fetch holdings: %s", e)
            return pd.DataFrame()
        data = resp.get("data") or resp.get("holdings") or []
        rows = []
        for item in data:
            qty = float(item.get("dp_qty") or item.get("holding_used") or 0)
            avg = float(item.get("avg_buy_price") or item.get("day_averageprice") or 0)
            ts_list = item.get("tradingsymbol") or []
            if ts_list:
                tinfo = ts_list[0]
                token = str(tinfo.get("token") or "")
                exch = tinfo.get("exchange") or "NSE"
                symbol = tinfo.get("tradingsymbol") or ""
            else:
                token = str(item.get("token",""))
                exch = item.get("exchange","NSE")
                symbol = item.get("symbol") or item.get("tradingsymbol") or ""
            rows.append({"symbol": symbol, "token": token, "exchange": exch, "qty": qty, "avg_buy_price": avg})
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        # attach md
        ltp_list, prev_list, src_list = [], [], []
        for _, r in df.iterrows():
            md = self.marketdata.get_ltp_prevclose(r["token"], r["exchange"])
            ltp_list.append(md.get("lp"))
            prev_list.append(md.get("prev_close"))
            src_list.append(md.get("source"))
        df["ltp"] = ltp_list
        df["prev_close"] = prev_list
        df["md_source"] = src_list
        df["invested"] = df["avg_buy_price"] * df["qty"]
        df["current_value"] = df.apply(lambda r: ((r["ltp"] if r["ltp"] not in (None,0) else (r["prev_close"] or 0)) * r["qty"]), axis=1)
        df["overall_unrealized"] = df.apply(lambda r: ((r["ltp"] if r["ltp"] not in (None,0) else (r["prev_close"] or 0)) - r["avg_buy_price"]) * r["qty"], axis=1)
        df["today_pnl"] = df.apply(lambda r: ((r["ltp"] if r["ltp"] is not None else (r["prev_close"] or 0)) - (r["prev_close"] or 0)) * r["qty"], axis=1)
        total_invested = df["invested"].sum()
        df["capital_allocation_pct"] = df["invested"] / max(total_invested, 1e-9) * 100.0
        cols = ["symbol","token","exchange","qty","avg_buy_price","ltp","prev_close","invested","current_value","today_pnl","overall_unrealized","capital_allocation_pct","md_source"]
        cols = [c for c in cols if c in df.columns]
        return df[cols].sort_values("capital_allocation_pct", ascending=False).reset_index(drop=True)

    def fetch_positions_table(self) -> pd.DataFrame:
        try:
            resp = self.client.get_positions()
        except Exception as e:
            logger.exception("Failed to fetch positions: %s", e)
            return pd.DataFrame()
        data = resp.get("positions") or resp.get("data") or []
        rows = []
        for item in data:
            token = str(item.get("token") or "")
            exch = item.get("exchange") or "NSE"
            symbol = item.get("tradingsymbol") or ""
            net_qty = float(item.get("net_quantity") or item.get("net_qty") or 0)
            avg = float(item.get("net_averageprice") or item.get("avg_price") or 0)
            rows.append({"symbol": symbol, "token": token, "exchange": exch, "net_qty": net_qty, "avg_price": avg, "raw": item})
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        ltp_list, prev_list, src_list = [], [], []
        for _, r in df.iterrows():
            md = self.marketdata.get_ltp_prevclose(r["token"], r["exchange"])
            ltp_list.append(md.get("lp"))
            prev_list.append(md.get("prev_close"))
            src_list.append(md.get("source"))
        df["ltp"] = ltp_list
        df["prev_close"] = prev_list
        df["md_source"] = src_list
        df["invested"] = df["avg_price"] * df["net_qty"]
        df["current_value"] = df.apply(lambda r: ((r["ltp"] if r["ltp"] not in (None,0) else (r["prev_close"] or 0)) * r["net_qty"]), axis=1)
        df["overall_unrealized"] = df.apply(lambda r: ((r["ltp"] if r["ltp"] not in (None,0) else (r["prev_close"] or 0)) - r["avg_price"]) * r["net_qty"], axis=1)
        df["today_pnl"] = df.apply(lambda r: ((r["ltp"] if r["ltp"] is not None else (r["prev_close"] or 0)) - (r["prev_close"] or 0)) * r["net_qty"], axis=1)
        total_abs = df["invested"].abs().sum() if not df.empty else 1.0
        df["capital_allocation_pct"] = df["invested"].abs() / max(total_abs, 1e-9) * 100.0
        cols = ["symbol","token","exchange","net_qty","avg_price","ltp","prev_close","invested","current_value","today_pnl","overall_unrealized","capital_allocation_pct","md_source"]
        cols = [c for c in cols if c in df.columns]
        return df[cols].sort_values("capital_allocation_pct", ascending=False).reset_index(drop=True)

    def portfolio_summary(self) -> Dict[str,float]:
        h = self.fetch_holdings_table()
        p = self.fetch_positions_table()
        invested = float(h["invested"].sum()) if not h.empty else 0.0
        current = float(h["current_value"].sum()) if not h.empty else 0.0
        today = float(h["today_pnl"].sum()) + float(p["today_pnl"].sum()) if (not h.empty or not p.empty) else 0.0
        overall = float(h["overall_unrealized"].sum()) + float(p["overall_unrealized"].sum()) if (not h.empty or not p.empty) else 0.0
        realized = float(p["raw"].apply(lambda r: r.get("realized_pnl",0) if isinstance(r, dict) else 0).sum()) if not p.empty else 0.0
        return {"total_invested": invested, "total_current_value": current, "todays_pnl": today, "overall_unrealized": overall, "total_realized": realized, "capital": self.capital}
