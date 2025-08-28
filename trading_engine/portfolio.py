# trading_engine/portfolio.py
from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
import pandas as pd

from .api_client import APIClient
from .marketdata import MarketDataService

logger = logging.getLogger("trading_engine.portfolio")
logger.setLevel(logging.INFO)

DEFAULT_CAPITAL = 1_400_000

class PortfolioManager:
    def __init__(self, api_client: APIClient, marketdata: Optional[MarketDataService] = None, capital: float = DEFAULT_CAPITAL):
        self.client = api_client
        self.marketdata = marketdata or MarketDataService(api_client=api_client)
        self.capital = capital

    def _normalize_holdings(self, resp: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = []
        if not resp:
            return rows
        data = resp.get("data") or resp.get("holdings") or []
        for item in data:
            qty = float(item.get("dp_qty") or item.get("holding_used") or 0)
            avg = float(item.get("avg_buy_price") or item.get("day_averageprice") or 0)
            ts_list = item.get("tradingsymbol") or []
            if ts_list and isinstance(ts_list, (list, tuple)):
                tinfo = ts_list[0]
                token = str(tinfo.get("token") or "")
                exchange = tinfo.get("exchange") or "NSE"
                symbol = tinfo.get("tradingsymbol") or tinfo.get("SYMBOL") or ""
            else:
                token = str(item.get("token",""))
                exchange = item.get("exchange","NSE")
                symbol = item.get("symbol") or item.get("tradingsymbol") or ""
            rows.append({
                "symbol": symbol,
                "token": token,
                "exchange": exchange,
                "qty": qty,
                "avg_buy_price": avg,
                "raw": item
            })
        return rows

    def _normalize_positions(self, resp: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = []
        if not resp:
            return rows
        data = resp.get("positions") or resp.get("data") or []
        for p in data:
            token = str(p.get("token") or "")
            exchange = p.get("exchange") or "NSE"
            symbol = p.get("tradingsymbol") or ""
            net_qty = float(p.get("net_quantity") or p.get("net_qty") or 0)
            avg = float(p.get("net_averageprice") or p.get("avg_price") or 0)
            last_price = p.get("lastPrice") or p.get("last_price") or None
            rows.append({
                "symbol": symbol,
                "token": token,
                "exchange": exchange,
                "net_qty": net_qty,
                "avg_price": avg,
                "last_price": last_price,
                "raw": p
            })
        return rows

    def fetch_holdings_table(self) -> pd.DataFrame:
        try:
            resp = self.client.get_holdings()
        except Exception as e:
            logger.exception("fetch_holdings_table: API error %s", e)
            return pd.DataFrame()

        rows = self._normalize_holdings(resp)
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        # numeric conversions
        df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0)
        df["avg_buy_price"] = pd.to_numeric(df["avg_buy_price"], errors="coerce").fillna(0)

        # attach market data (LTP + prev_close)
        ltp_list, prev_list, src_list = [], [], []
        for _, r in df.iterrows():
            token = str(r["token"])
            exch = r.get("exchange","NSE")
            md = self.marketdata.get_ltp_prevclose(token, exch)
            ltp_list.append(md.get("lp"))
            prev_list.append(md.get("prev_close"))
            src_list.append(md.get("source"))
        df["ltp"] = ltp_list
        df["prev_close"] = prev_list
        df["md_source"] = src_list

        # compute values
        df["invested"] = df["avg_buy_price"] * df["qty"]
        # current value uses ltp if present else prev_close else 0
        df["current_value"] = df.apply(lambda r: (r["ltp"] if r["ltp"] not in (None,0) else (r["prev_close"] if r["prev_close"] not in (None,0) else 0)) * r["qty"], axis=1)
        # overall unrealized = (ltp - avg) * qty  (if ltp missing, fall back to prev_close for estimate)
        df["overall_unrealized"] = df.apply(lambda r: ((r["ltp"] if r["ltp"] not in (None,0) else (r["prev_close"] or 0)) - r["avg_buy_price"]) * r["qty"], axis=1)
        # today pnl = (ltp - prev_close) * qty (if prev_close missing -> 0)
        df["today_pnl"] = df.apply(lambda r: ((r["ltp"] or r["prev_close"] or 0) - (r["prev_close"] or 0)) * r["qty"], axis=1)

        # capital allocation percent based on invested
        total_invested = df["invested"].sum() if not df["invested"].empty else 1.0
        df["capital_allocation_pct"] = df["invested"] / max(total_invested, 1e-9) * 100.0

        # nice display order
        cols = ["symbol","token","exchange","qty","avg_buy_price","ltp","prev_close","invested","current_value","today_pnl","overall_unrealized","capital_allocation_pct","md_source"]
        cols = [c for c in cols if c in df.columns]
        return df[cols].sort_values("capital_allocation_pct", ascending=False).reset_index(drop=True)

    def fetch_positions_table(self) -> pd.DataFrame:
        try:
            resp = self.client.get_positions()
        except Exception as e:
            logger.exception("fetch_positions_table: API error %s", e)
            return pd.DataFrame()
        rows = self._normalize_positions(resp)
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["net_qty"] = pd.to_numeric(df["net_qty"], errors="coerce").fillna(0)
        df["avg_price"] = pd.to_numeric(df["avg_price"], errors="coerce").fillna(0)

        ltp_list, prev_list, src_list = [], [], []
        for _, r in df.iterrows():
            token = str(r["token"])
            exch = r.get("exchange","NSE")
            md = self.marketdata.get_ltp_prevclose(token, exch)
            ltp_list.append(md.get("lp") or r.get("last_price"))
            prev_list.append(md.get("prev_close"))
            src_list.append(md.get("source"))
        df["ltp"] = ltp_list
        df["prev_close"] = prev_list
        df["md_source"] = src_list

        df["invested"] = df["avg_price"] * df["net_qty"]
        df["current_value"] = df.apply(lambda r: (r["ltp"] or r["prev_close"] or 0) * r["net_qty"], axis=1)
        df["overall_unrealized"] = df.apply(lambda r: ((r["ltp"] or r["prev_close"] or 0) - r["avg_price"]) * r["net_qty"], axis=1)
        df["today_pnl"] = df.apply(lambda r: ((r["ltp"] or r["prev_close"] or 0) - (r["prev_close"] or 0)) * r["net_qty"], axis=1)

        total_abs = df["invested"].abs().sum() if not df.empty else 1.0
        df["capital_allocation_pct"] = df["invested"].abs() / max(total_abs, 1e-9) * 100.0

        cols = ["symbol","token","exchange","net_qty","avg_price","ltp","prev_close","invested","current_value","today_pnl","overall_unrealized","capital_allocation_pct","md_source"]
        cols = [c for c in cols if c in df.columns]
        return df[cols].sort_values("capital_allocation_pct", ascending=False).reset_index(drop=True)

    def portfolio_summary(self) -> Dict[str, float]:
        hold = self.fetch_holdings_table()
        pos = self.fetch_positions_table()
        total_invested = float(hold["invested"].sum()) if not hold.empty else 0.0
        total_current = float(hold["current_value"].sum()) if not hold.empty else 0.0
        today_pnl = float(hold["today_pnl"].sum()) + float(pos["today_pnl"].sum()) if (not hold.empty or not pos.empty) else 0.0
        overall_unreal = float(hold["overall_unrealized"].sum()) + float(pos["overall_unrealized"].sum()) if (not hold.empty or not pos.empty) else 0.0
        realized = float(pos["realized_pnl"].sum()) if "realized_pnl" in pos.columns else 0.0
        return {
            "total_invested": total_invested,
            "total_current_value": total_current,
            "todays_pnl": today_pnl,
            "overall_unrealized": overall_unreal,
            "total_realized": realized,
            "capital": self.capital
        }
