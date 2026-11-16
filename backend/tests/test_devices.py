from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DeviceSession, Robot, RobotCommand, RobotTelemetry
from app.repositories.devices import DeviceRepository
from app.schemas.devices import AckInput, TelemetryInput
from tests.test_auth import (
    accounts,
    auth_client,
    auth_settings,
    bearer,
    csrf,
    encoded_password,
    login,
)
from tests.test_control import acquire, payload, rig

__all__ = ["accounts", "auth_client", "auth_settings", "encoded_password", "rig"]
pytestmark = pytest.mark.integration
BASE = "/api/v1/devices"


@pytest.fixture
def device(rig):
    rig["settings"].device_allow_insecure_http = True
    headers = {"X-Device-ID": "control-device", "X-Device-Secret": rig["secret"]}
    boot_id = str(uuid4())
    response = rig["client"].post(
        BASE + "/authenticate", headers=headers, json={"boot_id": boot_id}
    )
    assert response.status_code == 200, response.text
    headers["X-Device-Session"] = response.json()["device_session_id"]
    assert (
        rig["client"]
        .post(BASE + "/heartbeat", headers=headers, json={"heartbeat_sequence": 1})
        .status_code
        == 200
    )
    return rig | {"headers": headers, "boot_id": boot_id, "session": response.json()}


def current(device):
    result = device["client"].get(BASE + "/commands/current", headers=device["headers"])
    assert result.status_code == 200, result.text
    return result.json()


def ack_body(command, status="APPLIED", safe=False):
    body = {k: command[k] for k in ["command_id", "sequence", "generation"]}
    body.update(status=status)
    if safe:
        body.update(safe_mode_switch=True, actual_mode=command["mode"], actual_movement="STOPPED")
    return body


def ack(device, command=None, status="APPLIED", safe=False):
    return device["client"].post(
        BASE + "/commands/ack",
        headers=device["headers"],
        json=ack_body(command or current(device)["command"], status, safe),
    )


def manual(device):
    grant = acquire(device)
    assert ack(device, safe=True).status_code == 200
    return grant


def sample(device, **changes):
    state = current(device)
    return {
        "robot_id": str(device["robot_id"]),
        "sample_sequence": 1,
        "sequence": state["sequence"],
        "generation": state["generation"],
        "distance_cm": None,
        "obstacle_status": "SENSOR_ERROR",
        "actual_mode": "MANUAL",
        "actual_movement": "STOPPED",
        "buzzer_active": None,
        **changes,
    }


def submit(device, body):
    return device["client"].post(BASE + "/telemetry", headers=device["headers"], json=body)


@pytest.mark.parametrize("case", ["missing", "wrong", "jwt", "disabled"])
def test_device_authentication_rejects_invalid_or_user_identity(device, case):
    headers = device["headers"].copy()
    if case in ["missing", "jwt"]:
        headers.pop("X-Device-Secret")
    if case == "wrong":
        headers["X-Device-Secret"] = "x" * 64
    if case == "disabled":
        with Session(device["db"]) as db:
            db.get(Robot, device["robot_id"]).is_active = False
            db.commit()
    response = device["client"].post(
        BASE + "/authenticate", headers=headers, json={"boot_id": str(uuid4())}
    )
    assert response.status_code == 401
    assert device["secret"] not in response.text


def test_authentication_is_idempotent_but_does_not_create_a_heartbeat(device):
    with Session(device["db"]) as db:
        db.get(Robot, device["robot_id"]).last_seen_at = None
        db.commit()
    response = device["client"].post(
        BASE + "/authenticate", headers=device["headers"], json={"boot_id": device["boot_id"]}
    )
    assert response.json()["device_session_id"] == device["session"]["device_session_id"]
    assert response.json()["heartbeat_interval_ms"] < response.json()["offline_timeout_ms"]
    with Session(device["db"]) as db:
        assert db.get(Robot, device["robot_id"]).last_seen_at is None
    assert not current(device)["control_authorized"]


