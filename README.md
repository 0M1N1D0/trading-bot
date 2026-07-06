# Trading Bot — monitoreo de mercado (USA + México)

Bot en Python que vigila acciones de EE.UU. y de la Bolsa Mexicana de Valores
(BMV), a intervalos configurables por acción, y manda alertas por Telegram
cuando el precio cruza un umbral o cambia más de cierto porcentaje. También
puede mandar un reporte periódico del precio.

Usa **[yfinance](https://pypi.org/project/yfinance/)** (Yahoo Finance) como
fuente de datos: es gratuita y no requiere API key.

## 1. Crear el bot de Telegram

1. Abre Telegram y busca **@BotFather**.
2. Mándale `/newbot` y sigue las instrucciones (nombre y username del bot).
3. Te dará un **token** como `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`. Guárdalo.
4. Mándale **cualquier mensaje** a tu bot recién creado (para que pueda
   escribirte de vuelta).
5. Obtén tu **chat_id**:
   - Opción rápida: busca **@userinfobot** en Telegram, mándale un mensaje y
     te dirá tu `Id`.
   - Opción manual: visita en el navegador
     `https://api.telegram.org/bot<TU_TOKEN>/getUpdates` después de haberle
     escrito al bot, y busca `"chat":{"id": ...}` en la respuesta.

## 2. Instalación

```powershell
cd C:\trading-bot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Configuración

1. Copia `.env.example` a `.env` y llena tu token y chat_id:

   ```powershell
   copy .env.example .env
   ```

2. Edita `config.yaml` con las acciones que quieres vigilar. Ejemplo:

   ```yaml
   default_interval: 5m
   market_hours_only: true
   periodic_report: true
   watchlist:
     - ticker: TTWO # Take-Two Interactive (EE.UU.)
       market: US
       interval: 5m
       rules:
         - { type: price_above, value: 200 }
         - { type: price_below, value: 150 }
         - { type: pct_change, value: 3 }

     - ticker: AMXB.MX # América Móvil (BMV)
       market: MX
       interval: 30m
       rules:
         - { type: pct_change, value: 2 }
   ```

   **Cómo escribir el ticker:**
   - Acciones de EE.UU.: igual que en GBM, ej. `TTWO`, `AAPL`, `MSFT`.
   - Acciones de la BMV: agrega el sufijo `.MX`, ej. `AMXB.MX` (América
     Móvil), `GFNORTEO.MX`, `WALMEX.MX`. El ticker exacto no siempre coincide
     con el nombre corto de GBM: confírmalo en https://finance.yahoo.com/
     antes de agregarlo a `config.yaml`.

   **Intervalos válidos:** `30s`, `5m`, `30m`, `1h`, `1d`.

   **Tipos de regla:**
   - `price_above` / `price_below`: alerta cuando el precio cruza `value`.
   - `pct_change`: alerta cuando el cambio contra el cierre previo supera
     ±`value` puntos porcentuales.

   Cada acción manda además un reporte periódico con su precio si
   `periodic_report: true` (a nivel global).

## 4. Probar antes de dejarlo corriendo

```powershell
# Confirma que yfinance responde con precios reales
python scripts/check_quotes.py TTWO AMXB.MX

# Confirma que Telegram está bien configurado
python scripts/check_telegram.py

# Corre las pruebas unitarias (reglas, dedup, horario de mercado, intervalos)
pip install pytest
pytest
```

## 5. Correr el bot

```powershell
python -m src.main
```

El bot se queda corriendo, revisando cada acción en su propio intervalo, y
escribe su actividad en consola y en `data/bot.log` (con rotación automática:
5 archivos de 5 MB máx., para no llenar el disco en un servidor 24/7).
Detente con `Ctrl+C`.

Por defecto (`market_hours_only: true`) solo evalúa mientras el mercado
correspondiente está abierto (NYSE/NASDAQ 9:30–16:00 hora NY; BMV 8:30–15:00
hora CDMX, lunes a viernes). Ponlo en `false` si quieres que revise siempre.

## 6. Dejarlo corriendo 24/7 en Windows

**Opción simple — Tarea Programada:**

1. Abre "Programador de tareas" (Task Scheduler).
2. Crear tarea básica → Desencadenador: "Al iniciar el equipo" (o "Diario").
3. Acción: "Iniciar un programa".
   - Programa: `C:\trading-bot\venv\Scripts\pythonw.exe`
   - Argumentos: `-m src.main`
   - Iniciar en: `C:\trading-bot`
4. En Configuración, marca "Ejecutar la tarea lo antes posible si se pierde
   una ejecución programada" y, si quieres que reinicie solo tras un error,
   configura "Reiniciar si la tarea produce un error".

Con esto el bot arranca solo al prender la máquina y sigue corriendo en
segundo plano (usa `pythonw.exe`, no abre ventana de consola).

**Servidor Linux — `systemd` (recomendado si el bot corre en una VPS/servidor Linux):**

1. Crea un usuario sin privilegios dedicado al bot (nunca lo corras como root):

   ```bash
   sudo useradd --system --create-home --shell /usr/sbin/nologin tradingbot
   sudo cp -r trading-bot /opt/trading-bot
   sudo chown -R tradingbot:tradingbot /opt/trading-bot
   sudo chmod 600 /opt/trading-bot/.env
   ```

2. Crea `/etc/systemd/system/trading-bot.service`:

   ```ini
   [Unit]
   Description=Bot de monitoreo de mercado
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   User=tradingbot
   Group=tradingbot
   WorkingDirectory=/opt/trading-bot
   ExecStart=/opt/trading-bot/venv/bin/python -m src.main
   Restart=on-failure
   RestartSec=10

   # --- Hardening: reduce lo que el proceso puede hacer si se ve comprometido ---
   NoNewPrivileges=true
   PrivateTmp=true
   ProtectSystem=strict
   ProtectHome=true
   ReadWritePaths=/opt/trading-bot/data
   ProtectKernelTunables=true
   ProtectKernelModules=true
   ProtectControlGroups=true
   RestrictSUIDSGID=true
   MemoryDenyWriteExecute=true

   [Install]
   WantedBy=multi-user.target
   ```

3. Actívalo:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now trading-bot
   sudo systemctl status trading-bot
   journalctl -u trading-bot -f   # ver logs en vivo
   ```

`Restart=on-failure` hace que systemd reinicie el bot solo si crashea, algo
que no ofrece el script por sí mismo.

## Seguridad (importante si el bot corre en un servidor)

El proyecto ya incluye estas protecciones, pero conviene entender qué hacen:

- **El token de Telegram nunca se loguea.** `src/notifier.py` redacta el
  token de cualquier mensaje de error (p. ej. fallos de red), porque de otro
  modo aparecería en texto plano en `data/bot.log` cada vez que hay un hipo
  de conexión — cualquiera con acceso a los logs podría secuestrar el bot.
- **`.env` nunca se sube a git** (está en `.gitignore`) y, al arrancar en
  Linux/Mac, el bot restringe sus permisos a `600` (solo el dueño puede
  leerlo) si detecta que quedaron demasiado abiertos. En Windows este chequeo
  no aplica: ahí la protección depende de los permisos de la carpeta/usuario.
- **Los logs rotan** (5 × 5 MB) para que un bot corriendo meses no llene el
  disco del servidor.
- **Sin superficie de ataque de red entrante:** el bot solo hace peticiones
  salientes (a Yahoo Finance y Telegram); no abre ningún puerto ni acepta
  conexiones, así que no hay endpoint que atacar desde fuera.
- **Sin `eval`/`exec`/`pickle`/YAML inseguro:** `config.yaml` se carga con
  `yaml.safe_load` (no ejecuta código arbitrario) y las consultas a SQLite
  usan parámetros (`?`), no interpolación de strings.

Recomendaciones adicionales para un servidor de producción:

- **No correr el bot como root/Administrador.** Usa un usuario dedicado sin
  privilegios (ver el ejemplo de `systemd` arriba).
- **Restringe el firewall de salida** si tu servidor lo permite, a solo
  `api.telegram.org` y los dominios de Yahoo Finance (`*.yahoo.com`,
  `*.yahooapis.com`) — el bot no necesita nada más.
- **Revoca y regenera el token con @BotFather (`/revoke`)** si sospechas que
  se filtró (por ejemplo, si `.env` se subió a un repo por error).
- **Mantén dependencias actualizadas**: `pip list --outdated` y de vez en
  cuando `pip install --upgrade -r requirements.txt` dentro del venv.
- **No comitees `.env` ni `data/*.db`/`data/*.log`** — ya están en
  `.gitignore`, pero revisa `git status` antes de un `git add` amplio.

## Estructura del proyecto

```
trading-bot/
├── config.yaml         # qué vigilar, intervalos, umbrales
├── .env                # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (no se sube a git)
├── src/
│   ├── main.py          # arranca el bot
│   ├── config.py        # carga config.yaml + .env
│   ├── models.py        # tipos: WatchItem, Quote, AlertRule...
│   ├── provider.py       # obtiene precios (yfinance)
│   ├── rules.py          # evalúa umbrales y % de cambio
│   ├── notifier.py       # manda mensajes a Telegram
│   ├── market_hours.py   # ¿mercado abierto?
│   ├── state.py          # evita repetir la misma alerta (SQLite)
│   └── scheduler.py      # un job por acción con su propio intervalo
├── scripts/
│   ├── check_quotes.py   # prueba manual de datos de mercado
│   └── check_telegram.py # prueba manual de envío a Telegram
├── tests/                # pruebas unitarias (pytest)
└── data/                 # bot.log y state.db (se crean solos)
```

## Cambiar de fuente de datos

Toda la lógica de mercado pasa por `src/provider.py` (`get_quote(ticker)`).
Si en el futuro yfinance no da abasto (rate limiting, cobertura), se puede
reemplazar por Alpha Vantage o Finnhub reescribiendo solo ese archivo.
