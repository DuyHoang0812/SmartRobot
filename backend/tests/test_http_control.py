import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from sqlalchemy.orm import Session
from websockets.sync.client import connect

from app.schemas.control import DeviceReport
from app.services.device_control import DeviceControlService
from tests.test_auth import ORIGIN, accounts, auth_client, auth_settings, encoded_password
from tests.test_control import payload, rig

__all__ = ["accounts", "auth_client", "auth_settings", "encoded_password", "rig"]
pytestmark = pytest.mark.integration


def test_http_control_and_websocket_events_over_real_network(rig):
    rig["settings"].websocket_interval_seconds = 0.05
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                rig["client"].app,
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
                base_url=f"http://127.0.0.1:{port}",
                headers={"Origin": ORIGIN, "Authorization": f"Bearer {rig['token']}"},
            ) as client:
                url = f"ws://127.0.0.1:{port}/api/v1/ws/robots/{rig['robot_id']}"
                with connect(url, origin=ORIGIN, proxy=None) as ws:
                    ws.send(json.dumps({"type": "authenticate", "access_token": rig["token"]}))
                    assert json.loads(ws.recv(timeout=3))["type"] == "robot.state"
                    response = client.post(rig["base"] + "/acquire")
                    assert response.status_code == 201
                    grant = response.json()
                    current = client.get(rig["base"] + "/state").json()["command"]
                    with Session(rig["db"]) as db:
                        DeviceControlService(db, rig["settings"]).report(
                            "control-device",
                            rig["secret"],
                            DeviceReport(
                                sequence=current["sequence"],
                                generation=current["generation"],
                                acknowledgement="EXECUTED",
                                actual_mode="MANUAL",
                                movement="STOP",
                                safe_mode_switch=True,
                            ),
                        )
                    move = client.post(
                        rig["base"] + "/move", json=payload(grant, direction="FORWARD")
                    )
                    assert move.status_code == 202 and move.json()["status"] == "ACCEPTED"
                    stop = client.post(rig["base"] + "/stop", json=payload(grant, 2))
                    assert stop.status_code == 202
                    assert stop.json()["sequence"] > move.json()["sequence"]
                    for _ in range(20):
                        event = json.loads(ws.recv(timeout=3))
                        if (
                            event["type"] == "robot.state"
                            and event["data"]["sequence"] >= stop.json()["sequence"]
                        ):
                            assert event["data"]["actual_movement"] == "STOP"
                            break
                    else:
                        pytest.fail("No command event received")
                    assert (
                        client.post(
                            rig["base"] + "/release",
                            json={
                                "control_session_id": grant["id"],
                                "lease_token": grant["lease_token"],
                            },
                        ).status_code
                        == 204
                    )
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            assert not thread.is_alive()
