import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import jwt
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import ControlSession, Robot, RobotCommand
from app.models.control import CommandKind, CommandStatus, Direction
from app.schemas.control import ActionInput, DeviceReport
from app.services.auth import AuthService
from app.services.control import ControlActor, ControlService
from app.services.device_control import DeviceControlService
from app.services.device_credentials import generate_device_credential
from tests.test_auth import (
    PASSWORD,
    accounts,
    auth_client,
    auth_settings,
    bearer,
    csrf,
    encoded_password,
    login,
)
from tests.test_database import add_robot

__all__ = ["accounts", "auth_client", "auth_settings", "encoded_password"]
pytestmark = pytest.mark.integration


@pytest.fixture
def rig(auth_client, db_engine, auth_settings):
    response = login(auth_client)
    token = response.json()["access_token"]
    claims = jwt.decode(token, options={"verify_signature": False})
    actor = ControlActor(UUID(claims["sub"]), UUID(claims["sid"]))
    auth_client.headers.update(bearer(response))
    credential = generate_device_credential()
    with Session(db_engine) as db:
        robot = add_robot(
            db,
            device_id="control-device",
            device_credential_hash=credential.hashed,
            last_seen_at=datetime.now(UTC),
        )
        robot_id = robot.id
        db.commit()
    return {
        "client": auth_client,
        "db": db_engine,
        "settings": auth_settings,
        "actor": actor,
        "robot_id": robot_id,
        "secret": credential.secret,
        "token": token,
        "base": f"/api/v1/robots/{robot_id}/control",
    }


def acquire(rig):
    response = rig["client"].post(rig["base"] + "/acquire")
    assert response.status_code == 201
    return response.json()


def payload(grant, sequence=1, **extra):
    return {
        "control_session_id": grant["id"],
        "lease_token": grant["lease_token"],
        "request_id": str(uuid4()),
        "client_sequence": sequence,
        **extra,
    }


def acknowledge(rig, mode="MANUAL", **extra):
    with Session(rig["db"]) as db:
        service = DeviceControlService(db, rig["settings"])
        current = service.current_command("control-device", rig["secret"])
        service.report(
            "control-device",
            rig["secret"],
            DeviceReport(
                sequence=current.sequence,
                generation=current.generation,
                acknowledgement="EXECUTED",
                actual_mode=mode,
                movement="STOP",
                safe_mode_switch=True,
                **extra,
            ),
        )


def test_acquire_is_exclusive_and_unknown_state_is_not_execution(rig):
    grant = acquire(rig)
    assert grant["owned"] and len(grant["lease_token"]) >= 64
    assert grant["renew_after_ms"] <= rig["settings"].mode_command_ttl_ms // 2
    resumed = acquire(rig)
    assert resumed["id"] == grant["id"] and resumed["lease_token"] != grant["lease_token"]
    state = rig["client"].get(rig["base"] + "/state").json()
    assert state["actual_mode"] is None and state["actual_movement"] is None
    assert state["mode_pending"] and state["command"]["status"] == "ACCEPTED"
    assert state["obstacle"] is None and state["distance_cm"] is None and state["buzzer"] is None
    assert "lease_token" not in str(state)


def test_renew_and_release(rig):
    grant = acquire(rig)
    response = rig["client"].post(rig["base"] + "/renew", json={k: grant[k] for k in ["id"]} | {})
    assert response.status_code == 422
    lease_body = {"control_session_id": grant["id"], "lease_token": grant["lease_token"]}
    renewed = rig["client"].post(rig["base"] + "/renew", json=lease_body)
    assert renewed.status_code == 200
    assert renewed.json()["expires_at"] is None and grant["expires_at"] is None
    assert rig["client"].post(rig["base"] + "/release", json=lease_body).status_code == 204
    assert not rig["client"].get(rig["base"] + "/session").json()["owned"]
    assert (
        rig["client"]
        .post(rig["base"] + "/move", json=payload(grant, direction="FORWARD"))
        .status_code
        == 403
    )


