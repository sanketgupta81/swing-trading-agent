"""
tools/execution/market_calendar.py — Market calendar utilities for Indian (NSE) and US (Alpaca) markets.

Provides checks for whether the market is open today,
used by schedulers to skip cycles on weekends and holidays.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
import pytz

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NSE (India) Trading Holidays (2025 - 2027)
# ---------------------------------------------------------------------------
_NSE_HOLIDAYS = {
    # 2025
    date(2025, 1, 26),  # Republic Day (Sunday)
    date(2025, 2, 26),  # Mahashivratri
    date(2025, 3, 14),  # Holi
    date(2025, 3, 31),  # Id-Ul-Fitr
    date(2025, 4, 10),  # Shri Mahavir Jayanti
    date(2025, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 1),   # Maharashtra Day
    date(2025, 6, 7),   # Bakri Id
    date(2025, 7, 6),   # Muharram
    date(2025, 8, 15),  # Independence Day
    date(2025, 8, 27),  # Ganesh Chaturthi
    date(2025, 10, 2),  # Mahatma Gandhi Jayanti / Dussehra
    date(2025, 10, 21), # Diwali Laxmi Pujan (Regular closed, Muhurat in evening)
    date(2025, 10, 22), # Diwali Balipratipada
    date(2025, 11, 5),  # Prakash Gurpurb Sri Guru Nanak Dev
    date(2025, 12, 25), # Christmas

    # 2026
    date(2026, 1, 26),  # Republic Day
    date(2026, 3, 3),   # Holi
    date(2026, 3, 20),  # Id-Ul-Fitr
    date(2026, 4, 3),   # Good Friday
    date(2026, 4, 14),  # Ambedkar Jayanti
    date(2026, 5, 1),   # Maharashtra Day
    date(2026, 5, 27),  # Bakri Id
    date(2026, 8, 15),  # Independence Day
    date(2026, 10, 2),  # Gandhi Jayanti
    date(2026, 10, 20), # Dussehra
    date(2026, 11, 8),  # Diwali Laxmi Pujan
    date(2026, 11, 24), # Guru Nanak Jayanti
    date(2026, 12, 25), # Christmas

    # 2027
    date(2027, 1, 26),  # Republic Day
    date(2027, 3, 22),  # Holi
    date(2027, 3, 26),  # Good Friday
    date(2027, 4, 14),  # Ambedkar Jayanti
    date(2027, 5, 1),   # Maharashtra Day
    date(2027, 8, 15),  # Independence Day
    date(2027, 10, 2),  # Gandhi Jayanti
    date(2027, 12, 25), # Christmas
}


def is_indian_market_open_today(check_date: date | None = None) -> bool:
    """Check if the Indian stock market (NSE) is open on the given date.

    Args:
        check_date: Date to check (defaults to today in Asia/Kolkata).

    Returns:
        True if regular trading occurs, False on weekends and holidays.
    """
    if check_date is None:
        kolkata_tz = pytz.timezone("Asia/Kolkata")
        check_date = datetime.now(kolkata_tz).date()

    # Weekend check: Monday is 0, Sunday is 6
    if check_date.weekday() >= 5:
        logger.info("NSE closed on weekend (%s)", check_date.isoformat())
        return False

    # Holiday check
    if check_date in _NSE_HOLIDAYS:
        logger.info("NSE closed for trading holiday on %s", check_date.isoformat())
        return False

    return True


def is_us_market_open_today() -> bool:
    """Check if the US stock market is open today using Alpaca's clock API."""
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetCalendarRequest
        from config.settings import get_settings

        s = get_settings()
        if not s.alpaca_api_key:
            return True

        client = TradingClient(
            api_key=s.alpaca_api_key,
            secret_key=s.alpaca_secret_key,
            paper=s.alpaca_paper,
        )
        clock = client.get_clock()

        if clock.is_open:
            return True

        now_et = datetime.now(clock.next_open.tzinfo)
        today = now_et.date()
        next_open_date = clock.next_open.date()

        if next_open_date == today:
            return True

        cal = client.get_calendar(GetCalendarRequest(start=today, end=today))
        if cal and cal[0].date == today:
            return True

        logger.info(
            "US market closed today (%s). Next open: %s.",
            today.isoformat(), clock.next_open.isoformat(),
        )
        return False

    except Exception as exc:
        logger.warning("US market calendar check failed (%s) — assuming open.", exc)
        return True


def is_market_open_today() -> bool:
    """General market calendar check based on settings (broker_type / market_country)."""
    from config.settings import get_settings
    s = get_settings()

    broker = getattr(s, "broker_type", "fyers").lower()
    country = getattr(s, "market_country", "IN").upper()

    if broker == "fyers" or country == "IN":
        return is_indian_market_open_today()

    return is_us_market_open_today()
