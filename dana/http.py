import base64
import contextlib
import hashlib
import secrets
import time
from urllib.parse import urlencode, urlsplit

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from .config import settings
from .security.http import RequestGuard, audit, unauthorized
from .server import mcp

_guard = RequestGuard(settings.rate_limit_rpm, settings.auth_burst)


class RestartableMCPApp:
    """ASGI proxy that receives a fresh FastMCP transport on every app startup.

    StreamableHTTPSessionManager is intentionally single-use. Rebuilding the
    transport per lifespan makes graceful restarts and repeated TestClient
    lifecycles safe without sharing a closed AnyIO task group.
    """

    def __init__(self):
        self.app = None

    def set_app(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if self.app is None:
            response = JSONResponse({"error": "MCP transport is starting"}, status_code=503)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


_mcp_proxy = RestartableMCPApp()
_raw_mcp_app = None

# OAuth codes and dynamically registered public clients are intentionally
# process-local. Dana's bearer credential is the durable authentication secret;
# OAuth client registration only identifies a connector during an authorization
# flow and does not require users to create or paste a client ID manually.
_OAUTH_CODES: dict[str, dict[str, str | float]] = {}
_OAUTH_CLIENTS: dict[str, dict[str, object]] = {}
_OAUTH_CODE_TTL_SECONDS = 120


def _issuer(request: Request) -> str:
    host = settings.public_host or request.url.netloc
    scheme = "https" if settings.public_host else request.url.scheme
    return f"{scheme}://{host}"


def _cleanup_oauth_clients() -> None:
    # Registration metadata is deliberately bounded so a long-running public
    # server cannot accumulate abandoned connector registrations forever.
    cutoff = time.time() - (7 * 24 * 60 * 60)
    for client_id, value in list(_OAUTH_CLIENTS.items()):
        if float(value.get("created_at", 0)) < cutoff:
            _OAUTH_CLIENTS.pop(client_id, None)


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _cleanup_oauth_codes() -> None:
    now = time.time()
    for key in [key for key, value in _OAUTH_CODES.items() if float(value["expires_at"]) <= now]:
        _OAUTH_CODES.pop(key, None)


def _is_trusted_connector_redirect_uri(redirect_uri: str) -> bool:
    """Accept HTTPS OAuth callbacks from supported AI connector providers.

    Dana is a multi-client MCP server. Providers can change callback paths, so
    validation is origin-based and limited to trusted provider domains instead
    of pinning one UI-specific redirect path.
    """
    try:
        parsed = urlsplit(redirect_uri)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    trusted_domains = (
        "chatgpt.com",
        "chat.openai.com",
        "openai.com",
        "claude.ai",
        "anthropic.com",
        "grok.com",
        "x.ai",
        "x.com",
    )
    return parsed.scheme == "https" and any(
        host == domain or host.endswith(f".{domain}")
        for domain in trusted_domains
    )


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


class OAuthProtectedMCPASGI:
    """Require Dana OAuth bearer credentials on the canonical MCP transport."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("path", "") not in {"/mcp", "/mcp/"}:
            await self.app(scope, receive, send)
            return
        authorization = next((value.decode("latin1") for name, value in scope.get("headers", ()) if name.lower() == b"authorization"), "")
        expected = f"Bearer {settings.require_auth_token()}"
        if not _guard.token_matches(authorization, expected):
            host = settings.public_host or next((value.decode("latin1") for name, value in scope.get("headers", ()) if name.lower() == b"host"), "")
            scheme = "https" if settings.public_host else scope.get("scheme", "http")
            metadata = f'{scheme}://{host}/.well-known/oauth-protected-resource/mcp'
            response = JSONResponse(
                {"error": "unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": f'Bearer resource_metadata="{metadata}"'},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


mcp_app = OAuthProtectedMCPASGI(AcceptCompatibleASGI(_mcp_proxy))


class LocalTokenMCPASGI:
    """Compatibility transport for Dana Local Mode's secret URL."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if settings.normalized_mode() != "local":
            response = JSONResponse({"error": "Not Found"}, status_code=404)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

# FastMCP's Streamable HTTP manager owns an AnyIO task group which must be
# entered through the application's lifespan. Keep the FastMCP lifespan on
# the outer FastAPI app so every mounted /mcp request sees an initialized
# session manager, including requests arriving immediately after startup.
@contextlib.asynccontextmanager
async def _mcp_lifespan(app_instance):
    global _raw_mcp_app
    # A StreamableHTTPSessionManager cannot be entered twice. Create a fresh
    # FastMCP ASGI transport for every FastAPI lifespan instead of reusing the
    # previous manager after shutdown/restart.
    # FastMCP caches the session manager after the first transport is built,
    # but that manager is single-use. Discard the closed manager before every
    # new application lifespan so restart/test lifecycles get a fresh task group.
    mcp._session_manager = None
    raw_app = mcp.streamable_http_app()
    _raw_mcp_app = raw_app
    _mcp_proxy.set_app(raw_app)
    try:
        async with raw_app.router.lifespan_context(raw_app):
            yield
    finally:
        _mcp_proxy.set_app(None)
        if _raw_mcp_app is raw_app:
            _raw_mcp_app = None


app = FastAPI(
    title="Dana MCP Server",
    version="0.1.0",
    lifespan=_mcp_lifespan,
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
    endpoint = (
        f"{scheme}://{host}{settings.mcp_path}"
        if settings.normalized_mode() == "server"
        else f"{scheme}://{host}/{token}{settings.mcp_path}"
    )
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
    """OAuth 2.0 authorization-code endpoint with PKCE for supported connectors."""
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
    if not _is_trusted_connector_redirect_uri(redirect_uri):
        raise HTTPException(status_code=400, detail="invalid_redirect_uri")
    _cleanup_oauth_clients()
    registered = _OAUTH_CLIENTS.get(client_id)
    if registered is not None:
        registered_redirects = registered.get("redirect_uris", [])
        if redirect_uri not in registered_redirects:
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


@app.post("/register", status_code=201)
async def oauth_register(request: Request):
    """RFC 7591-style dynamic registration for public MCP OAuth clients."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_client_metadata"}, status_code=400)

    redirect_uris = payload.get("redirect_uris") if isinstance(payload, dict) else None
    if not isinstance(redirect_uris, list) or not redirect_uris:
        return JSONResponse({"error": "invalid_redirect_uri"}, status_code=400)
    if not all(isinstance(uri, str) and _is_trusted_connector_redirect_uri(uri) for uri in redirect_uris):
        return JSONResponse({"error": "invalid_redirect_uri"}, status_code=400)

    token_endpoint_auth_method = payload.get("token_endpoint_auth_method", "none")
    if token_endpoint_auth_method not in {"none", None}:
        return JSONResponse({"error": "invalid_client_metadata"}, status_code=400)

    _cleanup_oauth_clients()
    client_id = f"dana_{secrets.token_urlsafe(24)}"
    now = int(time.time())
    _OAUTH_CLIENTS[client_id] = {
        "redirect_uris": list(dict.fromkeys(redirect_uris)),
        "created_at": time.time(),
        "client_name": str(payload.get("client_name", "Dana MCP Client"))[:200],
    }
    return {
        "client_id": client_id,
        "client_id_issued_at": now,
        "redirect_uris": _OAUTH_CLIENTS[client_id]["redirect_uris"],
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
    }


@app.post("/oauth/register", status_code=201)
async def oauth_register_alias(request: Request):
    """Alias for path proxies that rewrite the public registration route."""
    return await oauth_register(request)


@app.get("/.well-known/oauth-protected-resource")
@app.get("/.well-known/oauth-protected-resource/mcp")
async def oauth_protected_resource(request: Request):
    """RFC 9728 metadata so MCP clients can discover Dana OAuth automatically."""
    host = settings.public_host or request.url.netloc
    scheme = "https" if settings.public_host else request.url.scheme
    issuer = f"{scheme}://{host}"
    return {
        "resource": f"{issuer}{settings.mcp_path}",
        "authorization_servers": [issuer],
        "bearer_methods_supported": ["header"],
        "scopes_supported": ["mcp"],
    }


@app.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server(request: Request):
    issuer = _issuer(request)
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/authorize",
        "token_endpoint": f"{issuer}/token",
        "registration_endpoint": f"{issuer}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "token_endpoint_auth_methods_supported": ["none"],
        "token_endpoint_auth_signing_alg_values_supported": [],
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
    url = (
        f"{scheme}://{host}{settings.mcp_path}"
        if settings.normalized_mode() == "server"
        else f"{scheme}://{host}/{token}{settings.mcp_path}"
    )
    return {"title": "Chatbot Connection Link", "url": url}


# Local mode deliberately keeps the token in the public URL. The tokenized
# mount is the compatibility contract used by existing Dana connectors: Starlette
# strips /<token>, then FastMCP receives the normal /mcp transport path.
# Server mode uses OAuth on the canonical /mcp endpoint instead.
token = settings.require_auth_token()
if settings.normalized_mode() == "local":
    app.mount(f"/{token}", LocalTokenMCPASGI(AcceptCompatibleASGI(_mcp_proxy)))
app.mount("/", mcp_app)
