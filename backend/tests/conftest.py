import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.config import PROJECT_ROOT, get_settings
from tests.support import validate_test_database_url


def migration_config() -> Config:
    return Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))


@pytest.fixture(scope="session")
def test_database_url() -> URL:
    value = os.getenv("TEST_DATABASE_URL") or dotenv_values(PROJECT_ROOT / ".env.test").get(
        "TEST_DATABASE_URL"
    )
    if not value:
        pytest.fail("Set TEST_DATABASE_URL to a separate PostgreSQL *_test database; see README.")
    return validate_test_database_url(value, get_settings().database_url.get_secret_value())


@pytest.fixture
def empty_db_engine(test_database_url: URL) -> Iterator[Engine]:
    schema = f"test_{uuid4().hex}"
    admin_engine = create_engine(test_database_url, poolclass=NullPool, hide_parameters=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        test_database_url,
        poolclass=NullPool,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 5,
            "options": f"-csearch_path={schema} -ctimezone=UTC -cstatement_timeout=5000",
        },
    )
    try:
        yield engine
    finally:
        engine.dispose()
        # Only this randomly named schema in the guarded test DB is removed.
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def db_engine(empty_db_engine: Engine) -> Engine:
    with empty_db_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return empty_db_engine


@pytest.fixture
def db(db_engine: Engine) -> Iterator[Session]:
    with Session(db_engine) as session:
        yield session
