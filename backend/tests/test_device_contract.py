import secrets

import pytest
from starlette.requests import Request

from app.api.device_dependencies import credentials
from app.core.config import Settings
from app.core.errors import AppError


def settings(**changes):
    return Settings(
        _env_file=None, database_url="postgresql+psycopg://unused@localhost/unused_test", **changes
    )


@pytest.mark.parametrize(
    "host,allowed", [("192.168.1.20", True), ("127.0.0.1", True), ("8.8.8.8", False)]
)
def test_development_http_accepts_private_networks_only(host, allowed):
    request = Request(
        {
            "type": "http",
            "scheme": "http",
            "path": "/api/v1/devices/authenticate",
            "query_string": b"",
            "server": ("localhost", 8000),
            "client": (host, 1234),
            "headers": [(b"x-device-id", b"test-device"), (b"x-device-secret", b"x" * 64)],
        }
    )
    if allowed:
        assert (
            credentials(request, settings(device_allow_insecure_http=True)).device_id
            == "test-device"
        )
    else:
        with pytest.raises(AppError) as error:
            credentials(request, settings(device_allow_insecure_http=True))
        assert error.value.status_code == 403


def test_production_rejects_insecure_device_transport_configuration():
    with pytest.raises(ValueError, match="HTTPS"):
        settings(
            environment="production",
            device_allow_insecure_http=True,
            jwt_secret=secrets.token_urlsafe(48),
            cookie_secure=True,
            cors_origins=["https://example.test"],
        )
