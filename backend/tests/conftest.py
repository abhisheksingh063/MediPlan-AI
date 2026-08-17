"""Shared fixtures for database-layer tests.

Tests run against a dedicated ``mediplan_ai_test`` database so the development
database is never modified. The test schema is rebuilt from the ORM metadata
once per session; each test runs inside a transaction that is rolled back.
"""

import pytest
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (registers models on Base.metadata)
from app.core.config import settings
from app.models.base import Base

TEST_DATABASE_NAME = "mediplan_ai_test"


def test_database_url() -> str:
    """Return the database URL for the dedicated test database.

    ``render_as_string(hide_password=False)`` is required: the default
    ``str()`` on a SQLAlchemy URL masks the password with literal ``***``,
    which would be sent to the server as the password.
    """
    url = make_url(settings.resolved_database_url).set(database=TEST_DATABASE_NAME)
    return url.render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def engine():
    """Ensure the test database exists, then create the schema once."""
    admin_url = make_url(settings.resolved_database_url).set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": TEST_DATABASE_NAME},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DATABASE_NAME}"'))
    admin_engine.dispose()

    test_engine = create_engine(test_database_url())
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture()
def session(engine):
    """Provide a session whose writes are rolled back after each test.

    ``join_transaction_mode="create_savepoint"`` lets service-layer ``commit()``
    calls released inside nested savepoints so the outer transaction can still
    be rolled back at test teardown.
    """
    connection = engine.connect()
    transaction = connection.begin()
    test_session = sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint"
    )()
    try:
        yield test_session
    finally:
        test_session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture()
def client(session):
    """Provide a FastAPI TestClient whose requests share the test session."""
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)