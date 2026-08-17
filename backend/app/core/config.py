"""Application configuration backed by the repository-level .env file.

Phase 4 established the environment-variable strategy (POSTGRES_* variables in
``.env.example``). This module reads those variables and exposes a single
resolved SQLAlchemy database URL. A full ``DATABASE_URL`` may optionally
override the composed value.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    """Type-safe access to backend environment configuration."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "MediPlan AI API"
    app_version: str = "0.1.0"

    postgres_db: str = "mediplan_ai"
    postgres_user: str = "mediplan_dev"
    postgres_password: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    database_url: str | None = None

    @property
    def resolved_database_url(self) -> str:
        """Return the effective SQLAlchemy PostgreSQL URL.

        Prefer an explicit ``DATABASE_URL`` when provided; otherwise compose the
        URL from the Phase 4 ``POSTGRES_*`` variables so credentials stay in the
        environment and never in source code.
        """
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()