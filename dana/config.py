
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "info"
    mcp_path: str = "/mcp"
    auth_token: str = ""

    def require_auth_token(self) -> str:
        if not self.auth_token:
            raise RuntimeError("DANA_AUTH_TOKEN is not configured. Run scripts/init_token.py first.")
        return self.auth_token

    model_config = SettingsConfigDict(env_file=".env", env_prefix="DANA_", extra="ignore")


settings = Settings()