def test_offline_or_disabled_robot_cannot_be_acquired(rig):
    with Session(rig["db"]) as db:
        db.get(Robot, rig["robot_id"]).last_seen_at = None
        db.commit()
    assert rig["client"].post(rig["base"] + "/acquire").status_code == 409
    with Session(rig["db"]) as db:
        db.get(Robot, rig["robot_id"]).is_active = False
        db.commit()
    assert rig["client"].post(rig["base"] + "/acquire").status_code == 409


def test_wrong_lease_owner_and_secret_are_rejected(rig):
    grant = acquire(rig)
    bad = payload(grant, direction="FORWARD", lease_token=secrets.token_urlsafe(48))
    assert rig["client"].post(rig["base"] + "/move", json=bad).status_code == 403
    access = bearer(login(rig["client"], "administrator"))
    assert (
        rig["client"]
        .post(rig["base"] + "/move", headers=access, json=payload(grant, direction="FORWARD"))
        .status_code
        == 403
    )
    state = rig["client"].get(rig["base"] + "/state", headers=access).json()
    assert state["lease"]["id"] is None and state["command"] is None


@pytest.mark.parametrize("direction", ["FORWARD", "BACKWARD", "TURN_LEFT", "TURN_RIGHT"])
def test_manual_directions_require_safe_ack_then_are_accepted(rig, direction):
    grant = acquire(rig)
    body = payload(grant, direction=direction)
    assert rig["client"].post(rig["base"] + "/move", json=body).status_code == 409
    acknowledge(rig)
    command = rig["client"].post(rig["base"] + "/move", json=body)
    assert command.status_code == 202 and command.json()["direction"] == direction
    state = rig["client"].get(rig["base"] + "/state").json()
    assert state["actual_movement"] == "STOP"  # Accepted movement is not actual execution.
    assert command.json()["status"] == "ACCEPTED"


def test_stop_and_mode_fence_old_moves(rig):
    grant = acquire(rig)
    acknowledge(rig)
    moved = (
        rig["client"]
        .post(rig["base"] + "/move", json=payload(grant, 1, direction="FORWARD"))
        .json()
    )
    stop = rig["client"].post(rig["base"] + "/stop", json=payload(grant, 2))
    assert stop.status_code == 202 and stop.json()["sequence"] > moved["sequence"]
    with Session(rig["db"]) as db:
        assert db.get(RobotCommand, moved["command_id"]).status == CommandStatus.SUPERSEDED
    auto = rig["client"].post(rig["base"] + "/mode", json=payload(grant, 3, mode="AUTO"))
    assert auto.status_code == 202
    state = rig["client"].get(rig["base"] + "/state").json()
    assert (
        state["requested_mode"] == "AUTO"
        and state["actual_mode"] == "MANUAL"
        and state["mode_pending"]
    )
    assert (
        rig["client"]
        .post(rig["base"] + "/move", json=payload(grant, 4, direction="BACKWARD"))
        .status_code
        == 409
    )


def test_auto_to_manual_requires_device_safe_confirmation(rig):
    grant = acquire(rig)
    acknowledge(rig)
    assert (
        rig["client"].post(rig["base"] + "/mode", json=payload(grant, 1, mode="AUTO")).status_code
        == 202
    )
    acknowledge(rig, "AUTO")
    rig["client"].post(rig["base"] + "/mode", json=payload(grant, 2, mode="MANUAL"))
    assert (
        rig["client"]
        .post(rig["base"] + "/move", json=payload(grant, 3, direction="FORWARD"))
        .status_code
        == 409
    )
    acknowledge(rig, "MANUAL")
    assert (
        rig["client"]
        .post(rig["base"] + "/move", json=payload(grant, 3, direction="FORWARD"))
        .status_code
        == 202
    )


