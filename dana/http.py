from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .server import mcp


class TokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health" or not settings.auth_token:
            return await call_next(request)

        authorization = request.headers.get("authorization", "")
        expected = f"Bearer {settings.auth_token}"
        if authorization != expected:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


app = FastAPI(title="Dana MCP Server", version="0.1.0")
app.add_middleware(TokenMiddleware)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "dana-mcp"}


# FastMCP owns the MCP protocol endpoint. Mounting preserves the standard /mcp path.
app.mount(settings.mcp_path, mcp.streamable_http_app())
