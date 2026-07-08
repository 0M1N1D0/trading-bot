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

### Comandos de Telegram (gestionar la watchlist sin reiniciar)

Además de `config.yaml`, el bot escucha comandos en el chat configurado
(`TELEGRAM_CHAT_ID`) para agregar o quitar acciones **en caliente**, sin
reiniciar el proceso. Cualquier otro chat que le escriba es ignorado.

| Comando | Ejemplo | Qué hace |
|---|---|---|
| `/add_action` (alias `/add`) | `/add_action TTWO price_above=260 pct_change=3` | Agrega un ticker a la watchlist. Solo el ticker es obligatorio; el resto son argumentos opcionales `clave=valor`: `market=US\|MX`, `interval=15m`, `price_above=N`, `price_below=N`, `pct_change=N`. Sin reglas, la acción queda en monitoreo simple (sin alertas) hasta que se le agreguen. |
| `/remove_action` (alias `/remove`) | `/remove_action TTWO` | Quita un ticker de la watchlist. Si el ticker viene de `config.yaml`, se quita solo de la sesión actual y reaparecerá al reiniciar (edita `config.yaml` para quitarlo de forma permanente). |
| `/list_actions` (alias `/list`) | `/list_actions` | Muestra la watchlist completa (config.yaml + agregadas por Telegram) con su intervalo y reglas. |
| `/status` | `/status AAPL` | Precio actual de un ticker (o de toda la watchlist si no se indica ninguno). |
| `/help` (alias `/start`) | `/help` | Lista los comandos disponibles. |

El mercado (`US`/`MX`) se infiere del ticker: sufijo `.MX` → `MX`, si no →
`US` (mismo criterio que `config.yaml`). Las acciones agregadas por
Telegram se guardan en `data/state.db` y sobreviven a un reinicio del bot.

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

