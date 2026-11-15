import socket
import threading
import time

import httpx
import pytest
import uvicorn

from app.api.dependencies import CSRF_COOKIE
from tests.test_auth import ORIGIN, PASSWORD, accounts, auth_client, auth_settings, encoded_password

pytestmark = pytest.mark.integration
# Reuse the same isolated PostgreSQL/auth fixtures as API integration tests.
__all__ = ["accounts", "auth_client", "auth_settings", "encoded_password"]


def test_real_http_authentication_round_trip(auth_client):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                auth_client.app,
                host="127.0.0.1",
                port=port,
                access_log=False,
                log_level="error",
                proxy_headers=False,
            )
        )
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert server.started, "Uvicorn did not start"
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", headers={"Origin": ORIGIN}
            ) as client:
                logged_in = client.post(
                    "/api/v1/auth/login",
                    json={
                        "identifier": "operator",
                        "password": PASSWORD,
                    },
                )
                assert logged_in.status_code == 200
                access = {"Authorization": f"Bearer {logged_in.json()['access_token']}"}
                assert client.get("/api/v1/auth/me", headers=access).status_code == 200
                assert client.get("/api/v1/admin/check", headers=access).status_code == 403
                csrf = {"X-CSRF-Token": client.cookies[CSRF_COOKIE]}
                assert client.post("/api/v1/auth/refresh", headers=csrf).status_code == 200
                assert client.post("/api/v1/auth/logout", headers=csrf).status_code == 204
                assert client.get("/api/v1/auth/me", headers=access).status_code == 401
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            assert not thread.is_alive(), "Uvicorn did not stop"
