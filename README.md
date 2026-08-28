# Dana MCP Server

Cross-platform Python MCP server, independent from PHP, Apache, and Nginx. Dana listens on localhost and Tailscale Funnel provides the public HTTPS endpoint.

## One-command startup

From the repository root, run one launcher.

Linux/macOS:

```bash
./run.sh
```

Windows:

```bat
run.bat
```

The launcher creates `.venv` when needed, installs dependencies, creates the persistent token, starts Dana, adds Dana to Tailscale Funnel under the token-specific path, discovers the public Funnel hostname, and prints the exact MCP Connector URL. It does not replace an existing Tailscale Funnel root route, so another service on the same machine can remain connected.

## Connector

Use the printed `MCP Connector URL` as the Custom Connector URL:

```text
https://<machine>.<tailnet>.ts.net/mcp
```

The token is embedded in the URL and acts as the connection credential. The Custom Connector must use the generated URL directly; no Authorization header is required for MCP requests.

An authenticated `GET /connector` endpoint returns the current connector URL.

## Token regeneration

```bash
python scripts/regenerate_token.py
```

or use the platform helper in `scripts/`.

Restart Dana after regenerating the token.

## Endpoints

```text
GET  /health
GET  /connector
POST /mcp
```

## Tests

```bash
pytest -q
```
