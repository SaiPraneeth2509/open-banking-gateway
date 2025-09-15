from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

_env_file = ".env" if Path(".env").exists() else None

class Settings(BaseSettings):
    APP_NAME: str = "auth-consent"
    APP_ENV: str = "dev"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    SKIP_JWT: bool = False
    EXPIRY_SWEEP_ENABLED: bool = True
    EXPIRY_SWEEP_SECONDS: int = 60
    USE_ALEMBIC: bool = True

    DATABASE_URL: str = "postgresql+psycopg2://bankuser:bankpass@postgres:5432/bankdb"
    REDIS_URL: str = "redis://redis:6379/0"
    KEYCLOAK_ISSUER: str = "http://localhost:8080/realms/obg-realm"
    KEYCLOAK_AUDIENCE: str = "obg-auth-consent"
    KEYCLOAK_WELLKNOWN_URL: str | None = None
    METRICS_ENABLED: bool = True
    METRICS_EXCLUDE_ROUTES: list[str] = ["/metrics", "/health"]

    model_config = SettingsConfigDict(env_file=_env_file, env_file_encoding="utf-8")

settings = Settings()
