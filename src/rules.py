"""Evalúa las reglas de alerta de una acción contra su cotización actual."""

from __future__ import annotations

from dataclasses import dataclass

from src.models import AlertRule, Quote, RuleType, WatchItem


@dataclass(frozen=True)
class RuleStatus:
    """Estado de una regla en esta revisión. `triggered` indica si la
    condición se cumple ahora mismo (sin importar si ya se notificó antes;
    eso lo decide state.py). `message` solo es útil cuando triggered=True."""

    rule: AlertRule
    triggered: bool
    message: str


def _rule_message(item: WatchItem, rule_type: RuleType, value: float, quote: Quote) -> str:
    if rule_type == RuleType.PRICE_ABOVE:
        return (
            f"🔼 *{item.ticker}* superó ${value:,.2f}\n"
            f"Precio actual: ${quote.price:,.2f}"
        )
    if rule_type == RuleType.PRICE_BELOW:
        return (
            f"🔽 *{item.ticker}* cayó por debajo de ${value:,.2f}\n"
            f"Precio actual: ${quote.price:,.2f}"
        )
    if rule_type == RuleType.PCT_CHANGE:
        sign = "+" if quote.pct_change >= 0 else ""
        return (
            f"⚡ *{item.ticker}* cambió {sign}{quote.pct_change:.2f}% "
            f"(umbral ±{value:.2f}%)\n"
            f"Precio actual: ${quote.price:,.2f} (cierre previo ${quote.prev_close:,.2f})"
        )
    raise ValueError(f"Tipo de regla no soportado: {rule_type}")  # pragma: no cover


def _rule_triggered(rule_type: RuleType, value: float, quote: Quote) -> bool:
    if rule_type == RuleType.PRICE_ABOVE:
        return quote.price > value
    if rule_type == RuleType.PRICE_BELOW:
        return quote.price < value
    if rule_type == RuleType.PCT_CHANGE:
        return abs(quote.pct_change) >= value
    raise ValueError(f"Tipo de regla no soportado: {rule_type}")  # pragma: no cover


def evaluate(item: WatchItem, quote: Quote) -> list[RuleStatus]:
    """Evalúa TODAS las reglas de `item` contra `quote` (no solo las
    disparadas). Es una función pura: no manda nada ni consulta estado.
    El llamador (scheduler.py) usa state.py para decidir si, dado el
    estado previo, corresponde notificar o rearmar cada regla."""
    statuses = []
    for rule in item.rules:
        triggered = _rule_triggered(rule.type, rule.value, quote)
        message = _rule_message(item, rule.type, rule.value, quote) if triggered else ""
        statuses.append(RuleStatus(rule=rule, triggered=triggered, message=message))
    return statuses


def build_report(item: WatchItem, quote: Quote) -> str:
    """Mensaje de reporte periódico (no depende de ninguna regla)."""
    sign = "+" if quote.pct_change >= 0 else ""
    return (
        f"📊 *{item.ticker}*: ${quote.price:,.2f} "
        f"({sign}{quote.pct_change:.2f}% vs cierre previo)"
    )
