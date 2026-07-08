"""Parseo y formato para los comandos de Telegram que gestionan la
watchlist en caliente (/add_action, /list_actions, /status...).

Funciones puras (sin red ni I/O) para que sean fáciles de testear;
src/telegram_bot.py se encarga de la parte async y de hablar con
Telegram/el provider/la persistencia.
"""

from __future__ import annotations

from src.models import AlertRule, Quote, RuleType, WatchItem
from src.scheduler import parse_interval_seconds

# Alias cortos aceptados en el comando, además del nombre completo del RuleType.
_RULE_ALIASES = {
    "price_above": RuleType.PRICE_ABOVE,
    "price_below": RuleType.PRICE_BELOW,
    "pct_change": RuleType.PCT_CHANGE,
}


def _infer_market(ticker: str) -> str:
    return "MX" if ticker.upper().endswith(".MX") else "US"


def parse_add_args(args: list[str], default_interval: str) -> WatchItem:
    """Convierte los argumentos de /add_action en un WatchItem.

    Formato: TICKER [market=US|MX] [interval=5m] [price_above=N] [price_below=N] [pct_change=N]
    Ejemplos:
        AAPL
        TTWO price_above=260 pct_change=3
        AMXB.MX interval=30m pct_change=2

    Lanza ValueError con un mensaje apto para mostrar tal cual en el chat.
    """
    if not args:
        raise ValueError(
            "Falta el ticker. Uso: /add_action TICKER [market=US|MX] [interval=5m] "
            "[price_above=N] [price_below=N] [pct_change=N]"
        )

    ticker = args[0].strip().upper()
    if not ticker:
        raise ValueError("El ticker no puede estar vacío.")

    market = _infer_market(ticker)
    interval = default_interval
    rules: list[AlertRule] = []

    for raw_arg in args[1:]:
        if "=" not in raw_arg:
            raise ValueError(
                f"Argumento inválido: {raw_arg!r}. Usa la forma clave=valor "
                "(ej. price_above=260)."
            )
        key, _, value = raw_arg.partition("=")
        key = key.strip().lower()
        value = value.strip()

        if key == "market":
            if value.upper() not in ("US", "MX"):
                raise ValueError(f"'market' debe ser US o MX, recibí: {value!r}")
            market = value.upper()
        elif key == "interval":
            try:
                parse_interval_seconds(value)
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
            interval = value
        elif key in _RULE_ALIASES:
            try:
                numeric_value = float(value)
            except ValueError as exc:
                raise ValueError(f"'{key}' debe ser numérico, recibí: {value!r}") from exc
            rules.append(AlertRule(type=_RULE_ALIASES[key], value=numeric_value))
        else:
            valid_keys = ", ".join(["market", "interval", *_RULE_ALIASES])
            raise ValueError(f"Argumento desconocido: {key!r}. Válidos: {valid_keys}")

    return WatchItem(ticker=ticker, market=market, interval=interval, rules=rules)


def format_watchlist(items: list[WatchItem]) -> str:
    """Mensaje Markdown con la watchlist actual (usado por /list_actions)."""
    if not items:
        return "📋 La watchlist está vacía."

    lines = ["📋 *Watchlist actual:*"]
    for item in items:
        if item.rules:
            rules_desc = ", ".join(f"{r.type.value}={r.value:g}" for r in item.rules)
        else:
            rules_desc = "sin reglas (solo seguimiento)"
        lines.append(f"• *{item.ticker}* ({item.market}, cada {item.interval}) — {rules_desc}")
    return "\n".join(lines)


def format_quote(item: WatchItem, quote: Quote) -> str:
    """Mensaje Markdown con la cotización actual de una acción (usado por
    /add_action y /status)."""
    sign = "+" if quote.pct_change >= 0 else ""
    return (
        f"*{item.ticker}*: ${quote.price:,.2f} "
        f"({sign}{quote.pct_change:.2f}% vs cierre previo ${quote.prev_close:,.2f})"
    )
