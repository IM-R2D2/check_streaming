# Icecast Stream Monitor

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-See%20repo-lightgrey.svg)](LICENSE)

Monitor Icecast (and custom JSON-API) streams and get Telegram alerts when a stream goes down. Supports multiple mount points, HTTP/HTTPS, Basic Auth, and optional JSON status output for dashboards.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Quick Start (Docker)](#quick-start-docker)
- [Configuration](#configuration)
  - [Icecast](#icecast-configuration)
  - [Custom checker](#custom-checker)
  - [Telegram](#telegram)
  - [Endpoints & ports](#endpoints-and-ports)
- [Usage](#usage)
- [Project structure](#project-structure)
- [Logging](#logging)
- [Notifications](#notifications)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## Features

- **Multiple streams** — Monitor several mount points at once (main, backup, different bitrates).
- **Remote monitoring** — Check Icecast servers from an external host.
- **HTTP Basic Auth** — Support for protected Icecast/admin endpoints.
- **Flexible endpoints** — Auto-detection of Icecast API endpoints: `/admin/stats`, `/status-json.xsl`, `/admin/listmounts.xsl`, `/status.xsl`.
- **JSON status file** — Optional `status-online.json` with per-stream status for web UIs.
- **Smart Telegram notifications**:
  - Down alerts with cooldown to avoid spam.
  - Recovery alerts sent immediately (no cooldown).
  - Periodic reminders for long-lasting outages (e.g. every 30 checks).
- **Date-based logging** — Log files named by date with rotation (e.g. `YYYY-MM-DD-icecast_check.log`).
- **Configurable** — Check interval, cooldown, log size, log level.
- **Error handling** — Retries and detailed logging.
- **HTTP/HTTPS** — Standard ports (80/443) handled without explicit port in URLs when applicable.
- **Two checker types** — **Icecast** (native Icecast API) and **Custom** (any JSON API returning `{ "mount": listeners }`).

---

## Requirements

- **Python 3.10+** (for Docker: image uses Python 3.14)
- **Dependencies**: `requests`, `beautifulsoup4` (see `requirements.txt`)
- Network access to the Icecast (or custom) server and to Telegram API
- For remote monitoring: Icecast server must be reachable (firewall/port open, stats enabled)

---

## Quick Start (Docker)

1. **Clone and enter the repo**
   ```bash
   git clone <repo-url>
   cd check_streaming
   ```

2. **Create config from template**
   - For **Icecast**: copy `config_icecast_example.json` to `config.json`.
   - For **custom JSON-API**: copy `config_custom_example.json` to `config.json`.

3. **Edit `config.json`** — Set Icecast host/port, streams, and Telegram `bot_token` / `chat_id`.

4. **Deploy**
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```
   Or manually:
   ```bash
   docker compose up -d --build
   ```

The container runs `global-checker.py`, which picks **Icecast** or **Custom** checker from `icecast.type` in config. Config is mounted read-only; `status-online.json` and logs are written to local files/dirs. Restart policy is `always`; healthcheck runs `global-checker.py --once` every 60s.

---

## Configuration

Config file: `config.json` (not committed; use example configs as templates).

### Icecast configuration

| Field | Description |
|-------|-------------|
| `icecast.type` | `"icecast"` (default) or `"custom"` |
| `icecast.id` | Optional identifier (e.g. for log file names). |
| `icecast.host` | Icecast hostname or IP. |
| `icecast.port` | Port (e.g. 8000; 443 for HTTPS, 80 for HTTP). |
| `icecast.use_https` | `true` / `false`. |
| `icecast.timeout` | Request timeout in seconds. |
| `icecast.check_interval` | Seconds between checks. |
| `icecast.endpoint` | Preferred stats endpoint (e.g. `/admin/stats`). |
| `icecast.endpoint_only` | If `true`, use only `endpoint`; if `false`, fallback to others. |
| `icecast.auth` | `username`, `password`, `enabled` for HTTP Basic Auth. |
| `icecast.streams` | Array of `{ "mount_point", "name", "enabled" }`. |

**Example (excerpt):**

```json
{
  "icecast": {
    "id": "radio1",
    "type": "icecast",
    "host": "radio1.example.com",
    "port": 8000,
    "use_https": false,
    "timeout": 15,
    "check_interval": 60,
    "endpoint": "/admin/stats",
    "endpoint_only": false,
    "auth": {
      "username": "admin",
      "password": "secret",
      "enabled": true
    },
    "streams": [
      { "mount_point": "/main", "name": "Main 128k", "enabled": true },
      { "mount_point": "/backup", "name": "Backup 64k", "enabled": true }
    ]
  }
}
```

### Custom checker

For non-Icecast servers that expose a JSON API returning a map **mount → listener count**:

- Set `icecast.type` to `"custom"`.
- Set `icecast.endpoint` to your API path (e.g. `/api/streams`).
- Use `endpoint_only: true` so only that URL is used.
- Streams are still listed in `icecast.streams`; the checker requests the endpoint once and checks each `mount_point` in the response.

Expected response shape:

```json
{
  "/main": 5,
  "/backup": 2
}
```

Use `config_custom_example.json` as a template.

### Telegram

```json
"telegram": {
  "bot_token": "YOUR_BOT_TOKEN",
  "chat_id": "YOUR_CHAT_ID",
  "enabled": true
}
```

Create a bot via [@BotFather](https://t.me/BotFather); get chat ID e.g. via [@userinfobot](https://t.me/userinfobot).

### Endpoints and ports

- **Endpoints**: `/admin/stats`, `/status-json.xsl`, `/admin/listmounts.xsl`, `/status.xsl` (auto-tried when `endpoint_only` is false).
- **Port 443 (HTTPS)** / **80 (HTTP)**: URL is built without port (e.g. `https://host/path`).
- **Other ports**: URL includes port (e.g. `http://host:8000/path`).

### Logging and status file

```json
"logging": {
  "log_file": "/var/log/scripts/check_streaming/{YYYY}-{MM}-{DD}-icecast_check.log",
  "log_level": "INFO",
  "max_file_size": 10485760,
  "backup_count": 5
},
"status_json": {
  "enabled": true,
  "file_path": "status-online.json",
  "update_interval": 30
},
"notifications": {
  "retry_attempts": 3,
  "retry_delay": 30,
  "cooldown_period": 300
}
```

---

## Usage

- **Docker (recommended)**: `./deploy.sh` or `docker compose up -d`. The process runs continuously and restarts on failure.
- **One-shot check** (e.g. for healthchecks): `python global-checker.py --once` — exit code 0 = all streams OK, 1 = at least one failed.

---

## Project structure

| File / directory | Purpose |
|------------------|---------|
| `global-checker.py` | Entry point; loads config, runs Icecast or Custom checker. |
| `icecast_checker.py` | Icecast checker: stats API, Telegram, status JSON, logging. |
| `custom_checker.py` | Custom checker (subclass): single JSON endpoint `{ mount: listeners }`. |
| `config.json` | Runtime config (gitignored). |
| `config_icecast_example.json` | Example config for Icecast. |
| `config_custom_example.json` | Example config for custom API. |
| `status-online.json` | Written by checker with current stream status. |
| `Dockerfile` | Image for running the checker. |
| `docker-compose.yml` | Service definition, volumes, healthcheck. |
| `deploy.sh` | Creates dirs, copies example config if needed, runs compose. |

---

## Logging

- Log files: date in name, e.g. `YYYY-MM-DD-icecast_check.log`.
- Levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`.
- Smart throttling: first 3 failures always logged; then every 10th attempt and every ~5 minutes for long outages.
- In Docker, logs also go to the container log (e.g. `docker compose logs -f`); rotation via compose `logging` options.

---

## Notifications

- **Down**: Sent when a stream goes from OK to not OK; cooldown between repeated down alerts for the same stream.
- **Recovery**: Sent as soon as a stream is back (no cooldown).
- **Periodic**: Reminder every N failed checks (e.g. 30) while a stream stays down.

Message content includes stream name, server, mount point, and (for recovery) listener count.

---

## Troubleshooting

| Symptom | What to check |
|--------|----------------|
| Connection refused | Server reachable? Port open? |
| Timeout | Increase `timeout`; check network. |
| HTTP 401 | Wrong `auth.username` / `auth.password`. |
| HTTP 403 | User has no access to stats. |
| HTTP 404 | Stats endpoint not enabled on server (e.g. `/status-json.xsl`). |
| JSON parse error | Server returning non-JSON or wrong format; for custom, ensure `{ "mount": number }`. |

**Manual checks:**

```bash
# HTTP
curl http://your-icecast-server:8000/status-json.xsl

# HTTPS
curl -k https://your-icecast-server:443/status-json.xsl

# With Basic Auth
curl -u username:password http://your-icecast-server:8000/status-json.xsl
```

Set `log_level` to `DEBUG` in config for more detail.

---

## Contributing

1. Fork the repository.
2. Create a branch for your change (`git checkout -b feature/your-feature`).
3. Commit and push; open a Pull Request with a clear description.

---

## License

See [LICENSE](LICENSE) in the repository root, if present. Otherwise contact the repository owner before reuse.
