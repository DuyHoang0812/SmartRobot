"""Create a separate local test database without modifying the development database."""

import os
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import PROJECT_ROOT, get_settings
from tests.support import validate_test_database_url


def main() -> None:
    development_url = get_settings().database_url.get_secret_value()
    development = make_url(development_url)
    test_url = development.set(database="smartrobot_test")
    validate_test_database_url(test_url.render_as_string(hide_password=False), development_url)
    env_path: Path = PROJECT_ROOT / ".env.test"
    if env_path.exists():
        raise SystemExit(".env.test already exists; keep its configuration and provision manually.")
    # The current PostgreSQL development role must have CREATEDB permission.
    connection_url = development.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(connection_url, autocommit=True, connect_timeout=5) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (test_url.database,)
        ).fetchone()
        if not exists:
            connection.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(test_url.database))
            )
    # The file contains a secret, so create it with owner-only permissions.
    with open(env_path, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as f:
        f.write(f"TEST_DATABASE_URL='{test_url.render_as_string(hide_password=False)}'\n")
    print("Test database ready: smartrobot_test; configuration saved to ignored .env.test")


if __name__ == "__main__":
    main()
