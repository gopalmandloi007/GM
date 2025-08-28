# trading_engine/portfolio.py
import logging
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
from .api_client import APIClient
from .marketdata import MarketDataService

logger = logging.getLogger("trading_engine.portfolio")
logger.setLevel(logging.INFO)

DEFAULT_CAPITAL = 1_400_000  # default capital as you specified

class PortfolioManager:
    """
    Build holdings & positions table, attach LTP (via MarketDataService),
    compute Invested, Current Value, Realized/Unrealized P&L, Capital Allocation,
    and compute TSL/Targets.
    """
    def __init__(self, api_client: APIClient, marketdata: Optional[MarketDataService]=None, capital: float = DEFAULT_CAPITAL):
        self.client = api_client
        self.marketdata = marketdata or MarketDataService(api_client=api_client)
        self.capital = capital

    # ---------- P&L / money helpers ----------
    def _parse_holdings_response(self, resp: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Normalize the holdings JSON into a list of dicts with fields we need.
        Expected resp structure:
        { "status": "SUCCESS", "data": [ { ... tradingsymbol: [ {exchange, tradingsymbol, token...} ] } ] }
        """
        rows = []
        if not resp:
            return rows
        data = resp.get("data") or resp.get("holdings") or resp.get("result") or []
        for item in data:
            # prefer dp_qty or holding_used
            qty = float(item.get("dp_qty") or item.get("holding_used") or 0)
            avg = float(item.get("avg_buy_price") or item.get("day_averageprice") or 0)
            sell_amt = float(item.get("sell_amt") or 0)
            # tradingsymbol may be list; take first available mapping
            ts_list = item.get("tradingsymbol") or []
            if ts_list:
                tinfo = ts_list[0]
                exchange = tinfo.get("exchange","NSE")
                token = str(tinfo.get("token"))
                tradingsymbol = tinfo.get("tradingsymbol") or tinfo.get("SYMBOL") or ""
            else:
                exchange = "NSE"
                token = ""
                tradingsymbol = item.get("symbol") or item.get("tradingsymbol") or ""
            rows.append({
                "symbol": tradingsymbol,
                "token": token,
                "exchange": exchange,
                "qty": qty,
                "avg_buy_price": avg,
                "sell_amt": sell_amt,
                "raw": item
            })
        return rows

    def _parse_positions_response(self, resp: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Positions often have different keys; normalize similarly."""
        rows = []
        if not resp:
            return rows
        data = resp.get("positions") or resp.get("data") or []
        for p in data:
            token = str(p.get("token") or "")
            exchange = p.get("exchange") or "NSE"
            tradingsymbol = p.get("tradingsymbol") or ""
            net_qty = float(p.get("net_quantity") or p.get("net_quantity") or 0)
            avg = float(p.get("net_averageprice") or p.get("net_averageprice") or p.get("day_averageprice") or 0)
            unreal = float(p.get("unrealized_pnl") or 0)
            realized = float(p.get("realized_pnl") or 0)
            lastPrice = p.get("lastPrice") or p.get("last_price") or None
            rows.append({
                "symbol": tradingsymbol,
                "token": token,
                "exchange": exchange,
                "net_qty": net_qty,
                "avg_price": avg,
                "unrealized_pnl": unreal,
                "realized_pnl": realized,
                "last_price": lastPrice,
                "raw": p
            })
        return rows

    # ---------- TSL / Targets ----------
    def compute_tsl_and_targets(self, entry_price: float, ltp: Optional[float]) -> Dict[str, Optional[float]]:
        """
        TSL rules:
          - TSL initial: entry * (1 - 0.02) ??? (you said initial stop loss 2% - I'll store that)
          - Further shifting:
              If LTP > entry * 1.06 => TSL = entry (i.e. move to entry)
              If LTP > entry * 1.10 => TSL = entry + 6%
              If LTP > entry * 1.20 => TSL = entry + 10%
          NOTE: You said TSL only increases, never decreases. This function returns suggested tsl targets; persisting and "sticky" behavior must be done outside (DB/session).
        Returns dict with 'initial_sl','tsl','target1'...'target4'
        """
        initial_sl = round(entry_price * (1 - 0.02), 2)
        target1 = round(entry_price * (1 + 0.10), 2)
        target2 = round(entry_price * (1 + 0.20), 2)
        target3 = round(entry_price * (1 + 0.30), 2)
        target4 = round(entry_price * (1 + 0.40), 2)
        tsl = initial_sl
        if ltp is None:
            return {"initial_sl": initial_sl, "tsl": tsl, "target1": target1, "target2": target2, "target3": target3, "target4": target4}
        # rules in percent
        if ltp > entry_price * 1.20:
            tsl = round(entry_price * (1 + 0.10), 2)
        elif ltp > entry_price * 1.10:
            tsl = round(entry_price * (1 + 0.06), 2)
        elif ltp > entry_price * 1.06:
            tsl = round(entry_price, 2)
        # ensure tsl never lower than initial_sl
        if tsl < initial_sl:
            tsl = initial_sl
        return {"initial_sl": initial_sl, "tsl": tsl, "target1": target1, "target2": target2, "target3": target3, "target4": target4}

    # ---------- Public actions ----------
    def fetch_holdings_table(self) -> pd.DataFrame:
        """
        Fetch holdings via API, attach LTP and compute financial columns.
        Returns pandas DataFrame ready to display.
        """
        try:
            resp = self.client.get_holdings()
        except Exception as e:
            logger.exception("Failed to fetch holdings: %s", e)
            return pd.DataFrame()

        rows = self._parse_holdings_response(resp)
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        # Attach LTP
        ltp_list = []
        for idx, r in df.iterrows():
            token = r["token"]
            exchange = r["exchange"]
            md = self.marketdata.get_ltp_for_token(token, exchange)
            ltp = md.get("lp")
            ltp_list.append(ltp)
        df["ltp"] = ltp_list
        # numeric conversions
        df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0)
        df["avg_buy_price"] = pd.to_numeric(df["avg_buy_price"], errors="coerce").fillna(0)
        df["invested"] = df["avg_buy_price"] * df["qty"]
        df["current_value"] = df["ltp"].fillna(0) * df["qty"]
        df["unrealized_pnl"] = df["current_value"] - df["invested"]
        # capital allocation %
        total_invested = df["invested"].sum() if not df["invested"].empty else 0.0
        df["capital_allocation_pct"] = df["invested"] / max(total_invested, 1e-9) * 100.0
        # compute TSL/Targets for each
        tsl_cols = {"initial_sl": [], "tsl": [], "target1": [], "target2": [], "target3": [], "target4": []}
        for _, r in df.iterrows():
            entry = float(r["avg_buy_price"])
            ltp_val = r["ltp"] if pd.notna(r["ltp"]) else None
            tvals = self.compute_tsl_and_targets(entry, ltp_val)
            for k,v in tvals.items():
                tsl_cols[k].append(v)
        for k,v in tsl_cols.items():
            df[k] = v
        # nice columns order
        display_cols = ["symbol","token","exchange","qty","avg_buy_price","ltp","invested","current_value","unrealized_pnl","capital_allocation_pct","initial_sl","tsl","target1","target2","target3","target4"]
        # ensure exist
        display_cols = [c for c in display_cols if c in df.columns]
        return df[display_cols].sort_values("capital_allocation_pct", ascending=False).reset_index(drop=True)

    def fetch_positions_table(self) -> pd.DataFrame:
        """
        Fetch positions via API, attach LTP and compute P&L columns.
        """
        try:
            resp = self.client.get_positions()
        except Exception as e:
            logger.exception("Failed to fetch positions: %s", e)
            return pd.DataFrame()
        rows = self._parse_positions_response(resp)
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        # attach LTP (if last_price present use it)
        ltp_list = []
        for idx, r in df.iterrows():
            token = r["token"]
            exchange = r["exchange"]
            md = self.marketdata.get_ltp_for_token(token, exchange)
            ltp = md.get("lp") or r.get("last_price")
            ltp_list.append(ltp)
        df["ltp"] = ltp_list
        df["net_qty"] = pd.to_numeric(df["net_qty"], errors="coerce").fillna(0)
        df["avg_price"] = pd.to_numeric(df["avg_price"], errors="coerce").fillna(0)
        df["current_value"] = df["ltp"].fillna(0) * df["net_qty"]
        df["invested"] = df["avg_price"] * df["net_qty"]
        df["unrealized_pnl"] = df["current_value"] - df["invested"]
        df["realized_pnl"] = pd.to_numeric(df["realized_pnl"], errors="coerce").fillna(0)
        # capital allocation % (use absolute exposure)
        total_abs = df["invested"].abs().sum() if not df.empty else 1.0
        df["capital_allocation_pct"] = df["invested"].abs() / max(total_abs, 1e-9) * 100.0
        # TSL/targets based on avg_price
        tsl_cols = {"initial_sl": [], "tsl": [], "target1": [], "target2": [], "target3": [], "target4": []}
        for _, r in df.iterrows():
            entry = float(r["avg_price"])
            ltp_val = r["ltp"] if pd.notna(r["ltp"]) else None
            tvals = self.compute_tsl_and_targets(entry, ltp_val)
            for k,v in tvals.items():
                tsl_cols[k].append(v)
        for k,v in tsl_cols.items():
            df[k] = v
        display_cols = ["symbol","token","exchange","net_qty","avg_price","ltp","invested","current_value","unrealized_pnl","realized_pnl","capital_allocation_pct","initial_sl","tsl","target1","target2"]
        display_cols = [c for c in display_cols if c in df.columns]
        return df[display_cols].sort_values("capital_allocation_pct", ascending=False).reset_index(drop=True)

    def portfolio_summary(self) -> Dict[str, float]:
        """
        Compute overall totals: total_invested, total_current_value, total_unrealized_pnl, total_realized_pnl, todays_pnl ~ best effort
        """
        holdings_df = self.fetch_holdings_table()
        positions_df = self.fetch_positions_table()
        inv = float(holdings_df["invested"].sum()) if not holdings_df.empty else 0.0
        cur = float(holdings_df["current_value"].sum()) if not holdings_df.empty else 0.0
        unreal = float(holdings_df["unrealized_pnl"].sum()) if not holdings_df.empty else 0.0
        realized = float(positions_df["realized_pnl"].sum()) if not positions_df.empty else 0.0
        # today's pnl approximate: difference between current and invested of holdings + positions' day realized
        todays = unreal + realized
        return {
            "total_invested": inv,
            "total_current_value": cur,
            "total_unrealized_pnl": unreal,
            "total_realized_pnl": realized,
            "todays_pnl": todays,
            "capital": self.capital
        }
