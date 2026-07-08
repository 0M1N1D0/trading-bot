"""Bot de Telegram que recibe comandos para gestionar la watchlist en
caliente (agregar/quitar acciones, listarlas, consultar precio) sin
reiniciar el proceso principal.

A diferencia de src/notifier.py (que solo manda alertas salientes), este
módulo abre un long-polling hacia la API de Telegram y despacha comandos.
Solo el chat configurado en TELEGRAM_CHAT_ID puede usarlos; el resto de
chats se ignora en silencio (filtro a nivel de Application, no expone
ningún error que confirme la existencia del bot a terceros).
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, filters

from src import provider
from src.commands import format_quote, format_watchlist, parse_add_args
from src.config import AppConfig
from src.models import WatchItem
from src.notifier import Notifier
from src.provider import ProviderError
from src.scheduler import add_watch_job, remove_watch_job
from src.state import StateStore
from src.watchlist_store import WatchlistStore, merge_watchlist

logger = logging.getLogger(__name__)

_HELP_TEXT = (
    "🤖 *Comandos disponibles:*\n"
    "/add\\_action TICKER \\[market=US|MX\\] \\[interval=5m\\] \\[price\\_above=N\\] "
    "\\[price\\_below=N\\] \\[pct\\_change=N\\] — agrega una acción a la watchlist\n"
    "/remove\\_action TICKER — quita una acción de la watchlist\n"
    "/list\\_actions — muestra la watchlist actual\n"
    "/status \\[TICKER\\] — precio actual (de una acción o de todas)\n"
    "/help — este mensaje\n\n"
    "*Ejemplos:*\n"
    "`/add_action AAPL`\n"
    "`/add_action TTWO price_above=260 pct_change=3`\n"
    "`/add_action AMXB.MX interval=30m pct_change=2`"
)

_CTX_KEY = "bot_ctx"


class BotContext:
    """Agrupa las dependencias vivas que necesitan los handlers de comandos
    (scheduler, config, notifier, estado, persistencia) y el "quién está
    vigilado ahora mismo" combinando config.yaml + watchlist dinámica."""

    def __init__(
        self,
        config: AppConfig,
        scheduler: BackgroundScheduler,
        notifier: Notifier,
        state: StateStore,
        watchlist_store: WatchlistStore,
    ) -> None:
        self.config = config
        self.scheduler = scheduler
        self.notifier = notifier
        self.state = state
        self.watchlist_store = watchlist_store
        self.yaml_tickers = {item.ticker for item in config.watchlist}
        self.live_items: dict[str, WatchItem] = {
            item.ticker: item for item in merge_watchlist(config.watchlist, watchlist_store)
        }


def _get_ctx(context: ContextTypes.DEFAULT_TYPE) -> BotContext:
    return context.application.bot_data[_CTX_KEY]


async def _add_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    ctx = _get_ctx(context)

    try:
        item = parse_add_args(context.args or [], ctx.config.default_interval)
    except ValueError as exc:
        await update.message.reply_text(f"⚠️ {exc}")
        return

    if item.ticker in ctx.live_items:
        await update.message.reply_text(
            f"⚠️ *{item.ticker}* ya está en la watchlist. Usa /remove_action primero "
            "si quieres redefinirla.",
            parse_mode="Markdown",
        )
        return

    try:
        # get_quote es I/O bloqueante (yfinance); no puede correr directo en
        # el event loop de PTB o congelaría el resto de comandos entrantes.
        quote = await asyncio.to_thread(provider.get_quote, item.ticker)
    except ProviderError as exc:
        await update.message.reply_text(f"⚠️ No se pudo validar {item.ticker}: {exc}")
        return

    ctx.watchlist_store.add(item)
    add_watch_job(ctx.scheduler, item, ctx.config, ctx.notifier, ctx.state)
    ctx.live_items[item.ticker] = item

    await update.message.reply_text(
        f"✅ *{item.ticker}* agregado a la watchlist (cada {item.interval}).\n"
        f"{format_quote(item, quote)}",
        parse_mode="Markdown",
    )


async def _remove_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    ctx = _get_ctx(context)

    args = context.args or []
    if not args:
        await update.message.reply_text("Uso: /remove_action TICKER")
        return

    ticker = args[0].strip().upper()
    if ticker not in ctx.live_items:
        await update.message.reply_text(
            f"⚠️ *{ticker}* no está en la watchlist.", parse_mode="Markdown"
        )
        return

    remove_watch_job(ctx.scheduler, ticker)
    was_dynamic = ctx.watchlist_store.remove(ticker)
    del ctx.live_items[ticker]

    note = ""
    if not was_dynamic:
        note = (
            "\n_Nota: viene de config.yaml, así que reaparecerá si reinicias el bot. "
            "Para quitarla de forma permanente, edita config.yaml._"
        )
    await update.message.reply_text(
        f"🗑️ *{ticker}* quitado de la watchlist.{note}", parse_mode="Markdown"
    )


async def _list_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    ctx = _get_ctx(context)
    items = sorted(ctx.live_items.values(), key=lambda item: item.ticker)
    await update.message.reply_text(format_watchlist(items), parse_mode="Markdown")


async def _status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    ctx = _get_ctx(context)

    args = context.args or []
    tickers = [args[0].strip().upper()] if args else sorted(ctx.live_items.keys())
    if not tickers:
        await update.message.reply_text("📋 La watchlist está vacía.")
        return

    lines = []
    for ticker in tickers:
        item = ctx.live_items.get(ticker) or WatchItem(ticker=ticker, market="US", interval="5m")
        try:
            quote = await asyncio.to_thread(provider.get_quote, ticker)
            lines.append(format_quote(item, quote))
        except ProviderError as exc:
            lines.append(f"⚠️ {ticker}: {exc}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def _help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(_HELP_TEXT, parse_mode="Markdown")


def build_application(
    config: AppConfig,
    scheduler: BackgroundScheduler,
    notifier: Notifier,
    state: StateStore,
    watchlist_store: WatchlistStore,
) -> Application:
    """Construye (sin arrancar) la Application de python-telegram-bot con
    todos los comandos registrados, restringidos al chat_id configurado."""
    bot_ctx = BotContext(config, scheduler, notifier, state, watchlist_store)
    owner_only = filters.Chat(chat_id=int(config.telegram.chat_id))

    application = Application.builder().token(config.telegram.bot_token).build()
    application.bot_data[_CTX_KEY] = bot_ctx

    application.add_handler(CommandHandler(["add_action", "add"], _add_action, filters=owner_only))
    application.add_handler(
        CommandHandler(["remove_action", "remove"], _remove_action, filters=owner_only)
    )
    application.add_handler(
        CommandHandler(["list_actions", "list"], _list_actions, filters=owner_only)
    )
    application.add_handler(CommandHandler("status", _status, filters=owner_only))
    application.add_handler(CommandHandler(["help", "start"], _help, filters=owner_only))

    logger.info("Bot de Telegram configurado con %d comandos.", 5)
    return application
