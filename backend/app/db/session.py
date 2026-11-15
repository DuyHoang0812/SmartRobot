from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def create_db_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_connect_timeout_seconds,
        connect_args={
            "connect_timeout": settings.db_connect_timeout_seconds,
            "options": f"-c statement_timeout={settings.db_statement_timeout_ms} -c timezone=UTC",
        },
        hide_parameters=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    # Services explicitly own commits; exceptions and uncommitted work roll back on close.
    with request.app.state.session_factory() as session:
        yield session
