import pytest

from src.commands import format_quote, format_watchlist, parse_add_args
from src.models import AlertRule, Quote, RuleType, WatchItem


def test_parse_add_args_ticker_only_uses_defaults():
    item = parse_add_args(["ttwo"], default_interval="5m")
    assert item.ticker == "TTWO"
    assert item.market == "US"
    assert item.interval == "5m"
    assert item.rules == []


def test_parse_add_args_infers_mx_market_from_suffix():
    item = parse_add_args(["amxb.mx"], default_interval="5m")
    assert item.ticker == "AMXB.MX"
    assert item.market == "MX"


def test_parse_add_args_market_override():
    item = parse_add_args(["AAPL", "market=mx"], default_interval="5m")
    assert item.market == "MX"


def test_parse_add_args_rejects_invalid_market():
    with pytest.raises(ValueError):
        parse_add_args(["AAPL", "market=EU"], default_interval="5m")


def test_parse_add_args_with_rules():
    item = parse_add_args(
        ["TTWO", "price_above=260", "price_below=230", "pct_change=3"],
        default_interval="5m",
    )
    assert item.rules == [
        AlertRule(type=RuleType.PRICE_ABOVE, value=260.0),
        AlertRule(type=RuleType.PRICE_BELOW, value=230.0),
        AlertRule(type=RuleType.PCT_CHANGE, value=3.0),
    ]


def test_parse_add_args_with_custom_interval():
    item = parse_add_args(["AMXB.MX", "interval=30m"], default_interval="5m")
    assert item.interval == "30m"


def test_parse_add_args_rejects_invalid_interval():
    with pytest.raises(ValueError):
        parse_add_args(["AAPL", "interval=5 minutes"], default_interval="5m")


def test_parse_add_args_rejects_non_numeric_rule_value():
    with pytest.raises(ValueError):
        parse_add_args(["AAPL", "price_above=abc"], default_interval="5m")


def test_parse_add_args_rejects_unknown_key():
    with pytest.raises(ValueError):
        parse_add_args(["AAPL", "bogus=1"], default_interval="5m")


def test_parse_add_args_rejects_malformed_argument():
    with pytest.raises(ValueError):
        parse_add_args(["AAPL", "price_above"], default_interval="5m")


def test_parse_add_args_requires_ticker():
    with pytest.raises(ValueError):
        parse_add_args([], default_interval="5m")


def test_format_watchlist_empty():
    assert "vacía" in format_watchlist([])


def test_format_watchlist_lists_items_with_and_without_rules():
    items = [
        WatchItem(ticker="TTWO", market="US", interval="5m", rules=[AlertRule(RuleType.PRICE_ABOVE, 260)]),
        WatchItem(ticker="AAPL", market="US", interval="5m", rules=[]),
    ]
    text = format_watchlist(items)
    assert "TTWO" in text
    assert "price_above=260" in text
    assert "AAPL" in text
    assert "sin reglas" in text


def test_format_quote_includes_ticker_and_price():
    from datetime import datetime, timezone

    item = WatchItem(ticker="AAPL", market="US", interval="5m")
    quote = Quote(ticker="AAPL", price=150.0, prev_close=145.0, timestamp=datetime.now(timezone.utc))
    text = format_quote(item, quote)
    assert "AAPL" in text
    assert "150.00" in text
