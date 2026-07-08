"""Arma un job de APScheduler por cada acción de la watchlist, cada uno con
su propio intervalo, y ejecuta el ciclo: cotizar -> evaluar reglas ->
dedup -> notificar (+ reporte periódico opcional)."""

from __future__ import annotations

import logging
import re

from apscheduler.schedulers.background import BackgroundScheduler

from src import market_hours, provider, rules
from src.config import AppConfig
from src.models import WatchItem
from src.notifier import Notifier
from src.provider import ProviderError
from src.state import StateStore

logger = logging.getLogger(__name__)

_INTERVAL_RE = re.compile(r"^(\d+)\s*([smhd])$", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_interval_seconds(interval: str) -> int:
    """Convierte '5m', '30m', '1h', '1d', '30s' a segundos."""
    match = _INTERVAL_RE.match(interval.strip())
    if not match:
        raise ValueError(
            f"Intervalo inválido: {interval!r}. Usa formato como '5m', '30m', '1h', '1d'."
        )
    amount, unit = match.groups()
    return int(amount) * _UNIT_SECONDS[unit.lower()]


def check_item(
    item: WatchItem,
    config: AppConfig,
    notifier: Notifier,
    state: StateStore,
) -> None:
    """Revisa una sola acción: se ejecuta periódicamente por su propio job."""
    if config.market_hours_only and not market_hours.is_open(item.market):
        logger.debug("%s: mercado %s cerrado, se omite revisión", item.ticker, item.market)
        return

    try:
        quote = provider.get_quote(item.ticker)
    except ProviderError as exc:
        logger.error(str(exc))
        return

    for status in rules.evaluate(item, quote):
        if state.should_notify(item.ticker, status.rule.key(), status.triggered):
            logger.info("Alerta disparada: %s", status.message.replace("\n", " | "))
            notifier.send(status.message)

    if config.periodic_report:
        report = rules.build_report(item, quote)
        logger.info("Reporte: %s", report.replace("\n", " | "))
        notifier.send(report)


def add_watch_job(
    scheduler: BackgroundScheduler,
    item: WatchItem,
    config: AppConfig,
    notifier: Notifier,
    state: StateStore,
) -> None:
    """Programa (o reemplaza) el job de revisión periódica de `item`.

    Se usa tanto al arrancar (una vez por acción de la watchlist) como en
    caliente, cuando se agrega una acción nueva vía Telegram
    (src/telegram_bot.py) sin reiniciar el bot.
    """
    seconds = parse_interval_seconds(item.interval)
    scheduler.add_job(
        check_item,
        "interval",
        seconds=seconds,
        args=[item, config, notifier, state],
        id=f"check_{item.ticker}",
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )
    logger.info("Job programado: %s cada %ds (%s)", item.ticker, seconds, item.interval)


def remove_watch_job(scheduler: BackgroundScheduler, ticker: str) -> bool:
    """Quita el job de revisión de `ticker`, si existe. Devuelve True si lo
    quitó, False si no había ningún job programado para ese ticker."""
    job_id = f"check_{ticker}"
    if scheduler.get_job(job_id) is None:
        return False
    scheduler.remove_job(job_id)
    logger.info("Job removido: %s", ticker)
    return True


def build_scheduler(
    config: AppConfig,
    notifier: Notifier,
    state: StateStore,
) -> BackgroundScheduler:
    """Crea (sin arrancar) un BackgroundScheduler con un job por acción."""
    scheduler = BackgroundScheduler()
    for item in config.watchlist:
        add_watch_job(scheduler, item, config, notifier, state)
    return scheduler
