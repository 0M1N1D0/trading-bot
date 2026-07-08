"""Persistencia en SQLite de las acciones agregadas dinámicamente (por
Telegram), para que sobrevivan a un reinicio del bot sin tocar config.yaml.

Comparte el mismo archivo state.db que StateStore (src/state.py), pero en
su propia tabla: son responsabilidades distintas (dedup de alertas vs.
watchlist mutable).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.models import AlertRule, RuleType, WatchItem
from src.state import DEFAULT_DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    ticker TEXT PRIMARY KEY,
    market TEXT NOT NULL,
    interval TEXT NOT NULL,
    rules_json TEXT NOT NULL,
    added_at TEXT NOT NULL
);
"""


def _rules_to_json(rules: list[AlertRule]) -> str:
    return json.dumps([{"type": r.type.value, "value": r.value} for r in rules])


def _rules_from_json(raw: str) -> list[AlertRule]:
    return [AlertRule(type=RuleType(r["type"]), value=r["value"]) for r in json.loads(raw)]


class WatchlistStore:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def add(self, item: WatchItem) -> None:
        """Inserta o reemplaza (por ticker) una acción en la watchlist dinámica."""
        self._conn.execute(
            """
            INSERT INTO watchlist (ticker, market, interval, rules_json, added_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                market = excluded.market,
                interval = excluded.interval,
                rules_json = excluded.rules_json,
                added_at = excluded.added_at
            """,
            (
                item.ticker,
                item.market,
                item.interval,
                _rules_to_json(item.rules),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()

    def remove(self, ticker: str) -> bool:
        """Quita `ticker` de la watchlist dinámica. Devuelve True si existía."""
        cur = self._conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
        self._conn.commit()
        return cur.rowcount > 0

    def get(self, ticker: str) -> WatchItem | None:
        cur = self._conn.execute(
            "SELECT ticker, market, interval, rules_json FROM watchlist WHERE ticker = ?",
            (ticker,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        ticker, market, interval, rules_json = row
        return WatchItem(
            ticker=ticker, market=market, interval=interval, rules=_rules_from_json(rules_json)
        )

    def list(self) -> list[WatchItem]:
        """Devuelve todas las acciones agregadas dinámicamente, ordenadas por
        ticker para que la salida de /list_actions sea determinista."""
        cur = self._conn.execute(
            "SELECT ticker, market, interval, rules_json FROM watchlist ORDER BY ticker"
        )
        return [
            WatchItem(ticker=t, market=m, interval=i, rules=_rules_from_json(rj))
            for t, m, i, rj in cur.fetchall()
        ]

    def close(self) -> None:
        self._conn.close()


def merge_watchlist(yaml_items: list[WatchItem], watchlist_store: WatchlistStore) -> list[WatchItem]:
    """Combina la watchlist estática de config.yaml con las acciones
    agregadas dinámicamente (Telegram). Si un mismo ticker aparece en ambos
    lados, gana la definición de config.yaml (fuente de verdad principal).

    Usado tanto al arrancar (src/main.py, para programar los jobs que
    faltan) como por el bot de Telegram (para saber qué hay "vivo" en esta
    sesión sin duplicar la lógica de fusión).
    """
    merged: dict[str, WatchItem] = {item.ticker: item for item in yaml_items}
    for item in watchlist_store.list():
        merged.setdefault(item.ticker, item)
    return list(merged.values())
