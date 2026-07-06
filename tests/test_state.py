import tempfile
from pathlib import Path

import pytest

from src.state import StateStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        s = StateStore(db_path=Path(tmp) / "test_state.db")
        yield s
        s.close()


def test_first_trigger_notifies(store):
    assert store.should_notify("TTWO", "price_above:200", True) is True


def test_repeated_trigger_does_not_renotify(store):
    assert store.should_notify("TTWO", "price_above:200", True) is True
    # Sigue disparada en la siguiente revisión: no se debe repetir la alerta.
    assert store.should_notify("TTWO", "price_above:200", True) is False
    assert store.should_notify("TTWO", "price_above:200", True) is False


def test_rearms_after_condition_clears(store):
    assert store.should_notify("TTWO", "price_above:200", True) is True
    assert store.should_notify("TTWO", "price_above:200", True) is False
    # La condición deja de cumplirse: se rearma (sin notificar el "apagado").
    assert store.should_notify("TTWO", "price_above:200", False) is False
    # Vuelve a cumplirse: debe notificar de nuevo.
    assert store.should_notify("TTWO", "price_above:200", True) is True


def test_never_triggered_never_notifies(store):
    assert store.should_notify("TTWO", "price_above:200", False) is False
    assert store.should_notify("TTWO", "price_above:200", False) is False


def test_rules_are_independent_per_ticker_and_key(store):
    assert store.should_notify("TTWO", "price_above:200", True) is True
    assert store.should_notify("AAPL", "price_above:200", True) is True
    assert store.should_notify("TTWO", "pct_change:3", True) is True
