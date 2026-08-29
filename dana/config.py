from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "info"
    mcp_path: str = "/mcp"
    auth_token: str = ""
    public_host: str = ""
    public_port: int = 0
    public_scheme: str = ""
    deployment_mode: str = "local"

    def normalized_mode(self) -> str:
        mode = self.deployment_mode.lower().strip()
        if mode not in {"local", "server"}:
            raise RuntimeError("DANA_DEPLOYMENT_MODE must be 'local' or 'server'.")
        return mode

    def require_auth_token(self) -> str:
        if not self.auth_token:
            raise RuntimeError("DANA_AUTH_TOKEN is not configured. Run scripts/init_token.py first.")
        return self.auth_token

    model_config = SettingsConfigDict(env_file=".env", env_prefix="DANA_", extra="ignore")


settings = Settings()
