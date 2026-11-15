import re

from sqlalchemy.engine import URL, make_url


def validate_test_database_url(value: str, development_url: str) -> URL:
    url = make_url(value)
    development = make_url(development_url)
    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise ValueError("Tests require PostgreSQL")
    if not url.database or not re.fullmatch(r"[a-z0-9_]+_test", url.database):
        raise ValueError("Test database name must end with _test")
    # Refuse the development database name even through a different host alias.
    if url.database == development.database:
        raise ValueError("Test database must differ from development database")
    # A caller-supplied search_path must never redirect tests outside their isolated schema.
    if url.query:
        raise ValueError("Test database URL must not contain query parameters")
    return url.set(drivername="postgresql+psycopg")
