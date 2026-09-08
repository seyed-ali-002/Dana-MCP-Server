from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import settings
from .security.http import RequestGuard, audit, unauthorized
from .server import mcp

_guard = RequestGuard(settings.rate_limit_rpm, settings.auth_burst)
_raw_mcp_app = mcp.streamable_http_app()


class AcceptCompatibleASGI:
    """Normalize MCP client Accept headers without buffering SSE responses.

    This is a low-level ASGI wrapper, intentionally not BaseHTTPMiddleware: it
    only adjusts the request scope before FastMCP sees it and passes streaming
    responses through untouched.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("method") == "GET":
            # Browser/test probes usually send */* or text/html. Keep real MCP
            # GET requests advertising text/event-stream untouched.
            accept = next(
                (
                    value.lower()
                    for name, value in scope.get("headers", ())
                    if name.lower() == b"accept"
                ),
                b"",
            )
            if b"text/event-stream" not in accept:
                response = JSONResponse(
                    {
                        "status": "ok",
                        "service": "Dana MCP Server",
                        "message": (
                            "Dana MCP endpoint is online. Connect with an MCP client "
                            "using Streamable HTTP; this response is shown because a "
                            "normal browser does not request the MCP event stream."
                        ),
                        "protocol": "streamable-http",
                        "endpoint": scope.get("path", ""),
                    }
                )
                await response(scope, receive, send)
                return

        if scope.get("type") == "http" and scope.get("method") == "POST":
            headers = list(scope.get("headers", ()))
            for index, (name, value) in enumerate(headers):
                if name.lower() != b"accept":
                    continue
                accepted = value.lower()
                if b"text/event-stream" not in accepted:
                    headers[index] = (name, value + b", text/event-stream")
                scope = {**scope, "headers": headers}
                break
            else:
                scope = {
                    **scope,
                    "headers": headers
                    + [(b"accept", b"application/json, text/event-stream")],
                }
        await self.app(scope, receive, send)


mcp_app = AcceptCompatibleASGI(_raw_mcp_app)

app = FastAPI(
    title="Dana MCP Server",
    version="0.1.0",
    lifespan=_raw_mcp_app.router.lifespan_context,
)


@app.get("/")
async def root(request: Request):
    # Tailscale path proxies strip their matched prefix before forwarding. The
    # public /authorize route can therefore arrive as /. Preserve the OAuth
    # query contract here so connector re-authentication remains Dana-owned.
    if request.query_params.get("response_type") == "code" and request.query_params.get("client_id"):
        return await authorize(request)
    host = settings.public_host or request.url.netloc
    scheme = "https" if settings.public_host else request.url.scheme
    token = settings.require_auth_token()
    endpoint = f"{scheme}://{host}/{token}{settings.mcp_path}"
    return {
        "name": "Dana MCP Server",
        "status": "ok",
        "description": "Dana is ready. Connect using the private tokenized MCP endpoint.",
        "mcp_endpoint": endpoint,
        "health_endpoint": f"{scheme}://{host}/health",
        "protocol": "streamable-http",
    }


@app.get("/authorize")
async def authorize(request: Request):
    """Dana-owned OAuth authorization entrypoint for connector re-authentication."""
    token = settings.require_auth_token()
    redirect_uri = request.query_params.get("redirect_uri", "")
    state = request.query_params.get("state", "")
    return JSONResponse(
        {
            "status": "authorization_required",
            "service": "Dana MCP Server",
            "message": "Dana is online and owns this authorization endpoint independently.",
            "authorization": "Use the configured Dana MCP connection token to continue.",
            "redirect_uri": redirect_uri,
            "state": state,
            "mcp_endpoint": f"/{token}{settings.mcp_path}",
        },
        status_code=200,
    )


@app.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server(request: Request):
    host = settings.public_host or request.url.netloc
    scheme = "https" if settings.public_host else request.url.scheme
    issuer = f"{scheme}://{host}"
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/authorize",
        "token_endpoint": f"{issuer}/token",
        "response_types_supported": ["code"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["mcp"],
    }


@app.get("/oauth-authorization-server")
async def oauth_authorization_server_alias(request: Request):
    """Alias for Tailscale path proxies that strip '/.well-known' before forwarding."""
    return await oauth_authorization_server(request)



@app.api_route("/token", methods=["GET", "POST"])
async def oauth_token():
    return JSONResponse(
        {
            "error": "authorization_pending",
            "error_description": "Dana authorization is handled by the connector's configured authentication flow.",
        },
        status_code=400,
    )



@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "Dana MCP Server",
        "mode": settings.normalized_mode(),
        "mcp_path": settings.mcp_path,
        "workers": settings.normalized_workers(),
    }


@app.get("/connector")
async def connector(request: Request):
    token = settings.require_auth_token()
    expected = f"Bearer {token}"
    if not _guard.token_matches(request.headers.get("authorization", ""), expected):
        client_key = _guard.client_key(request)
        if not _guard.allow_auth_attempt(client_key):
            return JSONResponse({"error": "Too Many Requests"}, status_code=429)
        audit("auth_failed", client_key, "connector")
        return unauthorized()
    host = settings.public_host or request.url.netloc
    scheme = "https" if settings.public_host else request.url.scheme
    return {"title": "Chatbot Connection Link", "url": f"{scheme}://{host}/{token}{settings.mcp_path}"}


# FastMCP already owns the /mcp route. Mounting it under /mcp would create
# /mcp/mcp, so the canonical transport is mounted at root. The public token is
# a Mount prefix; Starlette strips that prefix and FastMCP still receives /mcp.
# No BaseHTTPMiddleware sits in front of streaming responses.
token = settings.require_auth_token()
app.mount(f"/{token}", mcp_app)
app.mount("/", mcp_app)
