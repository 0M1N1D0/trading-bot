"""Punto de entrada del bot: carga configuración, arranca el scheduler y el
bot de Telegram (comandos entrantes), y se mantiene vivo hasta Ctrl+C."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config import ConfigError, load_config  # noqa: E402
from src.notifier import Notifier  # noqa: E402
from src.scheduler import add_watch_job, build_scheduler  # noqa: E402
from src.state import StateStore  # noqa: E402
from src.telegram_bot import build_application  # noqa: E402
from src.watchlist_store import WatchlistStore, merge_watchlist  # noqa: E402

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
    watchlist_store = WatchlistStore()
    scheduler = build_scheduler(config, notifier, state)

    # Acciones agregadas por Telegram en sesiones anteriores: se reprograman
    # aquí para que sobrevivan a un reinicio del bot. config.yaml manda si un
    # mismo ticker aparece en ambos lados (ver merge_watchlist).
    live_items = merge_watchlist(config.watchlist, watchlist_store)
    for item in live_items:
        if item.ticker not in {w.ticker for w in config.watchlist}:
            add_watch_job(scheduler, item, config, notifier, state)

    tickers = ", ".join(item.ticker for item in live_items)
    logger.info("Bot iniciado. Vigilando: %s", tickers)
    notifier.send(f"🤖 Bot de mercado iniciado. Vigilando: {tickers}")

    scheduler.start()

    application = build_application(config, scheduler, notifier, state, watchlist_store)

    try:
        # Bloquea aquí hasta Ctrl+C / SIGTERM: run_polling maneja sus propios
        # señales y su propio loop de asyncio para recibir comandos.
        application.run_polling(close_loop=False)
    finally:
        scheduler.shutdown(wait=False)
        state.close()
        watchlist_store.close()
        logger.info("Bot detenido.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
