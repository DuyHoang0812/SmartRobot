import socket
import threading
import time
from uuid import uuid4

import httpx
import pytest
import uvicorn
from sqlalchemy.orm import Session

from tests.test_auth import ORIGIN, PASSWORD, accounts, auth_client, auth_settings, encoded_password
from tests.test_database import add_robot

__all__ = ["accounts", "auth_client", "auth_settings", "encoded_password"]
pytestmark = pytest.mark.integration


def test_user_robot_apis_over_real_http(auth_client, db_engine):
    with Session(db_engine) as db:
        robot = add_robot(db, name="Xe HTTP")
        disabled = add_robot(db, is_active=False)
        robot_id, disabled_id = str(robot.id), str(disabled.id)
        db.commit()
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
                assert client.get("/api/v1/robots").status_code == 401
                login = client.post(
                    "/api/v1/auth/login", json={"identifier": "operator", "password": PASSWORD}
                )
                assert login.status_code == 200
                client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
                response = client.get("/api/v1/robots")
                assert response.status_code == 200 and response.json()["total"] == 1
                assert response.headers["cache-control"] == "no-store"
                detail = client.get(f"/api/v1/robots/{robot_id}")
                assert detail.status_code == 200
                assert detail.json()["status"] == "OFFLINE" and not detail.json()["available"]
                assert "credential" not in detail.text
                assert client.get(f"/api/v1/robots/{disabled_id}").status_code == 404
                assert client.get(f"/api/v1/robots/{uuid4()}").status_code == 404
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            assert not thread.is_alive()
