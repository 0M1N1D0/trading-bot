"""Obtiene cotizaciones de mercado. Usa Yahoo Finance (yfinance) como fuente
gratuita; si en el futuro se cambia de proveedor (Alpha Vantage, Finnhub...),
solo hay que reescribir get_quote manteniendo la misma firma."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import yfinance as yf

from src.models import Quote

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """El proveedor de datos no pudo responder para un ticker."""


def get_history(ticker: str, period: str, interval: str) -> list[float]:
    """Devuelve la serie de precios de cierre de `ticker` para `period`
    (ej. "1mo", "6mo") a intervalos de `interval` (ej. "60m", "1d").

    Usado por src/analysis.py para calcular indicadores técnicos. Lanza
    ProviderError si no se pudo obtener historial (ticker incorrecto, sin
    conexión, o el intervalo pedido no está disponible para ese ticker —
    yfinance limita cuánto historial intradía sirve, y algunos tickers de
    la BMV traen menos datos que los de EE.UU.).
    """
    try:
        hist = yf.Ticker(ticker).history(period=period, interval=interval)
    except Exception as exc:  # yfinance puede lanzar varias excepciones internas
        raise ProviderError(f"Error consultando historial de {ticker}: {exc}") from exc

    if hist is None or hist.empty or "Close" not in hist:
        raise ProviderError(
            f"{ticker}: sin historial disponible para period={period!r} interval={interval!r}"
        )

    closes = [float(c) for c in hist["Close"].dropna().tolist()]
    if not closes:
        raise ProviderError(f"{ticker}: historial sin precios de cierre válidos")

    return closes


def get_quote(ticker: str) -> Quote:
    """Devuelve la cotización actual de `ticker`.

    Lanza ProviderError si no se pudo obtener un precio válido (ticker
    incorrecto, sin conexión, respuesta vacía, etc). El llamador decide
    cómo manejarlo (normalmente: loguear y seguir con el siguiente ticker).
    """
    try:
        info = yf.Ticker(ticker).fast_info
        price = info.get("last_price") if isinstance(info, dict) else info.last_price
        prev_close = (
            info.get("previous_close") if isinstance(info, dict) else info.previous_close
        )
    except Exception as exc:  # yfinance puede lanzar varias excepciones internas
        raise ProviderError(f"Error consultando {ticker}: {exc}") from exc

    if price is None or prev_close is None:
        raise ProviderError(f"{ticker}: respuesta sin precio válido (¿ticker correcto?)")

    return Quote(
        ticker=ticker,
        price=float(price),
        prev_close=float(prev_close),
        timestamp=datetime.now(timezone.utc),
    )
