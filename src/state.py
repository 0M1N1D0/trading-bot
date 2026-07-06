"""Persistencia en SQLite para evitar mandar la misma alerta en cada revisión.

Una regla se considera "activa" desde que se dispara hasta que deja de
cumplirse (histéresis): solo se notifica en la transición falso -> verdadero.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "state.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS active_alerts (
    ticker TEXT NOT NULL,
    rule_key TEXT NOT NULL,
    PRIMARY KEY (ticker, rule_key)
);
"""


class StateStore:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def is_active(self, ticker: str, rule_key: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM active_alerts WHERE ticker = ? AND rule_key = ?",
            (ticker, rule_key),
        )
        return cur.fetchone() is not None

    def mark_active(self, ticker: str, rule_key: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO active_alerts (ticker, rule_key) VALUES (?, ?)",
            (ticker, rule_key),
        )
        self._conn.commit()

    def clear(self, ticker: str, rule_key: str) -> None:
        self._conn.execute(
            "DELETE FROM active_alerts WHERE ticker = ? AND rule_key = ?",
            (ticker, rule_key),
        )
        self._conn.commit()

    def should_notify(self, ticker: str, rule_key: str, triggered: bool) -> bool:
        """Decide si hay que notificar esta regla ahora mismo, aplicando
        histéresis: solo True en la transición inactiva -> disparada."""
        currently_active = self.is_active(ticker, rule_key)
        if triggered and not currently_active:
            self.mark_active(ticker, rule_key)
            return True
        if not triggered and currently_active:
            self.clear(ticker, rule_key)
        return False

    def close(self) -> None:
        self._conn.close()
