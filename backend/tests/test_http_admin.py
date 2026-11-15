import socket
import threading
import time

import httpx
import pytest
import uvicorn

from tests.test_auth import ORIGIN, PASSWORD, accounts, auth_client, auth_settings, encoded_password

__all__ = ["accounts", "auth_client", "auth_settings", "encoded_password"]
pytestmark = pytest.mark.integration


def test_admin_management_over_real_http(auth_client):
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
            assert server.started
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", headers={"Origin": ORIGIN}
            ) as client:
                response = client.post(
                    "/api/v1/auth/login", json={"identifier": "administrator", "password": PASSWORD}
                )
                assert response.status_code == 200
                client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
                created = client.post(
                    "/api/v1/admin/users",
                    json={
                        "username": "network_user",
                        "email": "network@example.com",
                        "password": PASSWORD,
                    },
                )
                assert created.status_code == 201
                user_id = created.json()["id"]
                assert (
                    client.patch(
                        f"/api/v1/admin/users/{user_id}/role", json={"role": "ADMIN"}
                    ).status_code
                    == 200
                )
                assert (
                    client.patch(
                        f"/api/v1/admin/users/{user_id}/status", json={"is_active": False}
                    ).status_code
                    == 200
                )
                robot = client.post(
                    "/api/v1/admin/robots",
                    json={"name": "HTTP robot", "device_id": "network-robot"},
                )
                assert robot.status_code == 201 and robot.json()["robot"]["status"] == "OFFLINE"
                robot_id = robot.json()["robot"]["id"]
                rotated = client.post(f"/api/v1/admin/robots/{robot_id}/credentials/rotate")
                assert rotated.status_code == 200
                assert rotated.json()["credential"] != robot.json()["credential"]
                listing = client.get("/api/v1/admin/robots")
                assert listing.status_code == 200 and "credential" not in listing.text
                assert listing.headers["cache-control"] == "no-store"
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            assert not thread.is_alive()
