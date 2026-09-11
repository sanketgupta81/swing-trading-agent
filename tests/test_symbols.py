"""
tests/test_symbols.py — Unit tests for Indian and US symbol normalization.
"""

from tools.data.symbols import (
    is_indian_symbol,
    to_base_symbol,
    to_fyers_symbol,
    to_yf_symbol,
)


def test_to_base_symbol():
    assert to_base_symbol("NSE:RELIANCE-EQ") == "RELIANCE"
    assert to_base_symbol("BSE:TCS-EQ") == "TCS"
    assert to_base_symbol("NSE:INFY-BE") == "INFY"
    assert to_base_symbol("RELIANCE.NS") == "RELIANCE"
    assert to_base_symbol("TCS.BO") == "TCS"
    assert to_base_symbol("AAPL") == "AAPL"
    assert to_base_symbol("BRK.B") == "BRK.B"
    assert to_base_symbol("") == ""


def test_to_fyers_symbol():
    assert to_fyers_symbol("RELIANCE") == "NSE:RELIANCE-EQ"
    assert to_fyers_symbol("RELIANCE.NS") == "NSE:RELIANCE-EQ"
    assert to_fyers_symbol("NSE:RELIANCE-EQ") == "NSE:RELIANCE-EQ"
    assert to_fyers_symbol("TCS", exchange="BSE") == "BSE:TCS-EQ"
    assert to_fyers_symbol("") == ""


def test_to_yf_symbol():
    assert to_yf_symbol("RELIANCE", default_exchange="NSE") == "RELIANCE.NS"
    assert to_yf_symbol("NSE:RELIANCE-EQ") == "RELIANCE.NS"
    assert to_yf_symbol("BSE:TCS-EQ") == "TCS.BO"
    assert to_yf_symbol("TCS.NS") == "TCS.NS"
    assert to_yf_symbol("AAPL", default_exchange="") == "AAPL"
    assert to_yf_symbol("^NSEI") == "^NSEI"


def test_is_indian_symbol():
    assert is_indian_symbol("NSE:RELIANCE-EQ") is True
    assert is_indian_symbol("RELIANCE.NS") is True
    assert is_indian_symbol("TCS.BO") is True
    assert is_indian_symbol("^NSEI") is True
    assert is_indian_symbol("AAPL") is False
    assert is_indian_symbol("MSFT") is False
