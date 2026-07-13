import pytest

from src.commands import format_analysis, format_quote, format_watchlist, parse_add_args
from src.models import AlertRule, Analysis, Quote, Recommendation, RuleType, Trend, WatchItem


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
    assert "price\\_above=260" in text
    assert "AAPL" in text
    assert "sin reglas" in text


def test_format_watchlist_escapes_underscores_in_rule_names():
    # Con las 3 reglas (price_above, price_below, pct_change) hay un número
    # impar de "_" en el texto sin escapar, lo que rompe el parseo de
    # Markdown de Telegram ("Can't parse entities"). Ver commands.py.
    items = [
        WatchItem(
            ticker="TTWO",
            market="US",
            interval="5m",
            rules=[
                AlertRule(RuleType.PRICE_ABOVE, 260),
                AlertRule(RuleType.PRICE_BELOW, 230),
                AlertRule(RuleType.PCT_CHANGE, 3),
            ],
        )
    ]
    text = format_watchlist(items)
    # Cada tipo de regla trae exactamente un "_" (price_above, price_below,
    # pct_change); las 3 reglas deben quedar escapadas como "\_".
    assert text.count("\\_") == 3
    assert "price\\_above" in text
    assert "price\\_below" in text
    assert "pct\\_change" in text


def test_format_quote_includes_ticker_and_price():
    from datetime import datetime, timezone

    item = WatchItem(ticker="AAPL", market="US", interval="5m")
    quote = Quote(ticker="AAPL", price=150.0, prev_close=145.0, timestamp=datetime.now(timezone.utc))
    text = format_quote(item, quote)
    assert "AAPL" in text
    assert "150.00" in text


def test_format_analysis_includes_both_timeframes_and_disclaimer():
    analyses = [
        Analysis(
            timeframe="Horas",
            trend=Trend.ALCISTA,
            recommendation=Recommendation.COMPRAR,
            confidence=73.3,
            notes=["SMA5>SMA20 (alcista)", "RSI 55 (neutral)"],
        ),
        Analysis(
            timeframe="Días",
            trend=Trend.LATERAL,
            recommendation=Recommendation.MANTENER,
            confidence=50.0,
            notes=["Datos insuficientes para calcular indicadores"],
        ),
    ]
    text = format_analysis("TTWO", analyses)
    assert "TTWO" in text
    assert "Horas" in text
    assert "Días" in text
    assert "COMPRAR" in text
    assert "MANTENER" in text
    assert "73%" in text
    assert "no es asesoría financiera" in text


def test_format_analysis_escapes_underscores_in_notes():
    analyses = [
        Analysis(
            timeframe="Días",
            trend=Trend.BAJISTA,
            recommendation=Recommendation.VENDER,
            confidence=60.0,
            notes=["SMA10<SMA30 (bajista)", "pct_change algo"],
        )
    ]
    text = format_analysis("TTWO", analyses)
    assert "pct\\_change" in text


def test_format_analysis_reports_errors_without_crashing_when_no_data():
    text = format_analysis("BOGUS", [], errors=["Horas: BOGUS: sin historial disponible"])
    assert "BOGUS" in text
    assert "sin historial" in text
