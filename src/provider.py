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
