# backend/orders/oco.py

import logging
import sqlite3
import time
from typing import Dict, Optional, List

from backend.api_client import APIClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


DB_FILE = "tradebot.db"


class OCOManager:
    """
    Manages OCO (One Cancels Other) and TSL (Trailing Stop Loss) groups.
    """

    def __init__(self, api: APIClient):
        self.api = api
        self.groups: Dict[str, Dict] = {}  # group_id → group info

        self._init_db()

    def _init_db(self):
        """Ensure SQLite tables exist."""
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS oco_groups (
                    group_id TEXT PRIMARY KEY,
                    tradingsymbol TEXT,
                    exchange TEXT,
                    parent_order_id TEXT,
                    target_order_id TEXT,
                    stoploss_order_id TEXT,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def create_group(
        self,
        group_id: str,
        tradingsymbol: str,
        exchange: str,
        order_type: str,
        quantity: int,
        target_price: float,
        stoploss_price: float,
        trailing: Optional[float] = None,
    ) -> Dict:
        """
        Create a new OCO group.
        """
        if group_id in self.groups:
            raise ValueError(f"OCO group {group_id} already exists")

        logger.info(f"Creating OCO group {group_id} for {tradingsymbol}")

        # Place target order
        try:
            target_resp = self.api.place_order(
                exchange=exchange,
                tradingsymbol=tradingsymbol,
                order_type=order_type,
                quantity=quantity,
                price=target_price,
                price_type="LIMIT",
                product_type="NORMAL",
            )
            target_order_id = target_resp.get("order_id")
        except Exception as e:
            logger.error(f"Target order failed: {e}")
            raise

        # Place stoploss order
        try:
            stoploss_resp = self.api.place_order(
                exchange=exchange,
                tradingsymbol=tradingsymbol,
                order_type="SELL" if order_type == "BUY" else "BUY",
                quantity=quantity,
                price=stoploss_price,
                price_type="STOPLOSS_LIMIT",
                product_type="NORMAL",
            )
            stoploss_order_id = stoploss_resp.get("order_id")
        except Exception as e:
            logger.error(f"Stoploss order failed: {e}")
            # If SL fails, cancel target
            if target_order_id:
                self.api.cancel_order(target_order_id)
            raise

        group_data = {
            "tradingsymbol": tradingsymbol,
            "exchange": exchange,
            "order_type": order_type,
            "quantity": quantity,
            "target_order_id": target_order_id,
            "stoploss_order_id": stoploss_order_id,
            "status": "OPEN",
            "trailing": trailing,
            "last_price": None,
        }
        self.groups[group_id] = group_data

        # Save in DB
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO oco_groups
                (group_id, tradingsymbol, exchange, parent_order_id,
                 target_order_id, stoploss_order_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    group_id,
                    tradingsymbol,
                    exchange,
                    None,
                    target_order_id,
                    stoploss_order_id,
                    "OPEN",
                ),
            )
            conn.commit()

        return {"status": "SUCCESS", "group_id": group_id, **group_data}

    def handle_fill(self, order_id: str):
        """
        Called when an order is filled. Cancels the opposite order.
        """
        for gid, group in self.groups.items():
            if group["target_order_id"] == order_id:
                logger.info(f"OCO {gid}: Target filled, cancelling stoploss")
                self.api.cancel_order(group["stoploss_order_id"])
                group["status"] = "CLOSED"
                self._update_status(gid, "CLOSED")
                return gid
            elif group["stoploss_order_id"] == order_id:
                logger.info(f"OCO {gid}: Stoploss filled, cancelling target")
                self.api.cancel_order(group["target_order_id"])
                group["status"] = "CLOSED"
                self._update_status(gid, "CLOSED")
                return gid
        return None

    def update_trailing(self, group_id: str, ltp: float):
        """
        Adjust stoploss dynamically if trailing SL is enabled.
        """
        group = self.groups.get(group_id)
        if not group or not group.get("trailing"):
            return

        if group["last_price"] is None:
            group["last_price"] = ltp
            return

        # Example trailing logic: if price moves favorably, trail stop
        trail_gap = group["trailing"]
        if group["order_type"] == "BUY":
            if ltp > group["last_price"]:
                new_sl = ltp - trail_gap
                logger.info(f"OCO {group_id}: Trailing SL updated to {new_sl}")
                # Cancel + re-place stoploss order
                self.api.cancel_order(group["stoploss_order_id"])
                sl_resp = self.api.place_order(
                    exchange=group["exchange"],
                    tradingsymbol=group["tradingsymbol"],
                    order_type="SELL",
                    quantity=group["quantity"],
                    price=new_sl,
                    price_type="STOPLOSS_LIMIT",
                    product_type="NORMAL",
                )
                group["stoploss_order_id"] = sl_resp.get("order_id")
                group["last_price"] = ltp
        else:
            # SELL side trailing
            if ltp < group["last_price"]:
                new_sl = ltp + trail_gap
                logger.info(f"OCO {group_id}: Trailing SL updated to {new_sl}")
                self.api.cancel_order(group["stoploss_order_id"])
                sl_resp = self.api.place_order(
                    exchange=group["exchange"],
                    tradingsymbol=group["tradingsymbol"],
                    order_type="BUY",
                    quantity=group["quantity"],
                    price=new_sl,
                    price_type="STOPLOSS_LIMIT",
                    product_type="NORMAL",
                )
                group["stoploss_order_id"] = sl_resp.get("order_id")
                group["last_price"] = ltp

    def cancel_group(self, group_id: str) -> bool:
        """
        Cancel both target + stoploss orders and close the group.
        """
        group = self.groups.get(group_id)
        if not group:
            logger.warning(f"OCO group {group_id} not found for cancel")
            return False

        try:
            if group["target_order_id"]:
                self.api.cancel_order(group["target_order_id"])
            if group["stoploss_order_id"]:
                self.api.cancel_order(group["stoploss_order_id"])
            group["status"] = "CANCELLED"
            self._update_status(group_id, "CANCELLED")
            logger.info(f"OCO group {group_id} cancelled successfully")
            return True
        except Exception as e:
            logger.error(f"Error cancelling OCO group {group_id}: {e}")
            return False

    def _update_status(self, group_id: str, status: str):
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE oco_groups SET status=? WHERE group_id=?",
                (status, group_id),
            )
            conn.commit()

    def list_groups(self) -> List[Dict]:
        """
        Return current OCO groups.
        """
        return [
            {"group_id": gid, **data}
            for gid, data in self.groups.items()
        ]


# For quick manual test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    api = APIClient()
    mgr = OCOManager(api)
    # Example create
    gid = f"oco-{int(time.time())}"
    mgr.create_group(
        group_id=gid,
        tradingsymbol="NIFTY23FEB23F",
        exchange="NFO",
        order_type="BUY",
        quantity=50,
        target_price=17665,
        stoploss_price=17500,
        trailing=10,
    )
    print(mgr.list_groups())