def test_heartbeat_replay_does_not_extend_online_and_stale_sequence_is_rejected(device):
    response = device["client"].post(
        BASE + "/heartbeat", headers=device["headers"], json={"heartbeat_sequence": 2}
    )
    duplicate = device["client"].post(
        BASE + "/heartbeat", headers=device["headers"], json={"heartbeat_sequence": 2}
    )
    assert (
        duplicate.json()["duplicate"]
        and duplicate.json()["last_seen_at"] == response.json()["last_seen_at"]
    )
    assert (
        device["client"]
        .post(BASE + "/heartbeat", headers=device["headers"], json={"heartbeat_sequence": 1})
        .status_code
        == 409
    )
    with Session(device["db"]) as db:
        db.get(Robot, device["robot_id"]).last_seen_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    assert device["client"].get(device["base"] + "/state").json()["status"] == "OFFLINE"


def test_fetch_is_repeatable_and_does_not_acknowledge_or_execute(device):
    acquire(device)
    first, second = current(device), current(device)
    assert first["command"] == second["command"]
    assert first["command"]["status"] == "ACCEPTED"
    assert first["command"]["acknowledged_at"] is None
    state = device["client"].get(device["base"] + "/state").json()
    assert state["actual_movement"] is None and state["mode_pending"]


@pytest.mark.parametrize("after_stop", [False, True])
def test_borrow_identity_stays_present_while_idle_and_disappears_only_on_return(device, after_stop):
    grant = manual(device)
    if after_stop:
        assert (
            device["client"].post(device["base"] + "/stop", json=payload(grant)).status_code == 202
        )
    command = current(device)["command"]
    assert current(device)["control_session_id"] == grant["id"]
    with Session(device["db"]) as db:
        row = db.get(RobotCommand, command["command_id"])
        row.issued_at = datetime.now(UTC) - timedelta(seconds=5)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    idle = current(device)
    assert idle["command"] is None and not idle["control_authorized"]
    assert idle["control_session_id"] == grant["id"]
    assert (
        device["client"]
        .post(
            device["base"] + "/release",
            json={"control_session_id": grant["id"], "lease_token": grant["lease_token"]},
        )
        .status_code
        == 204
    )
    returned = current(device)
    assert returned["control_session_id"] is None and returned["command"] is None


def test_received_then_applied_safe_handoff_and_ack_idempotency(device):
    acquire(device)
    command = current(device)["command"]
    assert ack(device, command, "RECEIVED").status_code == 200
    assert device["client"].get(device["base"] + "/state").json()["mode_pending"]
    assert ack(device, command).status_code == 409
    first = ack(device, command, safe=True)
    duplicate = ack(device, command, safe=True)
    assert first.status_code == duplicate.status_code == 200
    assert duplicate.json()["duplicate"]
    assert first.json()["acknowledged_at"] == duplicate.json()["acknowledged_at"]
    assert ack(device, command, "RECEIVED").status_code == 409
    state = device["client"].get(device["base"] + "/state").json()
    assert not state["mode_pending"] and state["command"]["status"] == "APPLIED"
    assert state["acknowledgement"]["status"] == "APPLIED"


def test_applied_move_does_not_invent_actual_movement(device):
    grant = manual(device)
    moved = (
        device["client"]
        .post(device["base"] + "/move", json=payload(grant, direction="FORWARD"))
        .json()
    )
    assert ack(device, moved).status_code == 200
    state = device["client"].get(device["base"] + "/state").json()
    assert state["actual_movement"] == "STOP" and state["command"]["status"] == "APPLIED"


@pytest.mark.parametrize("status", ["REJECTED", "FAILED"])
def test_failed_or_rejected_ack_stops_motion_and_keeps_borrow(device, status):
    acquire(device)
    command = current(device)["command"]
    assert ack(device, command, status).status_code == 200
    assert ack(device, command, status).json()["duplicate"]
    assert not current(device)["control_authorized"]
    assert device["client"].get(device["base"] + "/session").json()["owned"]


def test_expired_command_and_old_ack_after_stop_are_rejected(device):
    grant = manual(device)
    command = (
        device["client"]
        .post(device["base"] + "/move", json=payload(grant, direction="FORWARD"))
        .json()
    )
    device["client"].post(device["base"] + "/stop", json=payload(grant, 2))
    assert ack(device, command).status_code == 409
    latest = current(device)["command"]
    with Session(device["db"]) as db:
        row = db.get(RobotCommand, latest["command_id"])
        row.issued_at = datetime.now(UTC) - timedelta(seconds=2)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert current(device)["command"] is None
    assert ack(device, latest).status_code == 409