def test_auto_renew_produces_bounded_permission(rig):
    grant = acquire(rig)
    acknowledge(rig)
    rig["client"].post(rig["base"] + "/mode", json=payload(grant, 1, mode="AUTO"))
    acknowledge(rig, "AUTO")
    response = rig["client"].post(
        rig["base"] + "/renew",
        json={"control_session_id": grant["id"], "lease_token": grant["lease_token"]},
    )
    assert response.status_code == 200
    state = rig["client"].get(rig["base"] + "/state").json()
    assert state["command"]["kind"] == "KEEPALIVE"
    issued, expires = [
        datetime.fromisoformat(state["command"][key]) for key in ["issued_at", "expires_at"]
    ]
    assert (expires - issued).total_seconds() <= 3


def test_idempotency_and_client_ordering(rig):
    grant = acquire(rig)
    acknowledge(rig)
    body = payload(grant, 1, direction="FORWARD")
    first = rig["client"].post(rig["base"] + "/move", json=body).json()
    duplicate = rig["client"].post(rig["base"] + "/move", json=body).json()
    assert (
        first["command_id"] == duplicate["command_id"]
        and first["sequence"] == duplicate["sequence"]
    )
    assert (
        rig["client"].post(rig["base"] + "/move", json=body | {"direction": "BACKWARD"}).status_code
        == 409
    )
    rig["client"].post(rig["base"] + "/stop", json=payload(grant, 3))
    assert (
        rig["client"]
        .post(rig["base"] + "/move", json=payload(grant, 2, direction="FORWARD"))
        .status_code
        == 409
    )
    replay = rig["client"].post(rig["base"] + "/move", json=body).json()
    assert replay["status"] == "SUPERSEDED"


def test_manual_ttl_and_history_bounds(rig):
    grant = acquire(rig)
    acknowledge(rig)
    first = (
        rig["client"]
        .post(rig["base"] + "/move", json=payload(grant, 1, direction="FORWARD"))
        .json()
    )
    assert (
        datetime.fromisoformat(first["expires_at"]) - datetime.fromisoformat(first["issued_at"])
    ).total_seconds() == 0.7
    with Session(rig["db"]) as db:
        command = db.get(RobotCommand, first["command_id"])
        command.issued_at = datetime.now(UTC) - timedelta(seconds=5)
        command.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        assert (
            DeviceControlService(db, rig["settings"]).current_command(
                "control-device", rig["secret"]
            )
            is None
        )
        envelope = DeviceControlService(db, rig["settings"]).command_envelope(
            "control-device", rig["secret"]
        )
        assert envelope.command is None and envelope.fail_safe == "STOP"
        assert envelope.sequence == first["sequence"]
    rig["settings"].command_history_limit = 10
    for seq in range(2, 15):
        assert (
            rig["client"].post(rig["base"] + "/stop", json=payload(grant, seq)).status_code == 202
        )
    with Session(rig["db"]) as db:
        assert db.scalar(select(func.count()).select_from(RobotCommand)) <= 10


def test_idle_borrow_survives_cleanup_and_same_user_can_resume(rig):
    grant = acquire(rig)
    with Session(rig["db"]) as db:
        lease = db.get(ControlSession, grant["id"])
        lease.started_at = datetime.now(UTC) - timedelta(days=2)
        assert lease.expires_at is None
        db.commit()
        ControlService(db, rig["settings"]).cleanup()
        assert db.get(ControlSession, grant["id"], populate_existing=True).ended_at is None
    second = acquire(rig)
    assert second["id"] == grant["id"]


