"""Envío de mensajes al bot de Telegram del usuario."""

from __future__ import annotations

import logging

import requests

from src.config import TelegramConfig

logger = logging.getLogger(__name__)

_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
_TIMEOUT_SECONDS = 10
_REDACTED = "***TOKEN_REDACTED***"


class Notifier:
    def __init__(self, telegram: TelegramConfig):
        self._token = telegram.bot_token
        self._url = _API_URL.format(token=telegram.bot_token)
        self._chat_id = telegram.chat_id

    def _redact(self, text: str) -> str:
        """El token va embebido en la URL, así que aparece tal cual dentro
        del texto de las excepciones de `requests` (p. ej. errores de
        conexión). Sin esto, cada hipo de red en el servidor escribiría el
        token del bot en texto plano en data/bot.log."""
        return text.replace(self._token, _REDACTED)

    def send(self, text: str) -> bool:
        """Manda `text` (Markdown) al chat configurado. Reintenta una vez si
        falla por red. Devuelve True si Telegram confirmó el envío, False si
        no (nunca lanza excepción: un fallo de notificación no debe tumbar
        el bucle del bot)."""
        payload = {"chat_id": self._chat_id, "text": text, "parse_mode": "Markdown"}
        for attempt in (1, 2):
            try:
                resp = requests.post(self._url, json=payload, timeout=_TIMEOUT_SECONDS)
                if resp.status_code == 200 and resp.json().get("ok"):
                    return True
                logger.warning(
                    "Telegram respondió %s en intento %d: %s",
                    resp.status_code,
                    attempt,
                    self._redact(resp.text[:300]),
                )
            except requests.RequestException as exc:
                logger.warning(
                    "Error de red enviando a Telegram (intento %d): %s",
                    attempt,
                    self._redact(str(exc)),
                )
        logger.error("No se pudo enviar el mensaje a Telegram tras 2 intentos: %s", text[:100])
        return False
