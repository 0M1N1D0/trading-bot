"""Prueba manual: corre el análisis técnico de uno o más tickers contra
datos reales de yfinance, sin pasar por Telegram.

Uso:
    python scripts/check_analysis.py [TICKER ...]

Si no se pasan tickers, usa TTWO y AMXB.MX como ejemplo.
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src import analysis, provider  # noqa: E402
from src.commands import format_analysis  # noqa: E402
from src.provider import ProviderError  # noqa: E402


def main() -> int:
    tickers = sys.argv[1:] or ["TTWO", "AMXB.MX"]
    exit_code = 0
    for ticker in tickers:
        results = []
        errors = []
        for timeframe, params in analysis.TIMEFRAME_PARAMS.items():
            try:
                closes = provider.get_history(ticker, params["period"], params["interval"])
                results.append(analysis.analyze(closes, timeframe))
            except ProviderError as exc:
                errors.append(f"{timeframe}: {exc}")

        print(format_analysis(ticker, results, errors))
        print("-" * 60)
        if not results:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