def test_new_login_can_resume_borrow_but_old_browser_credentials_are_fenced(rig):
    grant = acquire(rig)
    assert rig["client"].post("/api/v1/auth/logout", headers=csrf(rig["client"])).status_code == 204
    access = bearer(login(rig["client"], "operator"))
    state = rig["client"].get(rig["base"] + "/state", headers=access).json()
    assert state["lease"]["id"] == grant["id"] and state["lease"]["owned"]
    resumed = rig["client"].post(rig["base"] + "/acquire", headers=access)
    assert resumed.status_code == 201
    assert resumed.json()["id"] == grant["id"]
    assert resumed.json()["lease_token"] != grant["lease_token"]
    assert (
        rig["client"].post(rig["base"] + "/stop", headers=access, json=payload(grant)).status_code
        == 403
    )
    assert (
        rig["client"]
        .post(rig["base"] + "/stop", headers=access, json=payload(resumed.json()))
        .status_code
        == 202
    )


def test_borrower_can_resume_and_return_an_offline_robot(rig):
    grant = acquire(rig)
    with Session(rig["db"]) as db:
        db.get(Robot, rig["robot_id"]).last_seen_at = None
        db.commit()
    resumed = acquire(rig)
    assert resumed["id"] == grant["id"]
    assert (
        rig["client"]
        .post(
            rig["base"] + "/release",
            json={"control_session_id": resumed["id"], "lease_token": resumed["lease_token"]},
        )
        .status_code
        == 204
    )
    assert not rig["client"].get(rig["base"] + "/session").json()["owned"]


def test_acknowledged_idle_manual_keeps_lease_after_mode_command_ttl(rig):
    grant = acquire(rig)
    acknowledge(rig)
    with Session(rig["db"]) as db:
        command = db.scalars(
            select(RobotCommand).where(RobotCommand.robot_id == rig["robot_id"])
        ).one()
        command.issued_at = datetime.now(UTC) - timedelta(seconds=5)
        command.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    state = rig["client"].get(rig["base"] + "/state").json()
    assert state["lease"]["id"] == grant["id"] and state["lease"]["owned"]
    assert not state["mode_pending"] and state["command"]["status"] == "EXPIRED"
    assert (
        rig["client"]
        .post(rig["base"] + "/move", json=payload(grant, direction="FORWARD"))
        .status_code
        == 202
    )


def test_logout_stops_commands_but_keeps_borrow_in_database(rig):
    grant = acquire(rig)
    acknowledge(rig)
    rig["client"].post(rig["base"] + "/move", json=payload(grant, direction="FORWARD"))
    assert rig["client"].post("/api/v1/auth/logout", headers=csrf(rig["client"])).status_code == 204
    with Session(rig["db"]) as db:
        assert db.get(ControlSession, grant["id"]).ended_at is None
        assert not list(
            db.scalars(select(RobotCommand).where(RobotCommand.status == CommandStatus.ACCEPTED))
        )


def test_robot_disable_and_credential_rotation_fence_commands(rig):
    grant = acquire(rig)
    admin = bearer(login(rig["client"], "administrator"))
    response = rig["client"].patch(
        f"/api/v1/admin/robots/{rig['robot_id']}/status", headers=admin, json={"is_active": False}
    )
    assert response.status_code == 200
    with Session(rig["db"]) as db:
        assert db.get(ControlSession, grant["id"]).ended_at is not None
    assert rig["client"].get(rig["base"] + "/state").status_code == 404


def test_concurrent_acquire_allows_only_one_user(rig, accounts):
    with Session(rig["db"]) as db:
        second = AuthService(db, rig["settings"]).login("administrator", PASSWORD, "test-admin")
        sid = jwt.decode(second.access_token, options={"verify_signature": False})["sid"]
    actors = [rig["actor"], ControlActor(accounts["admin"], UUID(sid))]
    barrier = Barrier(2)

    def attempt(actor):
        with Session(rig["db"]) as db:
            barrier.wait(timeout=5)
            try:
                ControlService(db, rig["settings"]).acquire(rig["robot_id"], actor)
                return 201
            except AppError as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, actors)) == [201, 409]


