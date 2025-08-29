import logging
from typing import Dict, Any
from trading_engine.session import get_session_safe

logger = logging.getLogger(__name__)


def place_order(order_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Place an order with given parameters
    """
    try:
        session = get_session_safe()
        if not session:
            raise Exception("⚠️ No active session found. Please login first.")

        order = session.place_order(**order_params)
        logger.info(f"✅ Order placed: {order}")
        return order
    except Exception as e:
        logger.error(f"❌ Error placing order: {str(e)}")
        return {"status": "error", "message": str(e)}


def modify_order(order_id: str, update_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Modify an existing order
    """
    try:
        session = get_session_safe()
        if not session:
            raise Exception("⚠️ No active session found.")

        order = session.modify_order(order_id, **update_params)
        logger.info(f"✅ Order modified: {order}")
        return order
    except Exception as e:
        logger.error(f"❌ Error modifying order: {str(e)}")
        return {"status": "error", "message": str(e)}


def cancel_order(order_id: str) -> Dict[str, Any]:
    """
    Cancel an existing order
    """
    try:
        session = get_session_safe()
        if not session:
            raise Exception("⚠️ No active session found.")

        result = session.cancel_order(order_id)
        logger.info(f"✅ Order cancelled: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Error cancelling order: {str(e)}")
        return {"status": "error", "message": str(e)}


def get_orders() -> Dict[str, Any]:
    """
    Fetch all orders
    """
    try:
        session = get_session_safe()
        if not session:
            raise Exception("⚠️ No active session found.")

        orders = session.get_orders()
        return orders
    except Exception as e:
        logger.error(f"❌ Error fetching orders: {str(e)}")
        return {"status": "error", "message": str(e)}
