"""SQLAlchemy engine, session factory, and request-scoped dependency.

This is the persistence plumbing shared by all API routers. The connection URL
is resolved from ``app.core.config.Settings`` (environment-driven, never
hard-coded).
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.resolved_database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()