def test_move_stop_race_never_resurrects_old_move(rig):
    grant = acquire(rig)
    acknowledge(rig)
    barrier = Barrier(2)

    def send(stop):
        with Session(rig["db"]) as db:
            barrier.wait(timeout=5)
            body = ActionInput.model_validate(payload(grant, 2 if stop else 1))
            try:
                ControlService(db, rig["settings"]).action(
                    rig["robot_id"],
                    rig["actor"],
                    body,
                    CommandKind.STOP if stop else CommandKind.MOVE,
                    Direction.STOP if stop else Direction.FORWARD,
                )
            except AppError as error:
                assert error.status_code == 409

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(send, [False, True]))
    state = rig["client"].get(rig["base"] + "/state").json()
    assert state["command"]["direction"] == "STOP"


@pytest.mark.parametrize("obstacle", ["CLEAR", "BLOCKED", "SENSOR_ERROR"])
def test_obstacle_contract_is_device_reported(rig, obstacle):
    acquire(rig)
    acknowledge(
        rig,
        obstacle=obstacle,
        distance_cm=10 if obstacle == "BLOCKED" else None,
        buzzer=obstacle == "BLOCKED",
    )
    state = rig["client"].get(rig["base"] + "/state").json()
    assert state["obstacle"] == obstacle and state["telemetry_fresh"]
    assert state["actual_movement"] == "STOP"


def test_invalid_sensor_data_is_rejected():
    for distance in [-1, float("nan"), float("inf")]:
        with pytest.raises(ValidationError):
            DeviceReport(
                sequence=1,
                generation=0,
                acknowledgement="EXECUTED",
                actual_mode="MANUAL",
                movement="STOP",
                distance_cm=distance,
            )


def test_stale_ack_and_unauthenticated_device_are_rejected(rig):
    grant = acquire(rig)
    old = rig["client"].get(rig["base"] + "/state").json()["command"]
    rig["client"].post(rig["base"] + "/mode", json=payload(grant, mode="AUTO"))
    with Session(rig["db"]) as db:
        with pytest.raises(AppError):
            DeviceControlService(db, rig["settings"]).report(
                "control-device",
                rig["secret"],
                DeviceReport(
                    sequence=old["sequence"],
                    generation=old["generation"],
                    acknowledgement="EXECUTED",
                    actual_mode="MANUAL",
                    movement="STOP",
                ),
            )
        with pytest.raises(AppError):
            DeviceControlService(db, rig["settings"]).current_command("control-device", "bad")


def test_websocket_authentication_and_reconnect(rig):
    headers = {"Origin": "http://localhost:5173"}
    path = f"/api/v1/ws/robots/{rig['robot_id']}"
    for _ in range(2):
        with rig["client"].websocket_connect(path, headers=headers) as ws:
            ws.send_json({"type": "authenticate", "access_token": rig["token"]})
            event = ws.receive_json()
            assert event["type"] == "robot.state" and event["data"]["robot_id"] == str(
                rig["robot_id"]
            )
            assert "lease_token" not in str(event)


def test_websocket_disconnect_keeps_owned_borrow_and_fences_motion(rig):
    grant = acquire(rig)
    with rig["client"].websocket_connect(
        f"/api/v1/ws/robots/{rig['robot_id']}", headers={"Origin": "http://localhost:5173"}
    ) as ws:
        ws.send_json({"type": "authenticate", "access_token": rig["token"]})
        assert ws.receive_json()["data"]["lease"]["owned"]
    with Session(rig["db"]) as db:
        assert db.get(ControlSession, grant["id"]).ended_at is None
    state = rig["client"].get(rig["base"] + "/state").json()
    assert state["lease"]["owned"] and state["mode_pending"]
    assert state["command"]["status"] == "SUPERSEDED"