**Servidor Linux (Ubuntu Server):** ver la guía completa más abajo,
[Despliegue en Ubuntu Server](#despliegue-en-ubuntu-server).

## Despliegue en Ubuntu Server

Guía de punta a punta para pasar de "el bot corre en mi laptop Windows" a
"el bot corre 24/7 en un servidor Ubuntu", con un usuario sin privilegios y
reinicio automático si crashea. Se usa `/opt/trading-bot` como ruta; cambia
según prefieras.

### 1. Prerrequisitos en el servidor

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip tzdata
python3 --version   # debe ser 3.9 o superior (el bot usa zoneinfo, de la stdlib desde 3.9)
```

Si tu Ubuntu es 20.04 (Python 3.8), instala Python 3.9+ vía el PPA
`deadsnakes` o actualiza a Ubuntu 22.04/24.04 LTS antes de continuar.

### 2. Subir el código al servidor

El proyecto vive hoy en tu máquina Windows, no en un repo git. La forma más
simple es empaquetarlo (excluyendo `venv/` y `data/`, que son específicos de
cada máquina — el `venv` de Windows **no funciona en Linux**, hay que
recrearlo ahí) y copiarlo por `scp`:

```powershell
# En PowerShell, desde C:\trading-bot
tar --exclude="venv" --exclude="data" --exclude="__pycache__" --exclude=".pytest_cache" -czf trading-bot.tar.gz .
scp trading-bot.tar.gz usuario@IP_DEL_SERVIDOR:/tmp/
```

```bash
# En el servidor
sudo mkdir -p /opt/trading-bot
sudo tar -xzf /tmp/trading-bot.tar.gz -C /opt/trading-bot
rm /tmp/trading-bot.tar.gz
```

Si más adelante quieres actualizar el código, repite estos dos pasos (o,
mejor aún, sube el proyecto a un repo git privado y usa `git pull` — más
cómodo para actualizaciones frecuentes).

### 3. Crear el entorno virtual e instalar dependencias (en el servidor)

```bash
cd /opt/trading-bot
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
```

### 4. Configurar `.env` y `config.yaml`

```bash
cp /opt/trading-bot/.env.example /opt/trading-bot/.env
nano /opt/trading-bot/.env      # pega tu TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID
chmod 600 /opt/trading-bot/.env
```

Tu `config.yaml` (watchlist, umbrales, intervalos) ya viaja tal cual dentro
del `.tar.gz`, así que normalmente no necesitas volver a escribirlo — solo
revísalo con `nano /opt/trading-bot/config.yaml` por si quieres ajustar algo
específico del servidor (por ejemplo, intervalos más largos si el servidor
tiene recursos limitados).

### 5. Probar antes de dejarlo como servicio

```bash
cd /opt/trading-bot
source venv/bin/activate
python scripts/check_quotes.py TTWO
python scripts/check_telegram.py
pip install pytest && pytest
deactivate
```

### 6. Usuario dedicado sin privilegios

Nunca corras el bot como `root`. Crea un usuario de sistema exclusivo y
transfiérele la propiedad de la carpeta:

```bash
sudo useradd --system --home /opt/trading-bot --shell /usr/sbin/nologin tradingbot
sudo mkdir -p /opt/trading-bot/data   # el .tar.gz no la incluye; systemd la necesita creada de antemano
sudo chown -R tradingbot:tradingbot /opt/trading-bot
```

### 7. Servicio `systemd` (arranque automático + reinicio ante fallos)

Crea `/etc/systemd/system/trading-bot.service`:

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

Actívalo:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now trading-bot
sudo systemctl status trading-bot
journalctl -u trading-bot -f   # ver logs en vivo (Ctrl+C para salir)
```

`Restart=on-failure` hace que systemd reinicie el bot solo si crashea, algo
que el script no hace por sí mismo.

### 8. Firewall (`ufw`)

El bot no necesita ningún puerto de entrada (solo hace peticiones salientes
a Yahoo Finance y Telegram), así que puedes cerrar todo el tráfico entrante
por defecto. **Cuidado:** si administras el servidor por SSH, debes permitir
el puerto 22 explícitamente *antes* de activar `ufw`, o perderás el acceso:

```bash
sudo ufw allow OpenSSH          # o: sudo ufw allow 22/tcp
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable
sudo ufw status verbose
```

### 9. Mantenimiento

```bash
sudo systemctl restart trading-bot   # reiniciar tras un cambio de config
sudo systemctl stop trading-bot      # detener
journalctl -u trading-bot -n 100     # últimas 100 líneas de log
tail -f /opt/trading-bot/data/bot.log  # log rotado de la app

# Actualizar dependencias:
cd /opt/trading-bot && source venv/bin/activate
pip list --outdated
pip install --upgrade -r requirements.txt
deactivate
sudo systemctl restart trading-bot

# Desinstalar por completo:
sudo systemctl disable --now trading-bot
sudo rm /etc/systemd/system/trading-bot.service
sudo systemctl daemon-reload
sudo userdel tradingbot
```

Considera además activar `unattended-upgrades` (`sudo apt install -y
unattended-upgrades && sudo dpkg-reconfigure --priority=low
unattended-upgrades`) para que el sistema operativo reciba parches de
seguridad automáticamente.

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
  privilegios (ver el paso 6 de la guía de Ubuntu arriba).
- **Cierra el tráfico entrante con `ufw`** (paso 8 de la guía): el bot no
  necesita ningún puerto abierto, solo SSH para administración. Restringir
  la salida por dominio (`api.telegram.org`, Yahoo Finance) no es práctico
  con `ufw` porque resuelve el hostname a una IP fija al crear la regla, y
  esas IPs cambian (son CDN); no vale la pena el riesgo de reglas rotas.
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
│   ├── main.py             # arranca el bot
│   ├── config.py           # carga config.yaml + .env
│   ├── models.py           # tipos: WatchItem, Quote, AlertRule...
│   ├── provider.py         # obtiene precios (yfinance)
│   ├── rules.py            # evalúa umbrales y % de cambio
│   ├── notifier.py         # manda mensajes a Telegram (saliente)
│   ├── telegram_bot.py     # recibe comandos de Telegram (/add_action...)
│   ├── commands.py         # parseo/formato de los comandos (puro, testeable)
│   ├── market_hours.py     # ¿mercado abierto?
│   ├── state.py            # evita repetir la misma alerta (SQLite)
│   ├── watchlist_store.py  # persiste acciones agregadas por Telegram (SQLite)
│   └── scheduler.py        # un job por acción con su propio intervalo
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
