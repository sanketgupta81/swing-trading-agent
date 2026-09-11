"""
tests/test_dry_run.py — Unit tests for Dry-Run mode and simulated order execution.
"""

from unittest.mock import patch
import pytest

from config.settings import Settings
from providers.fyers_broker import FyersBroker
from main import parse_args


def test_dry_run_settings_defaults():
    settings = Settings()
    assert settings.dry_run is False
    assert settings.dry_run_initial_cash == 500_000.0


def test_dry_run_cli_flag():
    with patch("sys.argv", ["main.py", "--dry-run"]):
        args = parse_args()
        assert args.dry_run is True

    with patch("sys.argv", ["main.py"]):
        args = parse_args()
        assert args.dry_run is False


def test_dry_run_fyers_broker_sync_without_credentials():
    settings = Settings(
        broker_type="fyers",
        dry_run=True,
        dry_run_initial_cash=750_000.0,
        fyers_client_id="",
        fyers_access_token="",
    )
    broker = FyersBroker(settings)

    # Sync should succeed without network calls or credentials
    result = broker.sync()

    assert result.get("error") is None
    assert result.get("dry_run") is True
    assert result.get("cash") == 750_000.0
    assert result.get("portfolio_value") == 750_000.0
    assert result.get("position_count") == 0


def test_dry_run_fyers_broker_full_lifecycle():
    settings = Settings(
        broker_type="fyers",
        dry_run=True,
        dry_run_initial_cash=500_000.0,
    )
    broker = FyersBroker(settings)
    broker.sync()

    # 1. Simulated Buy
    entry_res = broker.submit_entry(
        ticker="TCS",
        shares=10,
        stop_loss=3800.0,
        take_profit=4400.0,
        strategy="MOMENTUM",
        signal_price=4000.0,
    )

    assert entry_res.get("status") == "submitted"
    assert entry_res.get("dry_run") is True
    assert "SIM-ORD-" in entry_res.get("order_id", "")
    assert broker.cash == 460_000.0  # 500,000 - (10 * 4000)
    assert "TCS" in broker.positions
    pos = broker.positions["TCS"]
    assert pos.symbol == "TCS"
    assert pos.qty == 10
    assert pos.avg_entry_price == 4000.0
    assert pos.stop_loss_price == 3800.0

    # 2. Simulated Stop Update
    stop_res = broker.update_stop(ticker="TCS", new_stop=3900.0)
    assert stop_res.get("modified") is True
    assert stop_res.get("dry_run") is True
    assert broker.positions["TCS"].stop_loss_price == 3900.0

    # 3. Simulate Price Movement
    broker.positions["TCS"].current_price = 4200.0

    # 4. Simulated Exit
    exit_res = broker.execute_exit(ticker="TCS", exit_pct=1.0)
    assert exit_res is not None
    assert exit_res.get("dry_run") is True
    assert exit_res.get("exit_price") == 4200.0
    assert exit_res.get("exit_qty") == 10
    assert exit_res.get("pnl") == 2000.0  # (4200 - 4000) * 10
    assert broker.cash == 502_000.0  # 460,000 + (10 * 4200)
    assert "TCS" not in broker.positions
