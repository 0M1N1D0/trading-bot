"""Punto de entrada del bot: carga configuración, arranca el scheduler y
se mantiene vivo hasta Ctrl+C."""

from __future__ import annotations

import logging
import signal
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config import ConfigError, load_config  # noqa: E402
from src.notifier import Notifier  # noqa: E402
from src.scheduler import build_scheduler  # noqa: E402
from src.state import StateStore  # noqa: E402

LOG_DIR = BASE_DIR / "data"
LOG_FILE = LOG_DIR / "bot.log"


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # La consola de Windows suele usar cp1252, que no puede representar los
    # emojis que usan los mensajes de alerta (🔼 🔽 ⚡ 📊...). Sin esto, el
    # primer log con un emoji lanza UnicodeEncodeError y tumba el bot.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # stdout no soporta reconfigure (ej. algunos entornos embebidos)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            # Rotación por tamaño: en un servidor 24/7 un FileHandler simple
            # crecería sin límite hasta llenar el disco. 5 MB x 5 respaldos
            # (25 MB máx) es de sobra para revisar actividad reciente.
            RotatingFileHandler(
                LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
            ),
        ],
    )
    # yfinance/urllib3 son muy verbosos en INFO; bajarlos a WARNING.
    logging.getLogger("yfinance").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("peewee").setLevel(logging.WARNING)


def main() -> int:
    setup_logging()
    logger = logging.getLogger("main")

    try:
        config = load_config()
    except ConfigError as exc:
        logger.error("Error de configuración: %s", exc)
        return 1

    notifier = Notifier(config.telegram)
    state = StateStore()
    scheduler = build_scheduler(config, notifier, state)

    tickers = ", ".join(item.ticker for item in config.watchlist)
    logger.info("Bot iniciado. Vigilando: %s", tickers)
    notifier.send(f"🤖 Bot de mercado iniciado. Vigilando: {tickers}")

    scheduler.start()

    stop = {"flag": False}

    def _handle_signal(signum, frame):  # noqa: ANN001
        logger.info("Señal %s recibida, apagando...", signum)
        stop["flag"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        while not stop["flag"]:
            time.sleep(1)
    finally:
        scheduler.shutdown(wait=False)
        state.close()
        logger.info("Bot detenido.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
