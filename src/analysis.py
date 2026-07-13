"""Análisis técnico por acción: tendencia, recomendación y confianza.

Módulo puro (sin red, sin estado) — igual que rules.py. Toma una serie de
precios de cierre y calcula un puñado de indicadores técnicos clásicos.

La **dirección** (tendencia alcista/bajista/lateral y la recomendación
comprar/vender/mantener) la deciden 3 indicadores de tendencia — cruce de
medias móviles (SMA), histograma de MACD y momentum — que "votan"
alcista/bajista/neutral y se suman. RSI se trata aparte, como señal de
"cautela" (sobrecompra/sobreventa): no voltea la recomendación por sí solo,
pero resta confianza cuando contradice la tendencia vigente (ej. una racha
alcista con RSI en sobrecompra es más propensa a una corrección).

IMPORTANTE — esto NO es una predicción del mercado. `confidence` es una
medida heurística de qué tanto coinciden los indicadores entre sí (y de
cuántos se pudieron calcular con los datos disponibles), acotada a
[50, 85] a propósito para no aparentar certeza. Ningún indicador técnico
garantiza resultados futuros; ver el disclaimer que agrega
commands.format_analysis en el mensaje final.
"""

from __future__ import annotations

from src.models import Analysis, Recommendation, Trend

HORAS = "Horas"
DIAS = "Días"

# Qué le pide cada horizonte a provider.get_history (period, interval de yfinance).
TIMEFRAME_PARAMS: dict[str, dict[str, str]] = {
    HORAS: {"period": "1mo", "interval": "60m"},
    DIAS: {"period": "6mo", "interval": "1d"},
}

# Ventanas de cada indicador por horizonte.
_WINDOWS: dict[str, dict] = {
    HORAS: {"sma_short": 5, "sma_long": 20, "rsi": 14, "macd": (12, 26, 9), "momentum": 10},
    DIAS: {"sma_short": 10, "sma_long": 30, "rsi": 14, "macd": (12, 26, 9), "momentum": 10},
}

