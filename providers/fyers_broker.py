"""
providers/fyers_broker.py — Broker backend backed by Fyers API v3.

Wraps tools/execution/fyers_orders.py and fyers_client.py to implement
the Broker interface for live and paper trading in Indian equity markets.
"""

from __future__ import annotations

from dataclasses import asdict
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from providers.broker import Broker
from state.portfolio_state import Position
from tools.data.symbols import to_base_symbol, to_fyers_symbol
from tools.execution.fyers_client import get_fyers_client

logger = logging.getLogger(__name__)


class FyersBroker(Broker):
    """Live broker that executes orders via Fyers API v3.

    Handles Cash-and-Carry (CNC) equity swing delivery trades on NSE/BSE.
    """

    def __init__(self, settings) -> None:
        self._settings = settings
        self._cash: float = 0.0
        self._portfolio_value: float = 0.0
        self._peak_value: float = 0.0
        self._positions: dict[str, Position] = {}
        self._synced = False

    # ------------------------------------------------------------------
    # Broker interface: properties
    # ------------------------------------------------------------------

    @property
    def portfolio_value(self) -> float:
        return self._portfolio_value

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def positions(self) -> dict[str, Position]:
        return self._positions

    # ------------------------------------------------------------------
    # Broker interface: sync
    # ------------------------------------------------------------------

    def sync(self, sim_date: str | None = None, existing_positions=None) -> dict:
        """Sync portfolio state from Fyers and return sync response.

        Queries:
        - fyers.funds() for available cash and margin
        - fyers.holdings() for delivery equity holdings
        - fyers.positions() for today's active positions
        - fyers.orderbook() for open orders
        """
        client = get_fyers_client()
        now_str = datetime.now(timezone.utc).isoformat()

        if getattr(self._settings, "dry_run", False):
            # Dry-run sync: simulate portfolio state locally without calling Fyers API
            if self._cash <= 0.0:
                self._cash = float(getattr(self._settings, "dry_run_initial_cash", 500_000.0))

            # Reconcile existing positions if provided
            if existing_positions:
                for sym, pos in existing_positions.items():
                    if sym not in self._positions:
                        self._positions[sym] = pos

            holdings_market_val = 0.0
            positions_list: list[dict] = []
            positions_full: dict[str, dict] = {}

            for sym, pos in list(self._positions.items()):
                ltp = pos.current_price
                try:
                    from tools.data.symbols import to_yf_symbol
                    import yfinance as yf
                    yf_sym = to_yf_symbol(sym)
                    ticker_obj = yf.Ticker(yf_sym)
                    hist = ticker_obj.history(period="1d")
                    if not hist.empty:
                        ltp = float(hist["Close"].iloc[-1])
                        pos.current_price = ltp
                        pos.highest_close = max(pos.highest_close, ltp)
                except Exception:
                    pass

                mkt_val = round(pos.qty * ltp, 2)
                unrealized = round((ltp - pos.avg_entry_price) * pos.qty, 2)
                pos.unrealized_pnl = unrealized
                holdings_market_val += mkt_val

                positions_list.append({
                    "symbol": sym,
                    "qty": pos.qty,
                    "avg_entry_price": pos.avg_entry_price,
                    "current_price": ltp,
                    "market_value": mkt_val,
                    "unrealized_pnl": unrealized,
                    "stop_loss": pos.stop_loss_price,
                    "strategy": pos.strategy,
                })
                positions_full[sym] = asdict(pos)

            portfolio_val = round(self._cash + holdings_market_val, 2)
            peak_val = max(self._peak_value, portfolio_val)
            self._portfolio_value = portfolio_val
            self._peak_value = peak_val
            drawdown = max(0.0, (peak_val - portfolio_val) / peak_val) if peak_val > 0 else 0.0
            self._synced = True

            logger.info(
                "[DRY RUN] Portfolio Synced: cash=₹%.2f, portfolio_val=₹%.2f, positions=%d",
                self._cash, portfolio_val, len(positions_list),
            )
            return {
                "synced_at": now_str,
                "cash": self._cash,
                "buying_power": self._cash,
                "portfolio_value": self._portfolio_value,
                "peak_value": self._peak_value,
                "current_drawdown_pct": round(drawdown, 4),
                "position_count": len(positions_list),
                "positions": positions_list,
                "positions_full": positions_full,
                "open_orders": [],
                "today_rpl": 0.0,
                "newly_closed_positions": [],
                "error": None,
                "dry_run": True,
            }

        if client is None:
            logger.warning("Fyers client unavailable during sync. Returning empty state.")
            return {
                "synced_at": now_str,
                "cash": self._cash,
                "buying_power": self._cash,
                "portfolio_value": self._portfolio_value,
                "peak_value": self._peak_value,
                "current_drawdown_pct": 0.0,
                "position_count": len(self._positions),
                "positions": [],
                "positions_full": {},
                "open_orders": [],
                "today_rpl": 0.0,
                "newly_closed_positions": [],
                "error": "Fyers client unavailable (check FYERS_CLIENT_ID and FYERS_ACCESS_TOKEN)",
            }

        # 1. Fetch Funds
        cash = 0.0
        total_balance = 0.0
        today_rpl = 0.0
        try:
            funds_resp = client.funds()
            if isinstance(funds_resp, dict) and funds_resp.get("s") == "ok":
                for item in funds_resp.get("fund_limit", []):
                    title = item.get("title", "").lower()
                    amt = float(item.get("equityAmount", 0.0))
                    if "clear balance" in title or "available" in title or item.get("id") == 3:
                        cash = amt
                    elif "total balance" in title or item.get("id") == 1:
                        total_balance = amt
                    elif "realized" in title or item.get("id") == 10:
                        today_rpl = amt
                if cash == 0.0 and total_balance > 0.0:
                    cash = total_balance
            else:
                logger.warning("Fyers funds query response: %s", funds_resp)
        except Exception as exc:
            logger.error("Error syncing Fyers funds: %s", exc)

        # 2. Fetch Holdings & Net Positions
        holdings_map: dict[str, dict] = {}
        holdings_market_val = 0.0

        try:
            holdings_resp = client.holdings()
            if isinstance(holdings_resp, dict) and holdings_resp.get("s") == "ok":
                for h in holdings_resp.get("holdings", []):
                    sym = to_base_symbol(h.get("symbol", ""))
                    qty = int(h.get("quantity", 0))
                    if qty > 0:
                        cost = float(h.get("costPrice", 0.0))
                        ltp = float(h.get("ltp", 0.0) or cost)
                        mkt_val = float(h.get("marketVal", qty * ltp))
                        holdings_market_val += mkt_val
                        holdings_map[sym] = {
                            "qty": qty,
                            "avg_entry_price": cost,
                            "current_price": ltp,
                            "market_value": mkt_val,
                            "unrealized_pnl": float(h.get("pl", (ltp - cost) * qty)),
                        }
        except Exception as exc:
            logger.error("Error syncing Fyers holdings: %s", exc)

        # Also check today's net positions (intraday buys before settlement)
        try:
            positions_resp = client.positions()
            if isinstance(positions_resp, dict) and positions_resp.get("s") == "ok":
                for p in positions_resp.get("netPositions", []):
                    sym = to_base_symbol(p.get("symbol", ""))
                    qty = int(p.get("netQty", 0))
                    if qty > 0:
                        cost = float(p.get("netAvg", 0.0) or p.get("buyAvg", 0.0))
                        ltp = float(p.get("ltp", 0.0) or cost)
                        mkt_val = qty * ltp
                        holdings_market_val += mkt_val
                        if sym in holdings_map:
                            holdings_map[sym]["qty"] += qty
                            holdings_map[sym]["market_value"] += mkt_val
                        else:
                            holdings_map[sym] = {
                                "qty": qty,
                                "avg_entry_price": cost,
                                "current_price": ltp,
                                "market_value": mkt_val,
                                "unrealized_pnl": float(p.get("unrealized_profit", (ltp - cost) * qty)),
                            }
        except Exception as exc:
            logger.error("Error syncing Fyers positions: %s", exc)

        # 3. Calculate portfolio value
        portfolio_val = round(cash + holdings_market_val, 2)
        peak_val = max(self._peak_value, portfolio_val)
        self._cash = cash
        self._portfolio_value = portfolio_val
        self._peak_value = peak_val

        drawdown = 0.0
        if peak_val > 0:
            drawdown = max(0.0, (peak_val - portfolio_val) / peak_val)

        # 4. Fetch open orders
        open_orders_list: list[dict] = []
        try:
            orderbook_resp = client.orderbook()
            if isinstance(orderbook_resp, dict) and orderbook_resp.get("s") == "ok":
                for o in orderbook_resp.get("orderBook", []):
                    if o.get("status") in (1, 6):  # Pending / Open
                        open_orders_list.append({
                            "order_id": o.get("id"),
                            "symbol": to_base_symbol(o.get("symbol", "")),
                            "qty": int(o.get("qty", 0)),
                            "side": "buy" if o.get("side") == 1 else "sell",
                            "status": "open",
                        })
        except Exception as exc:
            logger.warning("Error syncing Fyers orderbook: %s", exc)

        # 5. Reconcile positions dictionary with existing metadata
        synced_syms = set(holdings_map.keys())
        newly_closed = []

        # Detect closed positions
        for sym, old_pos in list(self._positions.items()):
            if sym not in synced_syms:
                logger.info("FyersBroker: Position for %s no longer open (closed)", sym)
                newly_closed.append({
                    "symbol": sym,
                    "qty": old_pos.qty,
                    "avg_entry_price": old_pos.avg_entry_price,
                    "exit_price": old_pos.current_price,
                    "pnl": (old_pos.current_price - old_pos.avg_entry_price) * old_pos.qty,
                })
                del self._positions[sym]

        # Update / create active positions
        positions_full: dict[str, dict] = {}
        positions_list: list[dict] = []

        for sym, h in holdings_map.items():
            existing = None
            if existing_positions and sym in existing_positions:
                existing = existing_positions[sym]
            elif sym in self._positions:
                existing = self._positions[sym]

            strategy = existing.strategy if existing else "MOMENTUM"
            entry_date = existing.entry_date if existing else now_str[:10]
            stop_loss = existing.stop_loss_price if existing else (h["avg_entry_price"] * 0.95)
            bid = existing.bracket_order_id if existing else ""

            pos_obj = Position(
                symbol=sym,
                qty=h["qty"],
                avg_entry_price=h["avg_entry_price"],
                current_price=h["current_price"],
                stop_loss_price=stop_loss,
                unrealized_pnl=h.get("unrealized_pnl", 0.0),
                strategy=strategy,
                entry_date=entry_date,
                bracket_order_id=bid or "",
                highest_close=h["current_price"],
            )
            self._positions[sym] = pos_obj

            p_dict = {
                "symbol": sym,
                "qty": h["qty"],
                "avg_entry_price": h["avg_entry_price"],
                "current_price": h["current_price"],
                "market_value": h["market_value"],
                "unrealized_pnl": h["unrealized_pnl"],
                "stop_loss": stop_loss,
                "strategy": strategy,
            }
            positions_list.append(p_dict)
            positions_full[sym] = asdict(pos_obj)

        self._synced = True

        result = {
            "synced_at": now_str,
            "cash": self._cash,
            "buying_power": self._cash,
            "portfolio_value": self._portfolio_value,
            "peak_value": self._peak_value,
            "current_drawdown_pct": round(drawdown, 4),
            "position_count": len(positions_list),
            "positions": positions_list,
            "positions_full": positions_full,
            "open_orders": open_orders_list,
            "today_rpl": round(today_rpl, 2),
            "newly_closed_positions": newly_closed,
            "error": None,
        }
        return result

    # ------------------------------------------------------------------
    # Broker interface: order execution
    # ------------------------------------------------------------------

    def submit_entry(
        self,
        ticker: str,
        shares: int,
        stop_loss: float,
        take_profit: float,
        strategy: str,
        signal_price: float,
        entry_type: str = "MARKET",
        limit_price: float | None = None,
        atr: float = 0.0,
    ) -> dict:
        """Place a CNC buy order via Fyers.

        Also attaches a GTT stop or creates local position with stop level.
        """
        from tools.execution.fyers_orders import place_cnc_order, create_or_update_gtt_stop

        base_ticker = to_base_symbol(ticker)

        if getattr(self._settings, "dry_run", False):
            fill_price = float(limit_price or signal_price or 0.0)
            if fill_price <= 0.0:
                pos = self._positions.get(base_ticker)
                fill_price = pos.current_price if pos else 100.0
            cost = round(fill_price * shares, 2)
            self._cash = max(0.0, round(self._cash - cost, 2))
            sim_id = f"SIM-ORD-{int(datetime.now(timezone.utc).timestamp() * 1000)}"

            pos_obj = Position(
                symbol=base_ticker,
                qty=shares,
                avg_entry_price=fill_price,
                current_price=fill_price,
                stop_loss_price=stop_loss,
                strategy=strategy,
                entry_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                bracket_order_id=sim_id,
                highest_close=fill_price,
            )
            self._positions[base_ticker] = pos_obj

            logger.info(
                "[DRY RUN] Simulated CNC BUY: %d shares of %s @ ₹%.2f (Cost: ₹%.2f, Stop: ₹%.2f, TP: ₹%.2f, SimID: %s)",
                shares, base_ticker, fill_price, cost, stop_loss, take_profit, sim_id,
            )

            return {
                "status": "submitted",
                "order_id": sim_id,
                "symbol": base_ticker,
                "shares": shares,
                "fill_price": fill_price,
                "stop_loss_price": stop_loss,
                "take_profit_price": take_profit,
                "gtt_id": f"SIM-GTT-{sim_id}",
                "dry_run": True,
            }

        logger.info(
            "FyersBroker.submit_entry: buying %d shares of %s (entry_type=%s, limit=%s, stop=%.2f, tp=%.2f)",
            shares, base_ticker, entry_type, limit_price, stop_loss, take_profit,
        )

        order_res = place_cnc_order(
            symbol=base_ticker,
            qty=shares,
            side="buy",
            order_type=entry_type,
            limit_price=limit_price,
        )

        if order_res.get("error"):
            logger.error("FyersBroker.submit_entry failed: %s", order_res["error"])
            return order_res

        # Register GTT trigger for multi-day stop loss protection
        gtt_res = create_or_update_gtt_stop(
            symbol=base_ticker,
            qty=shares,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
        )

        gtt_id = gtt_res.get("gtt_id")
        order_res["gtt_id"] = gtt_id
        order_res["stop_loss_price"] = stop_loss
        order_res["take_profit_price"] = take_profit

        # Create position in local cache immediately
        self._positions[base_ticker] = Position(
            symbol=base_ticker,
            qty=shares,
            avg_entry_price=signal_price or float(limit_price or 0.0),
            current_price=signal_price or float(limit_price or 0.0),
            stop_loss_price=stop_loss,
            strategy=strategy,
            entry_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            bracket_order_id=gtt_id or "",
            highest_close=signal_price or float(limit_price or 0.0),
        )

        return order_res

    def execute_exit(
        self,
        ticker: str,
        qty: int | None = None,
        exit_pct: float = 1.0,
        sim_date: str | None = None,
        bars=None,
        **kwargs,
    ) -> dict | None:
        """Place a CNC market/limit sell order via Fyers to exit position.

        Cancels any open orders/GTT triggers for this symbol first.
        """
        from tools.execution.fyers_orders import (
            cancel_open_orders_for_symbol,
            place_cnc_order,
            poll_order_fill,
        )

        base_ticker = to_base_symbol(ticker)
        pos = self._positions.get(base_ticker)
        if pos is None and qty is None:
            logger.warning("FyersBroker.execute_exit: no position found for %s", base_ticker)
            return None

        sell_qty = qty
        if sell_qty is None and pos:
            sell_qty = max(1, int(pos.qty * exit_pct))
        elif sell_qty is None:
            sell_qty = 1

        if getattr(self._settings, "dry_run", False):
            exit_price = pos.current_price if (pos and pos.current_price > 0) else 0.0
            if exit_price <= 0 and bars is not None and hasattr(bars, "empty") and not bars.empty:
                exit_price = float(bars["Close"].iloc[-1])
            if exit_price <= 0 and pos:
                exit_price = pos.avg_entry_price

            pnl = round((exit_price - (pos.avg_entry_price if pos else exit_price)) * sell_qty, 2)
            proceeds = round(exit_price * sell_qty, 2)
            self._cash = round(self._cash + proceeds, 2)

            if pos:
                if sell_qty >= pos.qty:
                    del self._positions[base_ticker]
                else:
                    pos.qty -= sell_qty

            logger.info(
                "[DRY RUN] Simulated CNC SELL: %d shares of %s @ ₹%.2f (Proceeds: ₹%.2f, PnL: ₹%.2f)",
                sell_qty, base_ticker, exit_price, proceeds, pnl,
            )

            return {
                "ticker": base_ticker,
                "exit_price": exit_price,
                "exit_qty": sell_qty,
                "pnl": pnl,
                "action": "EXIT_FILLED",
                "status": "filled",
                "dry_run": True,
            }

        # 1. Cancel open orders/triggers
        cancel_open_orders_for_symbol(base_ticker)

        # 2. Place CNC sell order
        order_res = place_cnc_order(
            symbol=base_ticker,
            qty=sell_qty,
            side="sell",
            order_type="market",
        )

        if order_res.get("error"):
            logger.error("FyersBroker.execute_exit failed for %s: %s", base_ticker, order_res["error"])
            return order_res

        # 3. Poll for fill
        order_id = order_res.get("order_id")
        if order_id:
            fill = poll_order_fill(order_id, max_attempts=4, delay=1.0)
            if fill.get("filled"):
                fill_price = fill["filled_avg_price"]
                order_res["exit_price"] = fill_price
                order_res["exit_qty"] = fill.get("filled_qty", sell_qty)
                if pos and pos.avg_entry_price > 0:
                    order_res["pnl"] = round((fill_price - pos.avg_entry_price) * sell_qty, 2)
                logger.info(
                    "FyersBroker.execute_exit: %s filled @ ₹%.2f (pnl=₹%.2f)",
                    base_ticker, fill_price, order_res.get("pnl", 0),
                )
            else:
                est = pos.current_price if pos and pos.current_price > 0 else 0.0
                order_res["exit_price"] = est
                order_res["exit_qty"] = sell_qty
                if pos and pos.avg_entry_price > 0:
                    order_res["pnl"] = round((est - pos.avg_entry_price) * sell_qty, 2)
                order_res["estimated"] = True

        return order_res

    def update_stop(
        self,
        ticker: str,
        new_stop: float,
        bracket_order_id: str | None = None,
    ) -> dict:
        """Update stop-loss price for an existing position."""
        from tools.execution.fyers_orders import create_or_update_gtt_stop

        base_ticker = to_base_symbol(ticker)
        pos = self._positions.get(base_ticker)
        if not pos:
            return {"modified": False, "error": f"No position for {base_ticker}"}

        old_stop = pos.stop_loss_price
        pos.stop_loss_price = float(new_stop)

        if getattr(self._settings, "dry_run", False):
            logger.info(
                "[DRY RUN] Simulated Stop Updated: %s ₹%.2f -> ₹%.2f",
                base_ticker, old_stop, new_stop,
            )
            return {
                "modified": True,
                "ticker": base_ticker,
                "old_stop": old_stop,
                "new_stop": new_stop,
                "dry_run": True,
            }

        # Update GTT stop
        gtt_res = create_or_update_gtt_stop(
            symbol=base_ticker,
            qty=pos.qty,
            stop_loss_price=float(new_stop),
        )

        logger.info(
            "FyersBroker.update_stop: %s stop updated ₹%.2f -> ₹%.2f (gtt=%s)",
            base_ticker, old_stop, new_stop, gtt_res.get("gtt_id"),
        )

        return {
            "modified": True,
            "ticker": base_ticker,
            "old_stop": old_stop,
            "new_stop": new_stop,
            "gtt_response": gtt_res,
        }
