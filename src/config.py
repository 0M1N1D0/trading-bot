"""Carga y valida config.yaml + .env."""

from __future__ import annotations

import logging
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.models import AlertRule, RuleType, WatchItem

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.yaml"


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _harden_env_file_permissions(env_path: Path) -> None:
    """En un servidor Linux, .env contiene el token de Telegram en texto
    plano. Si el archivo quedó legible por el grupo u otros usuarios
    (permisos por defecto de algunos `scp`/`git clone`/umask), lo
    restringimos a solo lectura/escritura del dueño. No aplica en Windows,
    que usa un modelo de permisos distinto (ACLs)."""
    if _is_windows() or not env_path.exists():
        return
    try:
        current_mode = stat.S_IMODE(env_path.stat().st_mode)
        if current_mode & (stat.S_IRWXG | stat.S_IRWXO):
            env_path.chmod(0o600)
            logger.warning(
                "%s tenía permisos demasiado abiertos (%o); se restringieron a 600 "
                "porque contiene el token de Telegram en texto plano.",
                env_path,
                current_mode,
            )
    except OSError as exc:
        logger.warning("No se pudieron verificar/ajustar permisos de %s: %s", env_path, exc)


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str


@dataclass(frozen=True)
class AppConfig:
    default_interval: str
    market_hours_only: bool
    periodic_report: bool
    watchlist: list[WatchItem]
    telegram: TelegramConfig


class ConfigError(Exception):
    pass


def _parse_rule(raw: dict) -> AlertRule:
    try:
        rule_type = RuleType(raw["type"])
    except ValueError as exc:
        valid = ", ".join(t.value for t in RuleType)
        raise ConfigError(
            f"Tipo de regla desconocido: {raw.get('type')!r}. Válidos: {valid}"
        ) from exc
    try:
        value = float(raw["value"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"Regla sin 'value' numérico válido: {raw}") from exc
    return AlertRule(type=rule_type, value=value)


def _parse_watch_item(raw: dict, default_interval: str) -> WatchItem:
    ticker = raw.get("ticker")
    if not ticker:
        raise ConfigError(f"Entrada de watchlist sin 'ticker': {raw}")
    market = raw.get("market", "US").upper()
    if market not in ("US", "MX"):
        raise ConfigError(f"'market' debe ser US o MX (ticker {ticker}): {market!r}")
    interval = raw.get("interval", default_interval)
    rules = [_parse_rule(r) for r in raw.get("rules", [])]
    return WatchItem(ticker=ticker, market=market, interval=interval, rules=rules)


def load_config(
    config_path: Path | str = DEFAULT_CONFIG_PATH,
    env_path: Path | str | None = None,
) -> AppConfig:
    """Lee config.yaml y .env y devuelve un AppConfig validado.

    Lanza ConfigError con un mensaje claro si algo falta o está mal.
    """
    resolved_env_path = Path(env_path) if env_path else (BASE_DIR / ".env")
    _harden_env_file_permissions(resolved_env_path)
    load_dotenv(dotenv_path=resolved_env_path)

    config_path = Path(config_path)
    if not config_path.exists():
        raise ConfigError(
            f"No se encontró {config_path}. Copia config.yaml de ejemplo o crea uno."
        )

    with open(config_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    default_interval = raw.get("default_interval", "5m")
    market_hours_only = bool(raw.get("market_hours_only", True))
    periodic_report = bool(raw.get("periodic_report", True))

    raw_watchlist = raw.get("watchlist") or []
    if not raw_watchlist:
        raise ConfigError("La watchlist está vacía: agrega al menos una acción en config.yaml")

    watchlist = [_parse_watch_item(item, default_interval) for item in raw_watchlist]

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        raise ConfigError(
            "Faltan TELEGRAM_BOT_TOKEN y/o TELEGRAM_CHAT_ID. "
            "Copia .env.example a .env y llénalos (ver README)."
        )

    return AppConfig(
        default_interval=default_interval,
        market_hours_only=market_hours_only,
        periodic_report=periodic_report,
        watchlist=watchlist,
        telegram=TelegramConfig(bot_token=bot_token, chat_id=chat_id),
    )
