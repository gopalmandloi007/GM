# trading_engine/orders.py
from __future__ import annotations
import os
import json
import uuid
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Union

import pandas as pd

from utils.file_manager import ensure_dir, read_csv_safe, to_csv_atomic

logger = logging.getLogger("trading_engine.orders")
logger.setLevel(logging.INFO)

# Storage path
ORDERS_DIR = os.path.join("data", "orders")
ORDERS_FILE = os.path.join(ORDERS_DIR, "orders.csv")

# CSV columns schema
ORDER_COLUMNS = [
    "local_id",            # uuid local
    "broker_order_id",     # broker's order id if any
    "symbol",
    "token",
    "exchange",
    "side",                # BUY/SELL
    "quantity",
    "price",
    "price_type",          # MARKET/LIMIT/SL/SL-M
    "product_type",        # NORMAL/INTRADAY/NRML etc.
    "variety",             # REGULAR/GTT/OCO/...
    "status",              # OPEN/COMPLETE/CANCELLED/REJECTED/PARTIAL
    "filled_qty",
    "avg_traded_price",
    "raw_response",        # json string of broker response
    "created_at",
    "updated_at",
]

# Ensure storage dir exists
ensure_dir(ORDERS_DIR)


# ---------- Low-level CSV helpers ----------
def _make_empty_orders_df() -> pd.DataFrame:
    df = pd.DataFrame(columns=ORDER_COLUMNS)
    return df

def load_orders() -> pd.DataFrame:
    """
    Load orders CSV into DataFrame. If not exists, returns empty df with schema.
    """
    df = read_csv_safe(ORDERS_FILE)
    if df is None:
        return _make_empty_orders_df()
    # ensure all expected cols exist
    for c in ORDER_COLUMNS:
        if c not in df.columns:
            df[c] = None
    # normalize dtypes minimally
    return df[ORDER_COLUMNS].copy()

def save_orders(df: pd.DataFrame) -> None:
    """
    Persist DataFrame to CSV atomically.
    """
    ensure_dir(ORDERS_DIR)
    # ensure columns order
    df = df.copy()
    for c in ORDER_COLUMNS:
        if c not in df.columns:
            df[c] = None
    to_csv_atomic(df[ORDER_COLUMNS], ORDERS_FILE, index=False)

