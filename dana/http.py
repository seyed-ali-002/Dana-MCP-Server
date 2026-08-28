from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import settings
from .server import mcp


mcp_app = mcp.streamable_http_app()
app = FastAPI(
    title="Dana MCP Server",
    version="0.1.0",
    lifespan=mcp_app.router.lifespan_context,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "dana-mcp"}


@app.get("/connector")
async def connector(request: Request):
    token = settings.require_auth_token()
    authorization = request.headers.get("authorization", "")
    if authorization != f"Bearer {token}":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    host = settings.public_host or ("127.0.0.1:" + str(settings.port))
    scheme = "https" if settings.public_host else "http"
    return {
        "title": "Chatbot Connection Link",
        "url": f"{scheme}://{host}/{token}{settings.mcp_path}",
    }


# The token is part of the MCP URL itself. The MCP app is mounted only below
# that secret prefix, so the connection URL authenticates without a header.
token = settings.require_auth_token()
app.mount(f"/{token}", mcp_app)
