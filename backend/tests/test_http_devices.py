import json
import socket
import threading
import time
from uuid import uuid4

import httpx
import pytest
import uvicorn
from websockets.sync.client import connect

from tests.test_auth import ORIGIN, accounts, auth_client, auth_settings, encoded_password
from tests.test_control import payload, rig
from tests.test_devices import BASE, ack_body, device

__all__ = ["accounts", "auth_client", "auth_settings", "encoded_password", "rig", "device"]
pytestmark = pytest.mark.integration


def test_device_http_and_websocket_telemetry_over_real_tcp(device):
    device["settings"].websocket_interval_seconds = 0.05
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                device["client"].app,
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
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as http:
                headers = {k: v for k, v in device["headers"].items() if k != "X-Device-Session"}
                boot = http.post(
                    BASE + "/authenticate",
                    headers=headers,
                    json={"boot_id": str(uuid4()), "firmware_version": "test-contract"},
                )
                assert boot.status_code == 200
                headers["X-Device-Session"] = boot.json()["device_session_id"]
                assert (
                    http.post(
                        BASE + "/heartbeat", headers=headers, json={"heartbeat_sequence": 1}
                    ).status_code
                    == 200
                )
                assert http.get(BASE + "/commands/current").status_code == 401
                with connect(
                    f"ws://127.0.0.1:{port}/api/v1/ws/robots/{device['robot_id']}",
                    origin=ORIGIN,
                    proxy=None,
                ) as ws:
                    ws.send(json.dumps({"type": "authenticate", "access_token": device["token"]}))
                    assert json.loads(ws.recv(timeout=3))["data"]["status"] == "ONLINE"
                    user = {"Authorization": f"Bearer {device['token']}"}
                    acquired = http.post(device["base"] + "/acquire", headers=user)
                    assert acquired.status_code == 201
                    command = http.get(BASE + "/commands/current", headers=headers).json()[
                        "command"
                    ]
                    assert (
                        http.post(
                            BASE + "/commands/ack",
                            headers=headers,
                            json=ack_body(command, safe=True),
                        ).status_code
                        == 200
                    )
                    move = http.post(
                        device["base"] + "/move",
                        headers=user,
                        json=payload(acquired.json(), direction="FORWARD"),
                    )
                    assert move.status_code == 202
                    command = http.get(BASE + "/commands/current", headers=headers).json()[
                        "command"
                    ]
                    assert command["command_id"] == move.json()["command_id"]
                    assert (
                        http.post(
                            BASE + "/commands/ack", headers=headers, json=ack_body(command)
                        ).status_code
                        == 200
                    )
                    body = {
                        "robot_id": str(device["robot_id"]),
                        "sample_sequence": 1,
                        "sequence": command["sequence"],
                        "generation": command["generation"],
                        "command_sequence_applied": command["sequence"],
                        "distance_cm": 8.5,
                        "obstacle_status": "BLOCKED",
                        "actual_mode": "MANUAL",
                        "actual_movement": "STOPPED",
                        "buzzer_active": True,
                    }
                    response = http.post(BASE + "/telemetry", headers=headers, json=body)
                    assert response.status_code == 200
                    assert http.post(BASE + "/telemetry", headers=headers, json=body).json()[
                        "duplicate"
                    ]
                    for _ in range(20):
                        event = json.loads(ws.recv(timeout=3))
                        if (
                            event["type"] == "robot.state"
                            and event["data"]["obstacle"] == "BLOCKED"
                        ):
                            assert event["data"]["distance_cm"] == 8.5 and event["data"]["buzzer"]
                            assert event["data"]["actual_movement"] == "STOP"
                            assert event["data"]["acknowledgement"]["status"] == "APPLIED"
                            break
                    else:
                        pytest.fail("No telemetry event received over WebSocket")
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            assert not thread.is_alive()