def append_order_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Append a single order row (dict) to orders file, return the row (with local_id)
    """
    df = load_orders()
    # ensure local_id
    if "local_id" not in row or not row.get("local_id"):
        row["local_id"] = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    row.setdefault("created_at", now)
    row.setdefault("updated_at", now)
    # fill missing ORDER_COLUMNS
    for col in ORDER_COLUMNS:
        if col not in row:
            row[col] = None
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_orders(df)
    return row


# ---------- Query helpers ----------
def get_orders() -> pd.DataFrame:
    """Return all orders (DataFrame)"""
    return load_orders()

def get_open_orders() -> pd.DataFrame:
    df = load_orders()
    return df[df["status"].isin(["OPEN", "PARTIAL"])].copy()

def get_order_by_local_id(local_id: str) -> Optional[Dict[str, Any]]:
    df = load_orders()
    row = df.loc[df["local_id"] == local_id]
    if row.empty:
        return None
    return row.iloc[0].to_dict()

def update_order_by_local_id(local_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    df = load_orders()
    idx = df.index[df["local_id"] == local_id].tolist()
    if not idx:
        return None
    i = idx[0]
    for k, v in updates.items():
        if k in df.columns:
            df.at[i, k] = v
    df.at[i, "updated_at"] = datetime.utcnow().isoformat()
    save_orders(df)
    return df.loc[df["local_id"] == local_id].iloc[0].to_dict()


# ---------- Broker integration wrappers ----------
def _safe_extract_response(resp: Any) -> str:
    try:
        return json.dumps(resp)
    except Exception:
        return str(resp)


def place_order_via_api(
    api_client,
    payload: Dict[str, Any],
    persist_local: bool = True
) -> Dict[str, Any]:
    """
    Place an order via APIClient. `api_client` should implement `place_order(payload)` and return broker response.
    If persist_local True, the order and broker response are saved to local CSV as well.
    Returns a dict with `status`, `local_id`, `broker_order_id`, `broker_response`.
    """
    # basic payload normalization - expect keys: exchange, tradingsymbol/token, quantity, price, product_type, order_type/price_type, variety(optional)
    local_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    row = {
        "local_id": local_id,
        "broker_order_id": None,
        "symbol": payload.get("tradingsymbol") or payload.get("symbol"),
        "token": str(payload.get("token") or ""),
        "exchange": payload.get("exchange") or "NSE",
        "side": (payload.get("order_type") or payload.get("side") or "").upper(),
        "quantity": payload.get("quantity"),
        "price": payload.get("price"),
        "price_type": payload.get("price_type") or payload.get("order_type") or payload.get("price_type"),
        "product_type": payload.get("product_type"),
        "variety": payload.get("variety", "REGULAR"),
        "status": "OPEN",
        "filled_qty": 0,
        "avg_traded_price": None,
        "raw_response": None,
        "created_at": now,
        "updated_at": now,
    }

    try:
        broker_resp = api_client.place_order(payload)
    except Exception as e:
        logger.exception("Broker place_order failed: %s", e)
        # persist failed order with REJECTED status
        row["status"] = "REJECTED"
        row["raw_response"] = _safe_extract_response({"error": str(e)})
        if persist_local:
            append_order_row(row)
        return {"status": "error", "message": str(e), "local_id": local_id}

    # success path - attempt to extract broker order id and filled info
    row["raw_response"] = _safe_extract_response(broker_resp)
    # try common keys used earlier in docs: order_id / order_id
    broker_order_id = None
    try:
        if isinstance(broker_resp, dict):
            broker_order_id = broker_resp.get("order_id") or broker_resp.get("orders", [{}])[0].get("order_id") or broker_resp.get("orderid") or broker_resp.get("id")
    except Exception:
        broker_order_id = None

    row["broker_order_id"] = broker_order_id
    # inspect status from broker_resp if present
    broker_status = None
    filled_qty = 0
    avg_price = None
    try:
        if isinstance(broker_resp, dict):
            broker_status = broker_resp.get("status") or broker_resp.get("order_status")
            # if single order dict
            if "filled_qty" in broker_resp:
                filled_qty = int(broker_resp.get("filled_qty") or 0)
            # check nested orders list
            if "orders" in broker_resp and isinstance(broker_resp["orders"], list) and broker_resp["orders"]:
                ord0 = broker_resp["orders"][0]
                filled_qty = int(ord0.get("filled_qty") or filled_qty or 0)
                avg_price = ord0.get("average_traded_price") or ord0.get("avg_traded_price") or avg_price
    except Exception:
        pass

    if broker_status and str(broker_status).upper() in ("SUCCESS", "COMPLETE", "COMPLETE"):
        row["status"] = "COMPLETE"
    else:
        # if filled_qty equals qty treat as complete
        try:
            if filled_qty and int(filled_qty) >= int(row["quantity"]):
                row["status"] = "COMPLETE"
            else:
                row["status"] = "OPEN"
        except Exception:
            row["status"] = "OPEN"

    row["filled_qty"] = filled_qty
    row["avg_traded_price"] = avg_price
    if persist_local:
        append_order_row(row)

    return {"status": "ok", "local_id": local_id, "broker_order_id": broker_order_id, "broker_response": broker_resp}


def modify_order_via_api(api_client, broker_order_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Modify order via broker API. Expects api_client.modify_order(broker_order_id, payload).
    Returns dict of broker response; also updates local CSV if broker returns success.
    """
    try:
        resp = api_client.modify_order(broker_order_id, payload)
    except Exception as e:
        logger.exception("Broker modify failed: %s", e)
        return {"status": "error", "message": str(e)}
    # update local record if present
    # find order by broker_order_id
    df = load_orders()
    idx = df.index[df["broker_order_id"] == str(broker_order_id)].tolist()
    if idx:
        i = idx[0]
        # update price/quantity if returned new values
        try:
            if isinstance(resp, dict):
                new_price = resp.get("price")
                new_qty = resp.get("quantity")
                df.at[i, "price"] = new_price or df.at[i, "price"]
                df.at[i, "quantity"] = new_qty or df.at[i, "quantity"]
                df.at[i, "raw_response"] = _safe_extract_response(resp)
                df.at[i, "updated_at"] = datetime.utcnow().isoformat()
                save_orders(df)
        except Exception:
            logger.exception("Failed updating local order after modify")
    return {"status": "ok", "broker_response": resp}


def cancel_order_via_api(api_client, broker_order_id: str) -> Dict[str, Any]:
    """
    Cancel order via broker API. Expects api_client.cancel_order(broker_order_id).
    Updates local CSV status to CANCELLED on success.
    """
    try:
        resp = api_client.cancel_order(broker_order_id)
    except Exception as e:
        logger.exception("Broker cancel failed: %s", e)
        return {"status": "error", "message": str(e)}

    # update local file
    df = load_orders()
    idx = df.index[df["broker_order_id"] == str(broker_order_id)].tolist()
    if idx:
        i = idx[0]
        df.at[i, "status"] = "CANCELLED"
        df.at[i, "raw_response"] = _safe_extract_response(resp)
        df.at[i, "updated_at"] = datetime.utcnow().isoformat()
        save_orders(df)
    return {"status": "ok", "broker_response": resp}