@pytest.mark.parametrize("event", ["release", "logout", "auto_timeout", "offline"])
def test_lost_authorization_never_delivers_an_old_motion(device, event):
    grant = manual(device)
    mode = "AUTO" if event == "auto_timeout" else "MANUAL"
    if mode == "AUTO":
        device["client"].post(device["base"] + "/mode", json=payload(grant, mode=mode))
        assert ack(device, safe=True).status_code == 200
    else:
        device["client"].post(device["base"] + "/move", json=payload(grant, direction="FORWARD"))
    old = current(device)["command"]
    if event == "release":
        assert (
            device["client"]
            .post(
                device["base"] + "/release",
                json={"control_session_id": grant["id"], "lease_token": grant["lease_token"]},
            )
            .status_code
            == 204
        )
    elif event == "logout":
        assert (
            device["client"].post("/api/v1/auth/logout", headers=csrf(device["client"])).status_code
            == 204
        )
    else:
        with Session(device["db"]) as db:
            if event == "offline":
                db.get(Robot, device["robot_id"]).last_seen_at = None
            else:
                row = db.get(RobotCommand, old["command_id"])
                row.issued_at = datetime.now(UTC) - timedelta(seconds=5)
                row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
    envelope = current(device)
    assert envelope["command"] is None and not envelope["control_authorized"]
    assert envelope["authorization_expires_at"] is None and envelope["fail_safe"] == "STOP"
    assert ack(device, old).status_code == 409


@pytest.mark.parametrize("obstacle", ["CLEAR", "BLOCKED", "SENSOR_ERROR"])
def test_real_telemetry_is_persisted_and_reflected_in_control_state(device, obstacle):
    body = sample(
        device,
        obstacle_status=obstacle,
        distance_cm=9 if obstacle != "SENSOR_ERROR" else None,
        buzzer_active=True,
    )
    response = submit(device, body)
    assert response.status_code == 200, response.text
    duplicate = submit(device, body)
    assert (
        duplicate.json()["duplicate"]
        and duplicate.json()["recorded_at"] == response.json()["recorded_at"]
    )
    with Session(device["db"]) as db:
        assert db.scalar(select(func.count()).select_from(RobotTelemetry)) == 1
        row = db.scalars(select(RobotTelemetry)).one()
        assert row.obstacle_status == obstacle and row.buzzer_active
    state = device["client"].get(device["base"] + "/state").json()
    assert state["obstacle"] == obstacle and state["telemetry_fresh"]
    assert state["actual_movement"] == "STOP" and state["distance_cm"] == body["distance_cm"]


def test_telemetry_rate_ordering_and_conflicting_replay(device):
    body = sample(device)
    assert submit(device, body).status_code == 200
    assert submit(device, body | {"distance_cm": 20}).status_code == 409
    throttled = submit(device, body | {"sample_sequence": 2})
    assert throttled.status_code == 429 and throttled.headers["Retry-After"] == "1"
    with Session(device["db"]) as db:
        db.get(DeviceSession, device["headers"]["X-Device-Session"]).telemetry_at = datetime.now(
            UTC
        ) - timedelta(seconds=1)
        db.commit()
    assert submit(device, body | {"sample_sequence": 2}).status_code == 200
    assert submit(device, body).status_code == 409


def test_reboot_fences_lease_and_retires_previous_boot_requests(device):
    grant = manual(device)
    old = current(device)
    response = device["client"].post(
        BASE + "/authenticate", headers=device["headers"], json={"boot_id": str(uuid4())}
    )
    assert response.status_code == 200 and response.json()["generation"] > old["generation"]
    assert (
        device["client"].get(BASE + "/commands/current", headers=device["headers"]).status_code
        == 409
    )
    assert (
        device["client"]
        .post(
            BASE + "/authenticate", headers=device["headers"], json={"boot_id": device["boot_id"]}
        )
        .status_code
        == 409
    )
    with Session(device["db"]) as db:
        assert db.get(Robot, device["robot_id"]).last_seen_at is None
    assert device["client"].get(device["base"] + "/session").json()["owned"]
    device["headers"]["X-Device-Session"] = response.json()["device_session_id"]
    assert (
        device["client"]
        .post(BASE + "/heartbeat", headers=device["headers"], json={"heartbeat_sequence": 1})
        .status_code
        == 200
    )
    assert (
        device["client"]
        .post(
            device["base"] + "/renew",
            json={"control_session_id": grant["id"], "lease_token": grant["lease_token"]},
        )
        .status_code
        == 200
    )
    command = current(device)["command"]
    assert command["kind"] == "MODE" and command["mode"] == "MANUAL"
    assert command["generation"] > old["generation"]
    assert ack(device, command, safe=True).status_code == 200
    assert (
        device["client"]
        .post(device["base"] + "/move", json=payload(grant, direction="FORWARD"))
        .status_code
        == 202
    )


