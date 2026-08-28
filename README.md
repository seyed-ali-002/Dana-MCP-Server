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

The launcher creates `.venv` when needed, installs dependencies, creates the persistent token, starts Dana, starts Tailscale Funnel, discovers the public Funnel hostname, and prints the exact MCP Connector URL and bearer token. Keep the terminal open while the server is running.

## Connector

Use the printed `MCP Connector URL` as the Custom Connector URL:

```text
https://<machine>.<tailnet>.ts.net/mcp
```

The launcher also prints the bearer token required by Dana authentication.

An authenticated `GET /connector` endpoint returns the current connector URL and authorization value.

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
