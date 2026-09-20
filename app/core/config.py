"""Application configuration (12-factor, env based)."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_sqlalchemy_url(url: str) -> str:
    """Force an explicit psycopg3 driver so bare ``postgres://`` /
    ``postgresql://`` URLs (Render/Heroku-style) never fall back to
    the ``psycopg2`` dialect, which may not be installed.

    - ``postgres://...``            -> ``postgresql+psycopg://...``
    - ``postgresql://...``          -> ``postgresql+psycopg://...``
    - already explicit (``+psycopg`` / ``+psycopg2`` / ``+asyncpg``) -> unchanged
    - non-postgres URLs (sqlite for local tests, ...) -> unchanged
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def normalize_psycopg_url(url: str) -> str:
    """URL suitable for ``psycopg.connect()`` (psycopg v3 accepts the plain
    ``postgresql://`` scheme, not the SQLAlchemy ``+driver`` form)."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgresql+asyncpg://"):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix):]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Productivity OS"
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/productivity_os"
    # Sync URL used by the SQL auto-runner (psycopg3, DBAPI).
    # Empty by default so split deployments only need DATABASE_URL.
    SYNC_DATABASE_URL: str = ""
    SECRET_KEY: str = "change-me-to-a-long-random-secret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    AUTO_RUN_SQL: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        """DATABASE_URL normalised to an explicit-driver SQLAlchemy URL."""
        return normalize_sqlalchemy_url(self.DATABASE_URL)

    @property
    def psycopg_url(self) -> str:
        """SYNC_DATABASE_URL normalised for psycopg v3 connections.

        Falls back to DATABASE_URL when SYNC_DATABASE_URL is unset, so a
        split deployment only needs to set one variable.
        """
        raw = self.SYNC_DATABASE_URL or self.DATABASE_URL
        return normalize_psycopg_url(raw)


@lru_cache
def get_settings() -> Settings:
    return Settings()