@pytest.mark.parametrize(
    "case,code", [("bad-token", 4001), ("inactive", 4003), ("origin", 1008), ("url-token", 1008)]
)
def test_websocket_access_is_checked(rig, case, code):
    from starlette.websockets import WebSocketDisconnect

    path = f"/api/v1/ws/robots/{rig['robot_id']}"
    origin = "https://evil.example" if case == "origin" else "http://localhost:5173"
    if case == "inactive":
        with Session(rig["db"]) as db:
            db.get(Robot, rig["robot_id"]).is_active = False
            db.commit()
    if case == "url-token":
        path += "?access_token=forbidden"
    with pytest.raises(WebSocketDisconnect) as error:
        with rig["client"].websocket_connect(path, headers={"Origin": origin}) as ws:
            ws.send_json(
                {
                    "type": "authenticate",
                    "access_token": "bad" if case == "bad-token" else rig["token"],
                }
            )
            ws.receive_json()
    assert error.value.code == code


def test_telemetry_without_command_does_not_acknowledge_a_mode(rig):
    from app.schemas.control import DeviceTelemetry

    with Session(rig["db"]) as db:
        DeviceControlService(db, rig["settings"]).telemetry(
            "control-device",
            rig["secret"],
            DeviceTelemetry(
                sequence=0,
                generation=0,
                actual_mode="MANUAL",
                movement="STOP",
                obstacle="SENSOR_ERROR",
                buzzer=True,
            ),
        )
    state = rig["client"].get(rig["base"] + "/state").json()
    assert state["actual_mode"] == "MANUAL" and state["mode_pending"]
    assert state["obstacle"] == "SENSOR_ERROR" and state["command"] is None


def test_unsafe_mode_acknowledgement_does_not_unlock_manual(rig):
    grant = acquire(rig)
    with Session(rig["db"]) as db:
        adapter = DeviceControlService(db, rig["settings"])
        command = adapter.current_command("control-device", rig["secret"])
        adapter.report(
            "control-device",
            rig["secret"],
            DeviceReport(
                sequence=command.sequence,
                generation=command.generation,
                acknowledgement="EXECUTED",
                actual_mode="MANUAL",
                movement="STOP",
            ),
        )
    assert (
        rig["client"]
        .post(rig["base"] + "/move", json=payload(grant, direction="FORWARD"))
        .status_code
        == 409
    )


def test_offline_cleanup_keeps_a_live_borrow(rig):
    grant = acquire(rig)
    with Session(rig["db"]) as db:
        db.get(Robot, rig["robot_id"]).last_seen_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
        ControlService(db, rig["settings"]).cleanup()
        assert db.get(ControlSession, grant["id"], populate_existing=True).ended_at is None


def test_websocket_delivers_lease_changes_and_checks_revocation(rig):
    from starlette.websockets import WebSocketDisconnect

    rig["settings"].websocket_interval_seconds = 0.05
    with rig["client"].websocket_connect(
        f"/api/v1/ws/robots/{rig['robot_id']}", headers={"Origin": "http://localhost:5173"}
    ) as ws:
        ws.send_json({"type": "authenticate", "access_token": rig["token"]})
        assert not ws.receive_json()["data"]["lease"]["owned"]
        acquire(rig)
        for _ in range(10):
            event = ws.receive_json()
            if event["type"] == "robot.state" and event["data"]["lease"]["owned"]:
                break
        else:
            pytest.fail("No lease event received")
        rig["client"].post("/api/v1/auth/logout", headers=csrf(rig["client"]))
        with pytest.raises(WebSocketDisconnect) as error:
            while True:
                ws.receive_json()
        assert error.value.code == 4001


@pytest.mark.parametrize(
    "endpoint", ["acquire", "state", "session", "mode", "move", "stop", "renew", "release"]
)
def test_control_endpoints_require_jwt(auth_client, endpoint):
    method = auth_client.get if endpoint in ["state", "session"] else auth_client.post
    response = method(f"/api/v1/robots/{uuid4()}/control/{endpoint}")
    assert response.status_code == 401
