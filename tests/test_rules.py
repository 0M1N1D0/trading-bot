from datetime import datetime, timezone

from src.models import AlertRule, Quote, RuleType, WatchItem
from src.rules import build_report, evaluate


def make_quote(price: float, prev_close: float) -> Quote:
    return Quote(ticker="TTWO", price=price, prev_close=prev_close, timestamp=datetime.now(timezone.utc))


def test_price_above_triggers_when_price_exceeds_value():
    item = WatchItem(
        ticker="TTWO", market="US", interval="5m",
        rules=[AlertRule(RuleType.PRICE_ABOVE, 200)],
    )
    quote = make_quote(price=210, prev_close=200)
    statuses = evaluate(item, quote)
    assert len(statuses) == 1
    assert statuses[0].triggered is True
    assert "TTWO" in statuses[0].message


def test_price_above_does_not_trigger_when_below_value():
    item = WatchItem(
        ticker="TTWO", market="US", interval="5m",
        rules=[AlertRule(RuleType.PRICE_ABOVE, 200)],
    )
    quote = make_quote(price=190, prev_close=200)
    statuses = evaluate(item, quote)
    assert statuses[0].triggered is False
    assert statuses[0].message == ""


def test_price_below_triggers_when_price_under_value():
    item = WatchItem(
        ticker="TTWO", market="US", interval="5m",
        rules=[AlertRule(RuleType.PRICE_BELOW, 150)],
    )
    quote = make_quote(price=140, prev_close=200)
    statuses = evaluate(item, quote)
    assert statuses[0].triggered is True


def test_pct_change_triggers_on_positive_and_negative_swing():
    item = WatchItem(
        ticker="TTWO", market="US", interval="5m",
        rules=[AlertRule(RuleType.PCT_CHANGE, 3)],
    )
    # +5% respecto al cierre previo
    up = evaluate(item, make_quote(price=105, prev_close=100))
    assert up[0].triggered is True

    # -5% respecto al cierre previo
    down = evaluate(item, make_quote(price=95, prev_close=100))
    assert down[0].triggered is True

    # dentro del umbral, no dispara
    flat = evaluate(item, make_quote(price=101, prev_close=100))
    assert flat[0].triggered is False


def test_build_report_includes_price_and_pct_change():
    item = WatchItem(ticker="TTWO", market="US", interval="5m", rules=[])
    quote = make_quote(price=105, prev_close=100)
    report = build_report(item, quote)
    assert "TTWO" in report
    assert "105" in report
    assert "+5.00%" in report
