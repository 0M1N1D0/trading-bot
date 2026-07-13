from src.analysis import DIAS, HORAS, analyze
from src.models import Recommendation, Trend


def _linear_series(start: float, step: float, length: int = 60) -> list[float]:
    return [start + step * i for i in range(length)]


def test_analyze_strong_uptrend_is_alcista_comprar():
    closes = _linear_series(start=100, step=1.0)
    result = analyze(closes, DIAS)
    assert result.trend == Trend.ALCISTA
    assert result.recommendation == Recommendation.COMPRAR
    assert 50.0 <= result.confidence <= 85.0


def test_analyze_strong_downtrend_is_bajista_vender():
    closes = _linear_series(start=200, step=-1.0)
    result = analyze(closes, DIAS)
    assert result.trend == Trend.BAJISTA
    assert result.recommendation == Recommendation.VENDER
    assert 50.0 <= result.confidence <= 85.0


def test_analyze_constant_price_is_lateral_mantener():
    closes = [100.0] * 60
    result = analyze(closes, DIAS)
    assert result.trend == Trend.LATERAL
    assert result.recommendation == Recommendation.MANTENER
    assert 50.0 <= result.confidence <= 85.0


def test_analyze_confidence_never_reaches_100():
    # Ni la tendencia más limpia debe leerse como certeza absoluta.
    closes = _linear_series(start=50, step=2.0, length=90)
    result = analyze(closes, DIAS)
    assert result.confidence < 100.0
    assert result.confidence <= 85.0


def test_analyze_overbought_rsi_adds_caution_note_on_uptrend():
    closes = _linear_series(start=100, step=1.0)
    result = analyze(closes, DIAS)
    assert any("sobrecompra" in note for note in result.notes)
    assert any("Cautela" in note for note in result.notes)


def test_analyze_very_short_series_does_not_crash():
    closes = [100.0, 101.0, 99.5]
    result = analyze(closes, DIAS)
    assert result.trend == Trend.LATERAL
    assert result.recommendation == Recommendation.MANTENER
    assert result.confidence == 50.0
    assert "insuficientes" in result.notes[0].lower()


def test_analyze_insufficient_bars_for_indicators_does_not_crash():
    # Pasa el mínimo de barras (5) pero no alcanza para ningún indicador de
    # "Horas" (SMA20, RSI14, MACD 26+9, momentum10 piden más historial).
    closes = [100.0, 101.0, 99.0, 102.0, 98.0, 103.0]
    result = analyze(closes, HORAS)
    assert result.recommendation == Recommendation.MANTENER
    assert result.confidence == 50.0
    assert "insuficientes" in result.notes[0].lower()


def test_analyze_returns_notes_for_typical_series():
    closes = _linear_series(start=100, step=0.5)
    result = analyze(closes, DIAS)
    assert result.notes
    assert all(isinstance(note, str) and note for note in result.notes)