def test_auto_timeout_keeps_selected_mode_and_requires_a_fresh_safe_handoff(device):
    grant = manual(device)
    assert (
        device["client"]
        .post(device["base"] + "/mode", json=payload(grant, mode="AUTO"))
        .status_code
        == 202
    )
    assert ack(device, safe=True).status_code == 200
    old = current(device)["command"]
    with Session(device["db"]) as db:
        row = db.get(RobotCommand, old["command_id"])
        row.issued_at = datetime.now(UTC) - timedelta(seconds=30)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=20)
        db.commit()
    assert current(device)["command"] is None
    assert device["client"].get(device["base"] + "/session").json()["owned"]
    assert (
        device["client"]
        .post(
            device["base"] + "/renew",
            json={"control_session_id": grant["id"], "lease_token": grant["lease_token"]},
        )
        .status_code
        == 200
    )
    restarted = current(device)
    assert restarted["lease_expires_at"] is None
    assert restarted["authorization_expires_at"] is not None
    assert restarted["command"]["kind"] == "MODE"
    assert restarted["command"]["mode"] == "AUTO"
    assert restarted["mode_pending"]
    assert restarted["generation"] > old["generation"]
    assert ack(device, restarted["command"], safe=True).status_code == 200


def test_reboot_preserves_auto_selection_and_rearms_only_after_owner_renew(device):
    grant = manual(device)
    assert (
        device["client"]
        .post(device["base"] + "/mode", json=payload(grant, mode="AUTO"))
        .status_code
        == 202
    )
    assert ack(device, safe=True).status_code == 200
    response = device["client"].post(
        BASE + "/authenticate", headers=device["headers"], json={"boot_id": str(uuid4())}
    )
    assert response.status_code == 200
    device["headers"]["X-Device-Session"] = response.json()["device_session_id"]
    state = device["client"].get(device["base"] + "/state").json()
    assert state["requested_mode"] == "AUTO" and state["mode_pending"]
    assert state["lease"]["owned"] and current(device)["command"] is None
    assert (
        device["client"]
        .post(BASE + "/heartbeat", headers=device["headers"], json={"heartbeat_sequence": 1})
        .status_code
        == 200
    )
    assert (
        device["client"]
        .post(
            device["base"] + "/renew",
            json={"control_session_id": grant["id"], "lease_token": grant["lease_token"]},
        )
        .status_code
        == 200
    )
    command = current(device)["command"]
    assert command["kind"] == "MODE" and command["mode"] == "AUTO"
    assert ack(device, command, safe=True).status_code == 200


def test_delayed_ack_for_refreshed_same_direction_does_not_revive_old_move(device):
    grant = manual(device)
    first = (
        device["client"]
        .post(device["base"] + "/move", json=payload(grant, 1, direction="FORWARD"))
        .json()
    )
    second = (
        device["client"]
        .post(device["base"] + "/move", json=payload(grant, 2, direction="FORWARD"))
        .json()
    )
    assert ack(device, first).status_code == 200
    assert ack(device, first).json()["duplicate"]
    active = current(device)["command"]
    assert active["command_id"] == second["command_id"] and active["status"] == "ACCEPTED"
    with Session(device["db"]) as db:
        old = db.get(RobotCommand, first["command_id"])
        assert old.status.value == "SUPERSEDED" and old.acknowledgement == "APPLIED"


