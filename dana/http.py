from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .server import mcp


class MCPCompatibilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Tailscale Funnel may expose Dana behind a tokenized path while the
        # application itself serves the canonical /mcp endpoint. Normalize that
        # public prefix before FastMCP routing so both forms work.
        path = request.scope.get("path", "")
        token = settings.auth_token
        token_prefix = f"/{token}" if token else ""
        if token_prefix and path.startswith(token_prefix + "/"):
            request.scope["path"] = path[len(token_prefix):] or "/"
        if settings.normalized_mode() == "server":
            # Server Mode is published by an HTTPS reverse proxy as the canonical
            # /mcp endpoint. Do not put the secret token in the public URL.
            path = request.scope["path"].rstrip("/")
            if path.startswith("/") and path.endswith(settings.mcp_path.rstrip("/")):
                token = settings.require_auth_token()
                legacy_prefix = f"/{token}{settings.mcp_path}".rstrip("/")
                if path == legacy_prefix:
                    return JSONResponse({"error": "Unauthorized"}, status_code=401)
        if request.method == "GET" and request.url.path.rstrip("/").endswith("/mcp"):
            accept = request.headers.get("accept", "")
            if "text/event-stream" not in accept.lower():
                raw_headers = list(request.scope.get("headers", []))
                accept_value = accept.encode("latin-1")
                replaced = False
                for index, (key, value) in enumerate(raw_headers):
                    if key.lower() == b"accept":
                        raw_headers[index] = (
                            key,
                            value.rstrip(b" ,") + b", text/event-stream",
                        )
                        replaced = True
                        break
                if not replaced:
                    raw_headers.append(
                        (
                            b"accept",
                            accept_value + b", text/event-stream"
                            if accept_value
                            else b"text/event-stream",
                        )
                    )
                request.scope["headers"] = raw_headers
        return await call_next(request)


mcp_app = mcp.streamable_http_app()
app = FastAPI(
    title="Dana MCP Server",
    version="0.1.0",
    lifespan=mcp_app.router.lifespan_context,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "dana-mcp", "mode": settings.normalized_mode()}


@app.get("/connector")
async def connector(request: Request):
    token = settings.require_auth_token()
    authorization = request.headers.get("authorization", "")
    if authorization != f"Bearer {token}":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    host = settings.public_host
    server_mode = settings.normalized_mode() == "server"
    if not host:
        host = "127.0.0.1:" + str(settings.port)
    if server_mode:
        scheme = "https"
        prefix = ""
    else:
        scheme = "https" if settings.public_host else "http"
        prefix = f"/{token}"
    port_suffix = ""
    if settings.public_host and settings.public_port:
        port_suffix = f":{settings.public_port}"
    return {
        "title": "Chatbot Connection Link",
        "url": f"{scheme}://{host}{port_suffix}{prefix}{settings.mcp_path}",
    }


# Both deployment modes expose a tokenized public MCP path. In Server Mode
# the middleware strips that tokenized prefix before forwarding to FastMCP.
settings.require_auth_token()
# Tailscale Funnel mounts /<token> and forwards that mount to this local service.
# Funnel strips the mount prefix before proxying, so the local app must expose /mcp.
# Keep /health and /connector above this catch-all mount.
app.add_middleware(MCPCompatibilityMiddleware)
app.mount("/", mcp_app)