# Los 3 indicadores que deciden dirección: SMA, MACD, momentum. RSI es aparte
# (modificador de confianza, no vota dirección) — ver docstring del módulo.
_TREND_INDICATORS = 3
_MIN_BARS = 5
_MOMENTUM_THRESHOLD_PCT = 0.5
_RSI_OVERSOLD = 30
_RSI_OVERBOUGHT = 70
_RSI_CAUTION_PENALTY = 10.0


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def _ema_series(values: list[float], period: int) -> list[float] | None:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema = [sum(values[:period]) / period]  # semilla: SMA del primer tramo
    for price in values[period:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema


def _rsi(values: list[float], period: int = 14) -> float | None:
    """RSI de Wilder. None si no hay suficiente historial."""
    if len(values) <= period:
        return None
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _macd_histogram(values: list[float], fast: int, slow: int, signal: int) -> float | None:
    if len(values) < slow + signal:
        return None
    ema_fast = _ema_series(values, fast)
    ema_slow = _ema_series(values, slow)
    if ema_fast is None or ema_slow is None:
        return None

    # ema_fast es más largo que ema_slow (arranca antes); se alinean por la cola.
    offset = len(ema_fast) - len(ema_slow)
    macd_line = [ema_fast[offset + i] - ema_slow[i] for i in range(len(ema_slow))]
    if len(macd_line) < signal:
        return None

    signal_line = _ema_series(macd_line, signal)
    if signal_line is None:
        return None
    return macd_line[-1] - signal_line[-1]


def _momentum(values: list[float], period: int) -> float | None:
    """Rate of change en % contra el precio de hace `period` barras."""
    if len(values) <= period:
        return None
    base = values[-1 - period]
    if not base:
        return None
    return (values[-1] - base) / base * 100


def _volatility(values: list[float], window: int = 20) -> float | None:
    """Desviación estándar de los rendimientos recientes, en %. Solo
    informativo (no vota tendencia): sirve para que el mensaje avise cuando
    el precio se está moviendo mucho, sin que eso decida comprar/vender."""
    tail = values[-window:] if len(values) > window else values
    if len(tail) < 2:
        return None
    returns = [
        (tail[i] - tail[i - 1]) / tail[i - 1] for i in range(1, len(tail)) if tail[i - 1]
    ]
    if not returns:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    return (variance**0.5) * 100


def _insufficient_data(timeframe: str, note: str) -> Analysis:
    return Analysis(
        timeframe=timeframe,
        trend=Trend.LATERAL,
        recommendation=Recommendation.MANTENER,
        confidence=50.0,
        notes=[note],
    )


def analyze(closes: list[float], timeframe: str) -> Analysis:
    """Analiza una serie de precios de cierre (ordenada de más antiguo a
    más reciente) y devuelve tendencia, recomendación y confianza para
    `timeframe` ("Horas" o "Días", ver TIMEFRAME_PARAMS)."""
    if len(closes) < _MIN_BARS:
        return _insufficient_data(timeframe, "Datos insuficientes para un análisis confiable")

    windows = _WINDOWS.get(timeframe, _WINDOWS[DIAS])
    last_price = closes[-1]
    # Umbral relativo al precio para no confundir ruido de punto flotante
    # (una serie perfectamente lineal da un histograma MACD ~1e-15, no 0
    # exacto) con una señal real, sin dejar de detectar movimientos genuinos.
    zero_eps = max(abs(last_price) * 1e-9, 1e-9)

    votes: list[int] = []
    notes: list[str] = []

    sma_short = _sma(closes, windows["sma_short"])
    sma_long = _sma(closes, windows["sma_long"])
    if sma_short is not None and sma_long is not None:
        if sma_short > sma_long:
            votes.append(1)
            notes.append(f"SMA{windows['sma_short']}>SMA{windows['sma_long']} (alcista)")
        elif sma_short < sma_long:
            votes.append(-1)
            notes.append(f"SMA{windows['sma_short']}<SMA{windows['sma_long']} (bajista)")
        else:
            votes.append(0)
            notes.append(f"SMA{windows['sma_short']}=SMA{windows['sma_long']} (plano)")

    fast, slow, signal = windows["macd"]
    macd_hist = _macd_histogram(closes, fast, slow, signal)
    if macd_hist is not None:
        if macd_hist > zero_eps:
            votes.append(1)
            notes.append(f"MACD histograma +{macd_hist:.2f} (alcista)")
        elif macd_hist < -zero_eps:
            votes.append(-1)
            notes.append(f"MACD histograma {macd_hist:.2f} (bajista)")
        else:
            votes.append(0)
            notes.append("MACD histograma en cero (sin cambio de momentum)")

    momentum = _momentum(closes, windows["momentum"])
    if momentum is not None:
        if momentum > _MOMENTUM_THRESHOLD_PCT:
            votes.append(1)
            notes.append(f"Momentum +{momentum:.2f}%")
        elif momentum < -_MOMENTUM_THRESHOLD_PCT:
            votes.append(-1)
            notes.append(f"Momentum {momentum:.2f}%")
        else:
            votes.append(0)
            notes.append(f"Momentum {momentum:+.2f}% (plano)")

    if not votes:
        return _insufficient_data(timeframe, "Datos insuficientes para calcular indicadores")

    net = sum(votes)
    if net > 0:
        trend = Trend.ALCISTA
    elif net < 0:
        trend = Trend.BAJISTA
    else:
        trend = Trend.LATERAL

    if net >= 2:
        recommendation = Recommendation.COMPRAR
    elif net <= -2:
        recommendation = Recommendation.VENDER
    else:
        recommendation = Recommendation.MANTENER

    # Confianza = qué tan de acuerdo están los 3 indicadores de tendencia con
    # la dirección neta, sobre un denominador fijo (no solo los que sí se
    # pudieron calcular) — así, menos indicadores disponibles también baja
    # la confianza, no solo el desacuerdo entre ellos.
    if net == 0:
        agreement = sum(1 for v in votes if v == 0)
    else:
        sign = 1 if net > 0 else -1
        agreement = sum(1 for v in votes if v == sign)
    confidence = 50.0 + (agreement / _TREND_INDICATORS) * 35.0

    # RSI: señal de cautela aparte, no vota dirección. Sobrecompra en una
    # racha alcista (o sobreventa en una bajista) es un riesgo de corrección
    # clásico, así que resta confianza en vez de invertir la recomendación.
    rsi = _rsi(closes, windows["rsi"])
    if rsi is not None:
        if rsi >= _RSI_OVERBOUGHT:
            notes.append(f"RSI {rsi:.0f} (sobrecompra)")
            if trend == Trend.ALCISTA:
                confidence -= _RSI_CAUTION_PENALTY
                notes.append("Cautela: posible corrección por sobrecompra")
        elif rsi <= _RSI_OVERSOLD:
            notes.append(f"RSI {rsi:.0f} (sobreventa)")
            if trend == Trend.BAJISTA:
                confidence -= _RSI_CAUTION_PENALTY
                notes.append("Cautela: posible rebote por sobreventa")
        else:
            notes.append(f"RSI {rsi:.0f} (neutral)")

    volatility = _volatility(closes)
    if volatility is not None:
        notes.append(f"Volatilidad {volatility:.2f}%")

    confidence = max(50.0, min(85.0, confidence))

    return Analysis(
        timeframe=timeframe,
        trend=trend,
        recommendation=recommendation,
        confidence=round(confidence, 1),
        notes=notes,
    )
