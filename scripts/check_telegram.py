"""Prueba manual: manda un mensaje de prueba a Telegram usando la
configuración de .env, para confirmar que el bot y el chat_id son correctos.

Uso:
    python scripts/check_telegram.py "mensaje opcional"
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.config import ConfigError, load_config  # noqa: E402
from src.notifier import Notifier  # noqa: E402


def main() -> int:
    text = " ".join(sys.argv[1:]) or "✅ Prueba de conexión del bot de mercado."
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Error de configuración: {exc}")
        return 1

    notifier = Notifier(config.telegram)
    ok = notifier.send(text)
    print("Mensaje enviado correctamente." if ok else "No se pudo enviar el mensaje.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
