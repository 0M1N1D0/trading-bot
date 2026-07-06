"""Prueba manual: consulta cotizaciones reales de un ticker de EE.UU. y uno
de México, para confirmar que yfinance responde correctamente.

Uso:
    python scripts/check_quotes.py [TICKER ...]

Si no se pasan tickers, usa TTWO y AMXB.MX como ejemplo.
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.provider import ProviderError, get_quote  # noqa: E402


def main() -> int:
    tickers = sys.argv[1:] or ["TTWO", "AMXB.MX"]
    exit_code = 0
    for ticker in tickers:
        try:
            quote = get_quote(ticker)
            print(
                f"{quote.ticker:12s} precio=${quote.price:,.2f}  "
                f"cierre_previo=${quote.prev_close:,.2f}  "
                f"cambio={quote.pct_change:+.2f}%  ({quote.timestamp.isoformat()})"
            )
        except ProviderError as exc:
            print(f"ERROR: {exc}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
