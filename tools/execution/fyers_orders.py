"""
tools/execution/fyers_orders.py — Fyers order execution and management tools.

Wraps the fyers-apiv3 SDK for order placement (CNC delivery equity for swing trading),
cancellations, GTT stop triggers, and order fill polling.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from tools.data.symbols import to_base_symbol, to_fyers_symbol
from tools.execution.fyers_client import get_fyers_client, is_fyers_available

logger = logging.getLogger(__name__)


def place_cnc_order(
    symbol: str,
    qty: int,
    side: str = "buy",
    order_type: str = "market",
    limit_price: float | None = None,
    stop_price: float | None = None,
) -> dict:
    """Place a Cash-and-Carry (CNC) delivery order via Fyers API v3.

    Args:
        symbol: Trading symbol (base like 'RELIANCE' or 'NSE:RELIANCE-EQ').
        qty: Number of shares. Must be > 0.
        side: 'buy' or 'sell'.
        order_type: 'market', 'limit', or 'stop_limit'.
        limit_price: Required if order_type is 'limit' or 'stop_limit'.
        stop_price: Trigger price if order_type is 'stop' or 'stop_limit'.

    Returns:
        dict with order response or error.
    """
    client = get_fyers_client()
    if client is None:
        return {"error": "Fyers client not available. Check credentials."}

    fyers_symbol = to_fyers_symbol(symbol)
    side_code = 1 if side.lower() == "buy" else -1

    # Fyers order types: 1: Limit, 2: Market, 3: Stop-Market (SL-M), 4: Stop-Limit (SL-L)
    ot = order_type.lower()
    if ot == "limit":
        type_code = 1
        price = float(limit_price or 0.0)
        stop = 0.0
    elif ot in ("stop", "stop_market", "sl_m"):
        type_code = 3
        price = 0.0
        stop = float(stop_price or 0.0)
    elif ot in ("stop_limit", "sl_l"):
        type_code = 4
        price = float(limit_price or 0.0)
        stop = float(stop_price or limit_price or 0.0)
    else:
        type_code = 2  # Market
        price = 0.0
        stop = 0.0

    payload = {
        "symbol": fyers_symbol,
        "qty": int(qty),
        "type": type_code,
        "side": side_code,
        "productType": "CNC",
        "limitPrice": price,
        "stopPrice": stop,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
    }

    try:
        resp = client.place_order(payload)
        logger.info("Fyers place_order payload: %s -> response: %s", payload, resp)

        if resp.get("s") == "ok":
            return {
                "order_id": resp.get("id"),
                "status": "submitted",
                "symbol": fyers_symbol,
                "ticker": to_base_symbol(fyers_symbol),
                "qty": qty,
                "side": side.lower(),
                "order_type": ot,
                "raw_response": resp,
            }
        else:
            err_msg = resp.get("message") or resp.get("errMsg") or str(resp)
            logger.error("Fyers place_order failed for %s: %s", fyers_symbol, err_msg)
            return {"error": f"Fyers order rejected: {err_msg}", "raw_response": resp}

    except Exception as exc:
        logger.exception("Fyers place_order exception for %s: %s", fyers_symbol, exc)
        return {"error": str(exc)}


def create_or_update_gtt_stop(
    symbol: str,
    qty: int,
    stop_loss_price: float,
    take_profit_price: float | None = None,
) -> dict:
    """Create a Good-Till-Triggered (GTT) order for overnight stop loss protection.

    In Indian markets, CNC holdings require GTT for multi-day stop losses.
    """
    client = get_fyers_client()
    if client is None:
        return {"error": "Fyers client not available"}

    fyers_symbol = to_fyers_symbol(symbol)

    # GTT payload for Fyers v3
    gtt_data = {
        "symbol": fyers_symbol,
        "side": -1,  # Sell trigger to exit
        "qty": int(qty),
        "productType": "CNC",
        "triggerPrice": round(float(stop_loss_price), 2),
        "limitPrice": round(float(stop_loss_price) * 0.995, 2),  # Limit slightly below trigger for fill certainty
    }

    try:
        # Check if fyers client has create_gtt
        if hasattr(client, "create_gtt"):
            resp = client.create_gtt(data=gtt_data)
            if resp.get("s") == "ok":
                logger.info("Fyers GTT stop created for %s @ %.2f", fyers_symbol, stop_loss_price)
                return {"success": True, "gtt_id": resp.get("id"), "stop_price": stop_loss_price}
            else:
                logger.warning("Fyers create_gtt returned: %s", resp)
                return {"error": resp.get("message", str(resp))}
        else:
            logger.info("create_gtt not available on client object; using agent-level stop tracking.")
            return {"success": True, "gtt_id": None, "note": "Managed by agent intraday loop"}
    except Exception as exc:
        logger.warning("Fyers GTT stop creation error: %s", exc)
        return {"error": str(exc)}


def cancel_open_orders_for_symbol(symbol: str) -> dict:
    """Cancel all pending / open orders for a specific ticker."""
    client = get_fyers_client()
    if client is None:
        return {"cancelled_count": 0, "error": "Client not available"}

    base = to_base_symbol(symbol).upper()
    fyers_sym = to_fyers_symbol(symbol).upper()

    cancelled_count = 0
    try:
        orderbook = client.orderbook()
        orders = orderbook.get("orderBook", []) if isinstance(orderbook, dict) else []

        for o in orders:
            o_sym = o.get("symbol", "").upper()
            # Status: 6 is pending / open in Fyers
            status = o.get("status")
            if (o_sym == fyers_sym or to_base_symbol(o_sym) == base) and status in (1, 6):
                oid = o.get("id")
                if oid:
                    client.cancel_order({"id": oid})
                    cancelled_count += 1
                    logger.info("Cancelled Fyers order %s for %s", oid, symbol)

    except Exception as exc:
        logger.warning("Failed to cancel open orders for %s: %s", symbol, exc)

    return {"cancelled_count": cancelled_count}


def poll_order_fill(order_id: str, max_attempts: int = 5, delay: float = 1.0) -> dict:
    """Poll Fyers orderbook to determine if an order was filled and at what price."""
    client = get_fyers_client()
    if client is None:
        return {"filled": False, "error": "Client not available"}

    for attempt in range(max_attempts):
        try:
            resp = client.orderbook()
            orders = resp.get("orderBook", []) if isinstance(resp, dict) else []
            for o in orders:
                if o.get("id") == order_id:
                    status = o.get("status")  # 2: Filled, 5: Cancelled, 6: Open
                    if status == 2:
                        avg_price = float(o.get("tradedPrice", 0.0) or o.get("limitPrice", 0.0))
                        filled_qty = int(o.get("filledQty", 0))
                        return {
                            "filled": True,
                            "filled_avg_price": avg_price,
                            "filled_qty": filled_qty,
                            "raw_order": o,
                        }
                    elif status == 5:
                        return {"filled": False, "cancelled": True, "error": "Order cancelled"}
        except Exception as exc:
            logger.warning("Error polling Fyers order fill: %s", exc)

        time.sleep(delay)

    return {"filled": False, "pending": True}
