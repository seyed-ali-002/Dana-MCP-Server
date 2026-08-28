# Dana MCP Server

Cross-platform Python MCP server, completely independent from PHP, Apache, and Nginx. Dana listens on localhost; Tailscale Funnel provides the public HTTPS endpoint.

## Run

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/init_token.py
python -m dana.main
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python scripts/init_token.py
python -m dana.main
```

Dana listens on `http://127.0.0.1:8765`.

## Fixed authentication token

`python scripts/init_token.py` creates one persistent token on first setup and does not replace it on normal restarts. The token is stored in `.env`, which is ignored by Git.

Regenerate it explicitly:

```bash
python scripts/regenerate_token.py
```

Linux/macOS shortcut:

```bash
./scripts/regenerate_token.sh
```

Windows PowerShell:

```powershell
.\scripts\regenerate_token.ps1
```

Windows CMD:

```bat
scripts\regenerate_token.bat
```

Restart Dana after regeneration. Clients authenticate with `Authorization: Bearer <DANA_AUTH_TOKEN>`.

## Tailscale Funnel

Start Dana first, then expose it through Tailscale Funnel:

Linux/macOS:

```bash
./scripts/tailscale_linux.sh
```

Windows PowerShell:

```powershell
.\scripts\tailscale_windows.ps1
```

Or directly:

```bash
tailscale funnel --bg http://127.0.0.1:8765
tailscale funnel status
```

The public MCP URL is the HTTPS hostname shown by `tailscale funnel status`, followed by `/mcp`:

```text
https://<machine>.<tailnet>.ts.net/mcp
```

Tailscale handles public HTTPS. Dana remains bound to localhost, so PHP and other web servers are not involved.

## Endpoints

```text
GET  /health
POST /mcp
```

## Initial tools

- `system_info` — OS, architecture, Python version, and hostname.
- `list_directory` — native host filesystem directory listing.

## Tests

```bash
pytest -q
```

## Configuration

```text
DANA_HOST=127.0.0.1
DANA_PORT=8765
DANA_LOG_LEVEL=info
DANA_MCP_PATH=/mcp
DANA_AUTH_TOKEN=GENERATE_WITH_SCRIPT
```
