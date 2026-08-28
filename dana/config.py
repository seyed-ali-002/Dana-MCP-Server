from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "info"
    mcp_path: str = "/mcp"
    auth_token: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="DANA_", extra="ignore")


settings = Settings()
