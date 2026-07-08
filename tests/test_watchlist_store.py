import tempfile
from pathlib import Path

import pytest

from src.models import AlertRule, RuleType, WatchItem
from src.watchlist_store import WatchlistStore, merge_watchlist


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        s = WatchlistStore(db_path=Path(tmp) / "test_watchlist.db")
        yield s
        s.close()


def test_add_and_get_roundtrip(store):
    item = WatchItem(
        ticker="TTWO",
        market="US",
        interval="15m",
        rules=[AlertRule(RuleType.PRICE_ABOVE, 260.0), AlertRule(RuleType.PCT_CHANGE, 3.0)],
    )
    store.add(item)
    fetched = store.get("TTWO")
    assert fetched == item


def test_get_missing_returns_none(store):
    assert store.get("NOPE") is None


def test_add_without_rules(store):
    item = WatchItem(ticker="AAPL", market="US", interval="5m", rules=[])
    store.add(item)
    assert store.get("AAPL") == item


def test_add_is_upsert_by_ticker(store):
    store.add(WatchItem(ticker="AAPL", market="US", interval="5m", rules=[]))
    updated = WatchItem(
        ticker="AAPL", market="US", interval="30m", rules=[AlertRule(RuleType.PRICE_BELOW, 100.0)]
    )
    store.add(updated)
    assert store.get("AAPL") == updated
    assert len(store.list()) == 1


def test_remove_existing_returns_true(store):
    store.add(WatchItem(ticker="AAPL", market="US", interval="5m", rules=[]))
    assert store.remove("AAPL") is True
    assert store.get("AAPL") is None


def test_remove_missing_returns_false(store):
    assert store.remove("NOPE") is False


def test_list_is_sorted_by_ticker(store):
    store.add(WatchItem(ticker="TTWO", market="US", interval="5m", rules=[]))
    store.add(WatchItem(ticker="AAPL", market="US", interval="5m", rules=[]))
    tickers = [item.ticker for item in store.list()]
    assert tickers == ["AAPL", "TTWO"]


def test_merge_watchlist_yaml_wins_on_conflict(store):
    yaml_items = [WatchItem(ticker="TTWO", market="US", interval="5m", rules=[])]
    store.add(WatchItem(ticker="TTWO", market="US", interval="30m", rules=[]))
    store.add(WatchItem(ticker="AAPL", market="US", interval="15m", rules=[]))

    merged = merge_watchlist(yaml_items, store)
    by_ticker = {item.ticker: item for item in merged}

    assert by_ticker["TTWO"].interval == "5m"  # gana config.yaml
    assert by_ticker["AAPL"].interval == "15m"  # viene de la dinámica
    assert len(merged) == 2
