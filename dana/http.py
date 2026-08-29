from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .server import mcp




class MCPCompatibilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if settings.normalized_mode() == "server" and request.url.path.rstrip("/") == settings.mcp_path.rstrip("/"):
            if request.headers.get("authorization", "") != f"Bearer {settings.require_auth_token()}":
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
        if request.method == "GET" and request.url.path.rstrip("/").endswith("/mcp"):
            accept = request.headers.get("accept", "")
            if "text/event-stream" not in accept.lower():
                raw_headers = list(request.scope.get("headers", []))
                accept_value = accept.encode("latin-1")
                replaced = False
                for index, (key, value) in enumerate(raw_headers):
                    if key.lower() == b"accept":
                        raw_headers[index] = (key, value.rstrip(b" ,") + b", text/event-stream")
                        replaced = True
                        break
                if not replaced:
                    raw_headers.append((b"accept", accept_value + b", text/event-stream" if accept_value else b"text/event-stream"))
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
    host = settings.public_host or ("127.0.0.1:" + str(settings.port))
    scheme = "https" if settings.public_host else "http"
    prefix = "" if settings.normalized_mode() == "server" else f"/{token}"
    return {
        "title": "Chatbot Connection Link",
        "url": f"{scheme}://{host}{prefix}{settings.mcp_path}",
    }


# Local mode keeps the token in the public Funnel path; server mode uses
# Authorization at the reverse-proxy/client boundary and exposes the canonical /mcp path.
settings.require_auth_token()
# Tailscale Funnel mounts /<token> and forwards that mount to this local service.
# Funnel strips the mount prefix before proxying, so the local app must expose /mcp.
# Keep /health and /connector above this catch-all mount.
app.add_middleware(MCPCompatibilityMiddleware)
app.mount("/", mcp_app)
