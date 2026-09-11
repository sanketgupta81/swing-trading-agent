"""
tools/data/symbols.py — Symbol mapping utilities for Indian and US equity markets.

Normalises tickers between:
- Clean Base Symbol: ``"RELIANCE"``, ``"TCS"``, ``"INFY"``, ``"AAPL"``
- Fyers Trading Symbol: ``"NSE:RELIANCE-EQ"``, ``"NSE:TCS-EQ"``
- Yahoo Finance Symbol: ``"RELIANCE.NS"``, ``"TCS.NS"``, ``"AAPL"``
"""

from __future__ import annotations

import re


def to_base_symbol(symbol: str) -> str:
    """Extract clean base ticker from any exchange-formatted symbol.

    Examples:
        >>> to_base_symbol("NSE:RELIANCE-EQ")
        'RELIANCE'
        >>> to_base_symbol("RELIANCE.NS")
        'RELIANCE'
        >>> to_base_symbol("BSE:TCS-EQ")
        'TCS'
        >>> to_base_symbol("TCS.BO")
        'TCS'
        >>> to_base_symbol("AAPL")
        'AAPL'
        >>> to_base_symbol("BRK.B")
        'BRK.B'
    """
    if not symbol:
        return ""

    s = symbol.strip().upper()

    # Check for Fyers format: EXCHANGE:SYMBOL-SERIES (e.g. NSE:RELIANCE-EQ)
    fyers_match = re.match(r"^(?:NSE|BSE):([A-Z0-9_\-\.]+)(?:-[A-Z0-9]+)?$", s)
    if fyers_match:
        base = fyers_match.group(1)
        if base.endswith("-EQ") or base.endswith("-BE"):
            base = base[:-3]
        return base

    # Check for Yahoo Finance Indian exchange suffix (.NS or .BO)
    if s.endswith(".NS") or s.endswith(".BO"):
        return s[:-3]

    return s


def to_fyers_symbol(symbol: str, exchange: str = "NSE", segment: str = "EQ") -> str:
    """Convert symbol to Fyers API v3 format (e.g. 'NSE:RELIANCE-EQ').

    If already in Fyers format, returns as-is.
    """
    if not symbol:
        return ""

    s = symbol.strip().upper()
    if s.startswith("NSE:") or s.startswith("BSE:"):
        return s

    base = to_base_symbol(s)
    return f"{exchange}:{base}-{segment}"


def to_yf_symbol(symbol: str, default_exchange: str = "NSE") -> str:
    """Convert symbol to Yahoo Finance ticker format.

    For Indian equities, appends .NS (default) or .BO.
    US equities (e.g. AAPL, MSFT) are left unchanged.
    """
    if not symbol:
        return ""

    s = symbol.strip().upper()

    # Already has Yahoo suffix
    if s.endswith(".NS") or s.endswith(".BO") or s.startswith("^"):
        return s

    # If it's a Fyers format
    if s.startswith("BSE:"):
        base = to_base_symbol(s)
        return f"{base}.BO"
    if s.startswith("NSE:"):
        base = to_base_symbol(s)
        return f"{base}.NS"

    # Raw base symbol: determine if Indian or US
    base = to_base_symbol(s)

    # If market is configured as Indian or symbol looks like Indian base symbol
    if default_exchange in ("NSE", "BSE"):
        suffix = ".NS" if default_exchange == "NSE" else ".BO"
        return f"{base}{suffix}"

    return base


def is_indian_symbol(symbol: str) -> bool:
    """Check if the symbol corresponds to the Indian market."""
    s = symbol.strip().upper()
    return (
        s.startswith("NSE:")
        or s.startswith("BSE:")
        or s.endswith(".NS")
        or s.endswith(".BO")
        or s == "^NSEI"
        or s == "^BSESN"
    )