def test_delayed_ack_for_changed_direction_stays_rejected(device):
    grant = manual(device)
    first = (
        device["client"]
        .post(device["base"] + "/move", json=payload(grant, 1, direction="FORWARD"))
        .json()
    )
    second = (
        device["client"]
        .post(device["base"] + "/move", json=payload(grant, 2, direction="BACKWARD"))
        .json()
    )
    assert ack(device, first).status_code == 409
    assert current(device)["command"]["command_id"] == second["command_id"]


def test_rotation_revokes_secret_and_device_session(device):
    manual(device)
    admin = bearer(login(device["client"], "administrator"))
    rotated = device["client"].post(
        f"/api/v1/admin/robots/{device['robot_id']}/credentials/rotate", headers=admin
    )
    assert rotated.status_code == 200
    assert (
        device["client"].get(BASE + "/commands/current", headers=device["headers"]).status_code
        == 401
    )
    headers = device["headers"] | {"X-Device-Secret": rotated.json()["credential"]}
    assert device["client"].get(BASE + "/commands/current", headers=headers).status_code == 409


def test_multi_robot_isolation(device):
    from app.services.device_credentials import generate_device_credential
    from tests.test_database import add_robot

    credential = generate_device_credential()
    with Session(device["db"]) as db:
        robot = add_robot(db, device_id="second-device", device_credential_hash=credential.hashed)
        other = robot.id
        db.commit()
    headers = {"X-Device-ID": "second-device", "X-Device-Secret": credential.secret}
    response = device["client"].post(
        BASE + "/authenticate", headers=headers, json={"boot_id": str(uuid4())}
    )
    headers["X-Device-Session"] = response.json()["device_session_id"]
    acquire(device)
    command = current(device)["command"]
    assert (
        device["client"]
        .post(BASE + "/commands/ack", headers=headers, json=ack_body(command))
        .status_code
        == 409
    )
    assert submit(device, sample(device, robot_id=str(other))).status_code == 403
    assert (
        device["client"].get(BASE + "/commands/current", headers=headers).json()["command"] is None
    )


def test_telemetry_retention_is_bounded(device):
    device["settings"].telemetry_history_limit = 10
    for seq in range(1, 13):
        with Session(device["db"]) as db:
            db.get(DeviceSession, device["headers"]["X-Device-Session"]).telemetry_at = (
                datetime.now(UTC) - timedelta(seconds=1)
            )
            db.commit()
        assert submit(device, sample(device, sample_sequence=seq)).status_code == 200
    with Session(device["db"]) as db:
        assert db.scalar(select(func.count()).select_from(RobotTelemetry)) == 10
        db.query(RobotTelemetry).update({"recorded_at": datetime.now(UTC) - timedelta(days=8)})
        db.commit()
        DeviceRepository(db).cleanup(datetime.now(UTC), 7)
        db.commit()
        assert db.scalar(select(func.count()).select_from(RobotTelemetry)) == 0


def test_device_transport_and_query_policy(device):
    device["settings"].device_allow_insecure_http = False
    assert (
        device["client"].get(BASE + "/commands/current", headers=device["headers"]).status_code
        == 403
    )
    device["settings"].device_allow_insecure_http = True
    assert (
        device["client"]
        .get(BASE + "/commands/current?secret=forbidden", headers=device["headers"])
        .status_code
        == 400
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"distance_cm": -1},
        {"obstacle_status": "UNKNOWN"},
        {"actual_movement": "STOP"},
        {"sample_sequence": 0},
        {"actual_mode": "INVALID"},
        {"robot_id": "bad"},
    ],
)
def test_telemetry_input_validation(device, changes):
    response = submit(device, sample(device, **changes))
    assert response.status_code == 422
    assert device["secret"] not in response.text


def test_non_finite_sensor_and_unsafe_mode_ack_are_rejected():
    body = {
        "robot_id": uuid4(),
        "sample_sequence": 1,
        "sequence": 0,
        "generation": 0,
        "obstacle_status": "SENSOR_ERROR",
        "actual_mode": "MANUAL",
        "actual_movement": "STOPPED",
    }
    for distance in [float("nan"), float("inf")]:
        with pytest.raises(ValidationError):
            TelemetryInput(**body, distance_cm=distance)
    with pytest.raises(ValidationError):
        AckInput(
            command_id=uuid4(), sequence=1, generation=0, status="APPLIED", safe_mode_switch=True
        )


