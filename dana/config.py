import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"
_PERSISTENT_ENV = (Path(os.environ["APPDATA"]) if os.name == "nt" and os.environ.get("APPDATA") else Path.home() / ".config") / "dana" / ".env"


def _persistent_auth_token() -> str:
    try:
        for line in _PERSISTENT_ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("DANA_AUTH_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "info"
    mcp_path: str = "/mcp"
    auth_token: str = _persistent_auth_token()
    public_host: str = ""
    public_port: int = 0
    public_scheme: str = ""
    deployment_mode: str = "local"
    workers: int = 5
    rate_limit_rpm: int = 120
    auth_burst: int = 20
    # ChatGPT connector access tokens are backed by Dana's static auth token.
    # Keep the advertised OAuth lifetime long so the connector does not force
    # a reconnect every hour while the underlying credential is still valid.
    oauth_access_token_ttl_seconds: int = 365 * 24 * 60 * 60
    max_body_bytes: int = 10 * 1024 * 1024
    # Dana is a local PC-control agent; desktop mutation tools are enabled by default.
    # Individual deployments can explicitly disable them with DANA_ALLOW_DANGEROUS_TOOLS=false.
    allow_dangerous_tools: bool = True
    allowed_origins: str = ""
    allowed_paths: str = ""
    denied_paths: str = ""
    tailscale_funnel_enabled: bool = True
    # Keep Dana's shared Tailscale path self-healing even when another local
    # application clears all handlers on port 443 while shutting down.
    tailscale_funnel_check_seconds: int = 2

    def normalized_workers(self) -> int:
        if not 1 <= self.workers <= 128:
            raise RuntimeError("DANA_WORKERS must be between 1 and 128.")
        return self.workers

    def normalized_mode(self) -> str:
        mode = self.deployment_mode.lower().strip()
        if mode not in {"local", "server"}:
            raise RuntimeError("DANA_DEPLOYMENT_MODE must be 'local' or 'server'.")
        return mode

    def require_auth_token(self) -> str:
        if not self.auth_token:
            raise RuntimeError(
                "DANA_AUTH_TOKEN is not configured. Run scripts/init_token.py first."
            )
        return self.auth_token

    model_config = SettingsConfigDict(
        env_file=(str(_ROOT_ENV), str(_PERSISTENT_ENV)), env_prefix="DANA_", extra="ignore"
    )


settings = Settings()
