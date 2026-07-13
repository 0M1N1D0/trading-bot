# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python bot that monitors US (NYSE/NASDAQ) and Mexican (BMV) stock tickers via Yahoo Finance (`yfinance`) and sends Telegram alerts when price rules trigger (price above/below threshold, % change vs. previous close). It also accepts Telegram commands to manage the watchlist live, without restarting.

The README.md (in Spanish) is the primary user-facing doc — installation, config format, Telegram command reference, and a full Ubuntu/systemd deployment guide all live there. Read it for anything user-facing; this file is about working on the code itself.

## Commands

```powershell
# Setup (Windows/PowerShell — the dev machine for this repo)
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Run the bot (blocks until Ctrl+C)
python -m src.main

# Manual smoke tests (real network calls, not part of pytest)
python scripts/check_quotes.py TTWO AMXB.MX   # confirms yfinance returns real prices
python scripts/check_analysis.py TTWO AMXB.MX # confirms the technical-analysis pipeline end-to-end
python scripts/check_telegram.py              # confirms TELEGRAM_BOT_TOKEN/CHAT_ID work

# Tests
pip install pytest
pytest                          # full suite
pytest tests/test_rules.py      # single file
pytest tests/test_rules.py::test_price_above_triggers_when_price_exceeds_value  # single test
```

There is no linter/formatter configured in this repo (no ruff/black/flake8 config) — don't assume one.

Config lives in `config.yaml` (watchlist, thresholds, intervals) and `.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, copy from `.env.example`). Both are required for `src.main` to start; `src/config.py` raises `ConfigError` with a human-readable message if either is missing or malformed.

## Architecture

**Two independent I/O loops share the same in-process state**, wired together in `src/main.py`:

1. **`APScheduler` (`src/scheduler.py`)** — one interval job per watchlist ticker (`check_{ticker}`), each running its own cadence. Each tick does: check market hours → fetch quote → evaluate rules → dedupe via state → notify (+ optional periodic report).
2. **`python-telegram-bot` `Application` (`src/telegram_bot.py`)** — long-polls Telegram for incoming commands (`/add_action`, `/remove_action`, `/list_actions`, `/status`, `/analisis`, `/help`) from the configured chat only. `application.run_polling()` is what actually blocks the process in `main()`.

Both loops read/write the same `BackgroundScheduler`, `Notifier`, `StateStore`, and `WatchlistStore` instances — e.g. `/add_action` calls the same `add_watch_job()` that startup uses, so a ticker added over Telegram gets an interval job without restarting anything.

**Data flow per tick** (`scheduler.check_item`): `market_hours.is_open()` gate → `provider.get_quote()` (yfinance) → `rules.evaluate()` (pure function, evaluates *all* rules, doesn't know about prior state) → `state.should_notify()` (SQLite-backed hysteresis: only fires on the inactive→triggered transition, and only clears on triggered→inactive) → `notifier.send()` (Telegram, redacts the bot token from any error text, retries once).

**Two watchlist sources merge at runtime** (`watchlist_store.merge_watchlist`): `config.yaml` is the static/primary source; tickers added via Telegram persist in `data/state.db` (table `watchlist`, separate from the alert-dedup table `active_alerts` — same SQLite file, different concern) and survive restarts. On conflict, `config.yaml` wins. `src/telegram_bot.py`'s `BotContext` keeps its own merged `live_items` dict in memory as the source of truth for what's "currently watched" during a session.

**Provider isolation**: all market-data access goes through `src/provider.get_quote(ticker) -> Quote` (current price) and `src/provider.get_history(ticker, period, interval) -> list[float]` (historical closes). It's the single seam to swap data sources (e.g. off yfinance to Alpha Vantage/Finnhub) without touching scheduler/rules/analysis/telegram code — keep it that way when making provider-related changes.

**Pure vs. I/O split for testability**: `src/rules.py`, `src/analysis.py`, and `src/commands.py` are deliberately side-effect-free (no network, no state reads) so they're covered directly by unit tests; `src/telegram_bot.py` and `src/scheduler.py` hold the async/I/O glue and call into them. Preserve this split when adding new rule types, indicators, or commands — put parsing/formatting/evaluation logic in the pure modules, not inline in the handler.

**Technical analysis (`/analisis`)**: `src/analysis.analyze(closes, timeframe)` is a pure function computing SMA/MACD/momentum trend votes (net ≥+2 → `COMPRAR`, ≤−2 → `VENDER`, else `MANTENER`) plus an RSI-based confidence penalty (overbought/oversold caution, doesn't flip direction). `confidence` is intentionally capped to `[50, 85]` — it's a heuristic confluence score, not a real probability — and `commands.format_analysis` always appends a "not financial advice" disclaimer. `telegram_bot._analysis` fetches two horizons (`analysis.TIMEFRAME_PARAMS`: `"Horas"` = 60m/1mo, `"Días"` = 1d/6mo) and degrades gracefully per-horizon on `ProviderError` (e.g. missing intraday history for some `.MX` tickers) rather than failing the whole command.

**Blocking I/O inside async handlers**: `telegram_bot.py` calls `provider.get_quote` (blocking, yfinance) via `asyncio.to_thread(...)` — never call it directly from an `async def` handler, it would stall the whole bot's command processing.

**Interval strings** (`"30s"`, `"5m"`, `"30m"`, `"1h"`, `"1d"`) are parsed once, in `scheduler.parse_interval_seconds`; both `config.py` (YAML) and `commands.py` (`/add_action interval=...`) route through it for validation, so intervals stay consistent across both entry points.

**Market hours** (`src/market_hours.py`) is a plain timezone/weekday check (NYSE 9:30–16:00 America/New_York, BMV 8:30–15:00 America/Mexico_City) — no holiday calendar. `now` is injectable for tests.

## Conventions worth knowing

- User-facing strings (log messages, Telegram messages, `ConfigError` text, README) are in Spanish; keep new user-facing text consistent with that.
- Dataclasses in `src/models.py` (`WatchItem`, `AlertRule`, `Quote`) are frozen; `AlertRule.key()` (`"{type}:{value}"`) is the stable identity used for dedup in `state.py` — if you add a new `RuleType`, nothing else needs to change for dedup to work, but do add it to `_rule_triggered`/`_rule_message` in `rules.py` and to `_RULE_ALIASES` in `commands.py`.
- SQLite access uses parameterized queries (`?`), never string interpolation; `config.yaml` is loaded with `yaml.safe_load`. Keep both when touching `state.py`, `watchlist_store.py`, or `config.py`.
- Never let the Telegram bot token reach logs unredacted — `Notifier._redact` exists specifically because the token is embedded in the request URL and leaks into `requests` exception text.
