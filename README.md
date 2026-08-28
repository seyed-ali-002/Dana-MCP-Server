# Dana MCP Server

Cross-platform Python MCP server designed to run independently from PHP, Apache, and Nginx. Tailscale Funnel is used only as the public HTTPS transport; Dana itself listens on localhost.

## Architecture

```text
Internet
   |
   v
Tailscale Funnel (HTTPS)
   |
   v
127.0.0.1:8765
   |
   v
Dana / Python / FastAPI
   |
   +--> MCP endpoint: /mcp
   +--> health endpoint: /health
   +--> platform-aware tools
```

The same architecture works on Linux and Windows. No PHP integration is required.

## Requirements

- Python 3.11+
- Tailscale installed and authenticated on the host
- Tailscale Funnel enabled for the tailnet/account

## Install

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env  # Linux/macOS
```

On Windows, copy `.env.example` to `.env` manually or with PowerShell.

Set a real token in `.env`:

```text
DANA_AUTH_TOKEN=replace-with-a-long-random-token
```

If `DANA_AUTH_TOKEN` is empty, authentication is disabled. Keep it set for any public Funnel deployment.

## Run Dana

```bash
python -m dana.main
```

Default listener:

```text
http://127.0.0.1:8765
```

Health check:

```text
http://127.0.0.1:8765/health
```

MCP endpoint:

```text
http://127.0.0.1:8765/mcp
```

## Enable Tailscale Funnel

With Dana already running:

### Linux

```bash
./scripts/tailscale_linux.sh
```

### Windows PowerShell

```powershell
.\scripts\tailscale_windows.ps1
```

Or run Tailscale directly:

```bash
tailscale funnel --bg http://127.0.0.1:8765
tailscale funnel status
```

Tailscale provides the public HTTPS hostname. Do not make Uvicorn listen on `0.0.0.0` unless there is a specific need; keeping Dana on `127.0.0.1` prevents accidental direct exposure.

## Authentication

Dana uses a bearer token middleware for HTTP requests except `/health`.

Clients must send:

```http
Authorization: Bearer <DANA_AUTH_TOKEN>
```

The token is deliberately kept outside source control in `.env`.

## Tools

The initial implementation includes:

- `system_info` — host OS, architecture, Python version, and hostname.
- `list_directory` — list entries in a directory using the native host filesystem.

Platform-specific tools should be added behind the platform abstraction rather than hard-coding Linux commands into MCP handlers.

## Development

```bash
pytest -q
```

The project is intentionally independent from PHP. Do not add Composer, Laravel, Apache, or Nginx runtime dependencies to this repository.
