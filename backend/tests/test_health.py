from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.db.session import get_db
from app.main import create_app


def test_liveness_does_not_connect_to_database():
    # Port 1 is intentionally unreachable; liveness must remain independent of PostgreSQL.
    application = create_app(
        Settings(_env_file=None, database_url="postgresql://localhost:1/unreachable")
    )
    with TestClient(application) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}
        assert client.get("/api/health").status_code == 200


def test_readiness_returns_503_without_driver_details():
    application = create_app(
        Settings(_env_file=None, database_url="postgresql://localhost:1/unreachable")
    )
    broken_session = Mock()
    broken_session.execute.side_effect = OperationalError("secret SQL", {}, Exception("password"))
    application.dependency_overrides[get_db] = lambda: broken_session
    with TestClient(application) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}


@pytest.mark.integration
def test_readiness_uses_real_postgres(test_database_url):
    application = create_app(
        Settings(
            _env_file=None, database_url=test_database_url.render_as_string(hide_password=False)
        )
    )
    with TestClient(application) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "ok"}
        assert client.get("/openapi.json").status_code == 200


def test_readiness_with_real_unreachable_database():
    application = create_app(
        Settings(_env_file=None, database_url="postgresql://localhost:1/unreachable")
    )
    with TestClient(application) as client:
        assert client.get("/api/v1/health/ready").status_code == 503
