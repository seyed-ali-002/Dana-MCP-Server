from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .security.http import RequestGuard, audit, unauthorized
from .server import mcp


_guard = RequestGuard(settings.rate_limit_rpm, settings.auth_burst)


class MCPCompatibilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        client_key = _guard.client_key(request)
        if not _guard.allow_request(client_key):
            return JSONResponse({"error": "Too Many Requests"}, status_code=429, headers={"Retry-After": "60"})

        # Reject oversized request bodies before they reach the MCP parser.
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.max_body_bytes:
                    return JSONResponse({"error": "Request body too large"}, status_code=413)
            except ValueError:
                return JSONResponse({"error": "Invalid Content-Length"}, status_code=400)

        # Tailscale Funnel may expose Dana behind a tokenized path while the
        # application itself serves the canonical /mcp endpoint. Normalize that
        # public prefix before FastMCP routing so both forms work.
        path = request.scope.get("path", "")
        token = settings.require_auth_token()
        token_prefix = f"/{token}"
        canonical_mcp = settings.mcp_path.rstrip("/") or "/mcp"
        tokenized = path == token_prefix or path.startswith(token_prefix + "/")
        if tokenized:
            # The prefix itself is the bearer secret. Constant-time comparison
            # keeps the direct HTTP form from leaking token length/content.
            supplied_prefix = path.split("/", 2)[1] if path.startswith("/") else ""
            if not _guard.token_matches(supplied_prefix, token):
                if not _guard.allow_auth_attempt(client_key):
                    return JSONResponse({"error": "Too Many Requests"}, status_code=429, headers={"Retry-After": "60"})
                audit("auth_failed", client_key, "tokenized_path")
                return unauthorized()
            request.scope["path"] = path[len(token_prefix):] or "/"
            path = request.scope["path"]
        elif path.rstrip("/").endswith("/mcp") and path.rstrip("/") != canonical_mcp:
            if not _guard.allow_auth_attempt(client_key):
                return JSONResponse({"error": "Too Many Requests"}, status_code=429, headers={"Retry-After": "60"})
            return unauthorized()

        # ChatGPT and other MCP clients may normalize the endpoint with a
        # trailing slash. FastMCP's canonical route is /mcp, so normalize both
        # /mcp and /mcp/ (including the tokenized public form) before routing.
        canonical_mcp = settings.mcp_path.rstrip("/") or "/mcp"
        if path.rstrip("/") == canonical_mcp:
            request.scope["path"] = canonical_mcp

        if settings.normalized_mode() == "server" and path.rstrip("/") == canonical_mcp:
            expected = f"Bearer {token}"
            if not _guard.token_matches(request.headers.get("authorization", ""), expected):
                if not _guard.allow_auth_attempt(client_key):
                    return JSONResponse({"error": "Too Many Requests"}, status_code=429, headers={"Retry-After": "60"})
                audit("auth_failed", client_key, "tokenized_path")
                return unauthorized()

        if settings.normalized_mode() == "server":
            # Server Mode is published by an HTTPS reverse proxy. The proxy
            # validates the tokenized public path and injects a Bearer token.
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


@app.get("/")
async def root(request: Request):
    host = settings.public_host or request.url.netloc
    scheme = "https" if settings.public_host else request.url.scheme
    token = settings.require_auth_token()
    endpoint = f"{scheme}://{host}/{token}{settings.mcp_path}"
    return {
        "name": "Dana MCP Server",
        "status": "ok",
        "description": "Dana is ready. Connect your MCP client using the tokenized mcp_endpoint URL below.",
        "mcp_endpoint": endpoint,
        "health_endpoint": f"{scheme}://{host}/health",
        "connector_endpoint": f"{scheme}://{host}/connector",
        "authentication": "Tokenized endpoint. Keep the MCP URL private.",
        "protocol": "streamable-http",
    }


@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    return JSONResponse({"issuer": "Dana MCP Server", "authorization_endpoint": None, "token_endpoint": None, "note": "Dana uses a tokenized MCP endpoint instead of OAuth."})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "Dana MCP Server", "mode": settings.normalized_mode(), "mcp_path": settings.mcp_path}


@app.get("/connector")
async def connector(request: Request):
    token = settings.require_auth_token()
    authorization = request.headers.get("authorization", "")
    expected = f"Bearer {token}"
    if not _guard.token_matches(authorization, expected):
        client_key = _guard.client_key(request)
        if not _guard.allow_auth_attempt(client_key):
            audit("auth_rate_limited", client_key, "connector")
            return JSONResponse({"error": "Too Many Requests"}, status_code=429, headers={"Retry-After": "60"})
        audit("auth_failed", client_key, "connector")
        return unauthorized()
    host = settings.public_host
    server_mode = settings.normalized_mode() == "server"
    if not host:
        host = "127.0.0.1:" + str(settings.port)
    if server_mode:
        scheme = "https"
        prefix = f"/{token}"
    else:
        scheme = "https" if settings.public_host else "http"
        prefix = f"/{token}"
    port_suffix = ""
    if settings.public_host and settings.public_port and settings.public_port not in (80, 443):
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
