import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from .config import settings
from .security.http import RequestGuard, audit, unauthorized
from .server import mcp

_guard = RequestGuard(settings.rate_limit_rpm, settings.auth_burst)
_raw_mcp_app = mcp.streamable_http_app()

# OAuth codes are short-lived and single-use. Reconnect remains independent
# from My_PC and external callback services.
_OAUTH_CODES: dict[str, dict[str, str | float]] = {}
_OAUTH_CODE_TTL_SECONDS = 120


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _cleanup_oauth_codes() -> None:
    now = time.time()
    for key in [key for key, value in _OAUTH_CODES.items() if float(value["expires_at"]) <= now]:
        _OAUTH_CODES.pop(key, None)


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

# FastMCP's Streamable HTTP manager owns an AnyIO task group which must be
# entered through the application's lifespan. Keep the FastMCP lifespan on
# the outer FastAPI app so every mounted /mcp request sees an initialized
# session manager, including requests arriving immediately after startup.
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
    endpoint = f"{scheme}://{host}{settings.mcp_path}" if settings.normalized_mode() == "server" else f"{scheme}://{host}/{token}{settings.mcp_path}"
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
    """OAuth 2.0 authorization-code endpoint with PKCE for ChatGPT reconnect."""
    params = request.query_params
    if params.get("response_type") != "code":
        raise HTTPException(status_code=400, detail="unsupported_response_type")
    redirect_uri = params.get("redirect_uri", "")
    client_id = params.get("client_id", "")
    challenge = params.get("code_challenge", "")
    method = params.get("code_challenge_method", "")
    state = params.get("state", "")
    if not redirect_uri or not client_id or not challenge or method != "S256":
        raise HTTPException(status_code=400, detail="invalid_authorization_request")
    if not redirect_uri.startswith("https://chatgpt.com/connector/oauth/"):
        raise HTTPException(status_code=400, detail="invalid_redirect_uri")
    _cleanup_oauth_codes()
    code = secrets.token_urlsafe(32)
    _OAUTH_CODES[code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "challenge": challenge,
        "expires_at": time.time() + _OAUTH_CODE_TTL_SECONDS,
    }
    query = urlencode({"code": code, "state": state})
    return RedirectResponse(url=f"{redirect_uri}?{query}", status_code=302)


@app.post("/token")
async def oauth_token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    code_verifier: str = Form(...),
):
    """Exchange a single-use authorization code and verify PKCE."""
    _cleanup_oauth_codes()
    record = _OAUTH_CODES.pop(code, None)
    if grant_type != "authorization_code" or record is None:
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    if record["redirect_uri"] != redirect_uri or record["client_id"] != client_id:
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    if not secrets.compare_digest(str(record["challenge"]), _pkce_challenge(code_verifier)):
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    token = settings.require_auth_token()
    # The bearer value is Dana's long-lived static auth token, so advertising
    # a one-hour OAuth lifetime would make ChatGPT discard an otherwise valid
    # connection and repeatedly ask the user to reconnect. Keep the advertised
    # lifetime aligned with the actual credential lifecycle.
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": settings.oauth_access_token_ttl_seconds,
        "scope": "mcp",
    }


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
        "grant_types_supported": ["authorization_code"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["mcp"],
    }


@app.get("/oauth-authorization-server")
async def oauth_authorization_server_alias(request: Request):
    """Alias for Tailscale path proxies that strip '/.well-known' before forwarding."""
    return await oauth_authorization_server(request)



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
    url = f"{scheme}://{host}{settings.mcp_path}" if settings.normalized_mode() == "server" else f"{scheme}://{host}/{token}{settings.mcp_path}"
    return {"title": "Chatbot Connection Link", "url": url}


@app.api_route("/{legacy_token}/mcp", methods=["GET", "POST", "DELETE"])
async def legacy_mcp_block(legacy_token: str):
    if settings.normalized_mode() == "server" and secrets.compare_digest(legacy_token, settings.require_auth_token()):
        return JSONResponse({"error": "Use canonical /mcp endpoint"}, status_code=401)
    return JSONResponse({"error": "Not Found"}, status_code=404)


# FastMCP already owns the /mcp route. Mounting it under /mcp would create
# /mcp/mcp, so the canonical transport is mounted at root. The public token is
# a Mount prefix; Starlette strips that prefix and FastMCP still receives /mcp.
# No BaseHTTPMiddleware sits in front of streaming responses.
token = settings.require_auth_token()
if settings.normalized_mode() != "server":
    app.mount(f"/{token}", mcp_app)
app.mount("/", mcp_app)