# ---------- Public high-level helpers ----------
def place_order(
    symbol: str,
    side: str,
    quantity: Union[int, float],
    price: Optional[Union[int, float]] = 0,
    price_type: str = "MARKET",
    product_type: str = "NORMAL",
    exchange: str = "NSE",
    token: Optional[str] = None,
    variety: str = "REGULAR",
    api_client: Optional[Any] = None,
    persist_local: bool = True,
) -> Dict[str, Any]:
    """
    Place a single order. If api_client provided, send to broker; otherwise log locally.
    Returns dict with status and local_id etc.
    """
    payload = {
        "exchange": exchange,
        "token": token,
        "tradingsymbol": symbol,
        "quantity": str(quantity),
        "price": str(price),
        "price_type": price_type,
        "product_type": product_type,
        "order_type": side,  # broker may expect 'order_type' for side
        "variety": variety,
    }

    if api_client:
        return place_order_via_api(api_client, payload, persist_local=persist_local)

    # offline/local logging path
    local_row = {
        "local_id": str(uuid.uuid4()),
        "broker_order_id": None,
        "symbol": symbol,
        "token": str(token or ""),
        "exchange": exchange,
        "side": side.upper(),
        "quantity": int(quantity),
        "price": float(price) if price is not None else 0.0,
        "price_type": price_type,
        "product_type": product_type,
        "variety": variety,
        "status": "OPEN",
        "filled_qty": 0,
        "avg_traded_price": None,
        "raw_response": json.dumps({"local_log": True}),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    append_order_row(local_row)
    return {"status": "ok", "local_id": local_row["local_id"]}


def modify_order(local_id: Optional[str] = None, broker_order_id: Optional[str] = None, updates: Dict[str, Any] = None, api_client: Optional[Any] = None) -> Dict[str, Any]:
    """
    Modify order either in local CSV (if no api_client) or via broker API.
    Provide either local_id or broker_order_id.
    updates: dict with fields to update e.g. {"price": 1200, "quantity": 5}
    """
    if updates is None:
        updates = {}
    if api_client and broker_order_id:
        return modify_order_via_api(api_client, broker_order_id, updates)

    # local modify
    if not local_id:
        return {"status": "error", "message": "local_id required for local modify"}
    row = get_order_by_local_id(local_id)
    if not row:
        return {"status": "error", "message": "order not found"}
    # apply updates
    upd = {}
    for k in ("price", "quantity", "price_type", "product_type"):
        if k in updates:
            upd[k] = updates[k]
    upd["updated_at"] = datetime.utcnow().isoformat()
    updated = update_order_by_local_id(local_id, upd)
    return {"status": "ok", "updated": updated}


def cancel_order(local_id: Optional[str] = None, broker_order_id: Optional[str] = None, api_client: Optional[Any] = None) -> Dict[str, Any]:
    """
    Cancel order: prefer broker cancel if api_client provided, otherwise mark local order CANCELLED.
    """
    if api_client and broker_order_id:
        return cancel_order_via_api(api_client, broker_order_id)

    if not local_id:
        return {"status": "error", "message": "local_id required for local cancel"}
    row = get_order_by_local_id(local_id)
    if not row:
        return {"status": "error", "message": "order not found"}
    updated = update_order_by_local_id(local_id, {"status": "CANCELLED", "updated_at": datetime.utcnow().isoformat()})
    return {"status": "ok", "updated": updated}


def place_batch_orders(batch: List[Dict[str, Any]], api_client: Optional[Any] = None, persist_local: bool = True) -> List[Dict[str, Any]]:
    """
    Place multiple orders. Each item in batch is dict accepted by place_order.
    Returns list of result dicts.
    """
    results = []
    for item in batch:
        try:
            res = place_order(
                symbol=item.get("symbol") or item.get("tradingsymbol"),
                side=item.get("side") or item.get("order_type"),
                quantity=item.get("quantity"),
                price=item.get("price"),
                price_type=item.get("price_type", "MARKET"),
                product_type=item.get("product_type", "NORMAL"),
                exchange=item.get("exchange", "NSE"),
                token=item.get("token"),
                variety=item.get("variety", "REGULAR"),
                api_client=api_client,
                persist_local=persist_local,
            )
            results.append(res)
        except Exception as e:
            logger.exception("Batch place error for item %s: %s", item, e)
            results.append({"status": "error", "message": str(e)})
    return results
