from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .server import mcp


class TokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health" or request.url.path.startswith("/docs") or request.url.path in {"/openapi.json", "/redoc"}:
            return await call_next(request)
        authorization = request.headers.get("authorization", "")
        expected = f"Bearer {settings.require_auth_token()}"
        if authorization != expected:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


app = FastAPI(title="Dana MCP Server", version="0.1.0")
app.add_middleware(TokenMiddleware)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "dana-mcp"}


@app.get("/connector")
async def connector():
    token = settings.require_auth_token()
    host = settings.public_host or ("127.0.0.1:" + str(settings.port))
    scheme = "https" if settings.public_host else "http"
    return {"url": f"{scheme}://{host}{settings.mcp_path}", "authorization": f"Bearer {token}"}


# FastMCP owns the MCP protocol endpoint. Mounting preserves the standard /mcp path.
app.mount(settings.mcp_path, mcp.streamable_http_app())
