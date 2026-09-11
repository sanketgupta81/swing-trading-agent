"""
tests/test_fyers_broker.py — Unit tests for FyersBroker implementation.
"""

from unittest.mock import MagicMock, patch
import pytest

from config.settings import Settings
from providers.fyers_broker import FyersBroker


@pytest.fixture
def mock_settings():
    return Settings(
        broker_type="fyers",
        fyers_client_id="XC12345-100",
        fyers_secret_key="test_secret",
        fyers_access_token="test_token",
    )


@pytest.fixture
def mock_fyers_client():
    client = MagicMock()
    # Mock funds
    client.funds.return_value = {
        "s": "ok",
        "fund_limit": [
            {"id": 1, "title": "Total Balance", "equityAmount": 150000.0},
            {"id": 3, "title": "Clear Balance", "equityAmount": 100000.0},
            {"id": 10, "title": "Realized P&L", "equityAmount": 1200.0},
        ],
    }
    # Mock holdings
    client.holdings.return_value = {
        "s": "ok",
        "holdings": [
            {
                "symbol": "NSE:RELIANCE-EQ",
                "quantity": 10,
                "costPrice": 2500.0,
                "marketVal": 26000.0,
                "pl": 1000.0,
                "ltp": 2600.0,
            }
        ],
    }
    # Mock positions
    client.positions.return_value = {
        "s": "ok",
        "netPositions": [],
    }
    # Mock orderbook
    client.orderbook.return_value = {
        "s": "ok",
        "orderBook": [],
    }
    # Mock place_order
    client.place_order.return_value = {
        "s": "ok",
        "id": "123456789",
    }
    return client


def test_fyers_broker_sync(mock_settings, mock_fyers_client):
    broker = FyersBroker(mock_settings)

    with patch("providers.fyers_broker.get_fyers_client", return_value=mock_fyers_client):
        result = broker.sync()

        assert result["cash"] == 100000.0
        assert result["portfolio_value"] == 126000.0  # 100000 cash + 26000 holdings
        assert result["position_count"] == 1
        assert "RELIANCE" in broker.positions
        pos = broker.positions["RELIANCE"]
        assert pos.qty == 10
        assert pos.avg_entry_price == 2500.0
        assert pos.current_price == 2600.0


def test_fyers_broker_submit_entry(mock_settings, mock_fyers_client):
    broker = FyersBroker(mock_settings)

    with patch("tools.execution.fyers_orders.get_fyers_client", return_value=mock_fyers_client):
        result = broker.submit_entry(
            ticker="TCS",
            shares=5,
            stop_loss=3800.0,
            take_profit=4200.0,
            strategy="MOMENTUM",
            signal_price=4000.0,
            entry_type="MARKET",
        )

        assert result.get("status") == "submitted"
        assert result.get("order_id") == "123456789"
        assert "TCS" in broker.positions
        pos = broker.positions["TCS"]
        assert pos.symbol == "TCS"
        assert pos.qty == 5
        assert pos.stop_loss_price == 3800.0
        assert result.get("take_profit_price") == 4200.0


def test_fyers_broker_execute_exit(mock_settings, mock_fyers_client):
    broker = FyersBroker(mock_settings)

    # Populate position first
    with patch("providers.fyers_broker.get_fyers_client", return_value=mock_fyers_client):
        broker.sync()

    # Mock order fill
    mock_fyers_client.orderbook.return_value = {
        "s": "ok",
        "orderBook": [
            {
                "id": "123456789",
                "status": 2,  # Filled
                "tradedPrice": 2650.0,
                "filledQty": 10,
            }
        ],
    }

    with patch("tools.execution.fyers_orders.get_fyers_client", return_value=mock_fyers_client):
        result = broker.execute_exit(ticker="RELIANCE", exit_pct=1.0)

        assert result is not None
        assert result.get("exit_price") == 2650.0
        assert result.get("pnl") == 1500.0  # (2650 - 2500) * 10