def test_ack_stop_race_cannot_restore_an_old_motion(device):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from uuid import UUID

    from app.core.errors import AppError
    from app.models.control import CommandKind
    from app.schemas.control import ActionInput
    from app.services.control import ControlService
    from app.services.devices import DeviceService

    grant = manual(device)
    move = (
        device["client"]
        .post(device["base"] + "/move", json=payload(grant, direction="FORWARD"))
        .json()
    )
    barrier = Barrier(2)

    def perform(stop):
        with Session(device["db"]) as db:
            barrier.wait(timeout=5)
            try:
                if stop:
                    ControlService(db, device["settings"]).action(
                        device["robot_id"],
                        device["actor"],
                        ActionInput.model_validate(payload(grant, 2)),
                        CommandKind.STOP,
                    )
                else:
                    DeviceService(
                        db, device["settings"], "control-device", device["secret"]
                    ).acknowledge(
                        UUID(device["headers"]["X-Device-Session"]),
                        AckInput.model_validate(ack_body(move)),
                    )
            except AppError as error:
                assert not stop and error.status_code == 409

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(perform, [True, False]))
    envelope = current(device)
    assert envelope["command"]["direction"] == "STOP"
    assert envelope["command"]["sequence"] > move["sequence"]


def test_public_auto_to_manual_waits_for_safe_device_ack(device):
    grant = manual(device)
    assert (
        device["client"]
        .post(device["base"] + "/mode", json=payload(grant, mode="AUTO"))
        .status_code
        == 202
    )
    auto = current(device)["command"]
    assert ack(device, auto, safe=True).status_code == 200
    assert (
        device["client"]
        .post(device["base"] + "/move", json=payload(grant, 2, direction="FORWARD"))
        .status_code
        == 409
    )
    assert (
        device["client"]
        .post(
            device["base"] + "/renew",
            json={"control_session_id": grant["id"], "lease_token": grant["lease_token"]},
        )
        .status_code
        == 200
    )
    permit = current(device)
    assert permit["command"]["kind"] == "KEEPALIVE" and permit["control_authorized"]
    assert (
        device["client"]
        .post(device["base"] + "/mode", json=payload(grant, 3, mode="MANUAL"))
        .status_code
        == 202
    )
    # Retrying an old ACK only returns its original receipt; it cannot confirm the new mode.
    assert ack(device, auto, safe=True).json()["duplicate"]
    assert device["client"].get(device["base"] + "/state").json()["mode_pending"]
    assert (
        device["client"]
        .post(device["base"] + "/move", json=payload(grant, 4, direction="FORWARD"))
        .status_code
        == 409
    )
    assert ack(device, safe=True).status_code == 200
    assert (
        device["client"]
        .post(device["base"] + "/move", json=payload(grant, 5, direction="FORWARD"))
        .status_code
        == 202
    )


def test_heartbeat_after_offline_fences_motion_and_keeps_borrow(device):
    manual(device)
    old = current(device)
    with Session(device["db"]) as db:
        db.get(Robot, device["robot_id"]).last_seen_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    response = device["client"].post(
        BASE + "/heartbeat", headers=device["headers"], json={"heartbeat_sequence": 2}
    )
    assert response.status_code == 200 and response.json()["generation"] > old["generation"]
    assert current(device)["command"] is None
    assert device["client"].get(device["base"] + "/session").json()["owned"]


def test_old_generation_telemetry_cannot_overwrite_current_state(device):
    grant = manual(device)
    body = sample(device, actual_movement="FORWARD")
    device["client"].post(device["base"] + "/stop", json=payload(grant))
    assert submit(device, body).status_code == 409
    assert device["client"].get(device["base"] + "/state").json()["actual_movement"] == "STOP"


@pytest.mark.parametrize(
    "path,method",
    [
        ("authenticate", "post"),
        ("heartbeat", "post"),
        ("commands/current", "get"),
        ("commands/ack", "post"),
        ("telemetry", "post"),
    ],
)
def test_all_device_routes_require_device_credentials_even_with_user_jwt(device, path, method):
    response = getattr(device["client"], method)(
        BASE + "/" + path, **({"json": {}} if method == "post" else {})
    )
    assert response.status_code == 401
