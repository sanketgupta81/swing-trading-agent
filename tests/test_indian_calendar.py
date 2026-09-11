"""
tests/test_indian_calendar.py — Unit tests for Indian market calendar.
"""

from datetime import date
from tools.execution.market_calendar import is_indian_market_open_today


def test_regular_weekday():
    # 2026-09-09 is a Wednesday and not an NSE holiday
    wednesday = date(2026, 9, 9)
    assert is_indian_market_open_today(wednesday) is True


def test_weekend():
    # 2026-09-12 is Saturday, 2026-09-13 is Sunday
    saturday = date(2026, 9, 12)
    sunday = date(2026, 9, 13)
    assert is_indian_market_open_today(saturday) is False
    assert is_indian_market_open_today(sunday) is False


def test_nse_holiday():
    # 2026-01-26 is Republic Day (Monday)
    republic_day = date(2026, 1, 26)
    assert is_indian_market_open_today(republic_day) is False

    # 2026-12-25 is Christmas (Friday)
    christmas = date(2026, 12, 25)
    assert is_indian_market_open_today(christmas) is False
