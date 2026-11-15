import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import verify_password
from app.models import AuditLog, AuthSession, ControlSession, Robot, User
from app.models.enums import UserRole
from app.services.admin_users import UserManagementService
from app.services.device_credentials import authenticate_device
from tests.test_auth import (
    PASSWORD,
    accounts,
    auth_client,
    auth_settings,
    bearer,
    encoded_password,
    login,
)
from tests.test_database import add_robot, lease

__all__ = ["accounts", "auth_client", "auth_settings", "encoded_password"]
pytestmark = pytest.mark.integration
USERS = "/api/v1/admin/users"
ROBOTS = "/api/v1/admin/robots"


@pytest.fixture
def manager(auth_client):
    auth_client.headers.update(bearer(login(auth_client, "administrator")))
    return auth_client


def user_payload(**changes):
    return {"username": "newuser", "email": "newuser@example.com", "password": PASSWORD, **changes}


def new_robot(manager, **changes):
    response = manager.post(
        ROBOTS, json={"name": "Xe thử nghiệm", "device_id": "esp32-01", **changes}
    )
    assert response.status_code == 201, response.status_code
    return response.json()


def test_admin_can_create_get_and_update_user(manager, db_engine):
    response = manager.post(USERS, json=user_payload())
    assert response.status_code == 201
    data = response.json()
    assert "password_hash" not in data and "password" not in data
    with Session(db_engine) as db:
        assert verify_password(PASSWORD, db.get(User, data["id"]).password_hash)
    assert manager.get(f"{USERS}/{data['id']}").status_code == 200
    edited = manager.patch(
        f"{USERS}/{data['id']}", json={"username": "edited", "email": "edited@example.com"}
    )
    assert edited.status_code == 200 and edited.json()["username"] == "edited"


@pytest.mark.parametrize("path", [USERS, ROBOTS])
def test_user_cannot_access_admin_lists(auth_client, path):
    assert auth_client.get(path).status_code == 401
    assert auth_client.get(path, headers=bearer(login(auth_client))).status_code == 403


@pytest.mark.parametrize(
    "path,method,payload",
    [
        (USERS, "post", user_payload()),
        (f"{USERS}/{{id}}", "patch", {"username": "hacked"}),
        (f"{USERS}/{{id}}/role", "patch", {"role": "ADMIN"}),
        (f"{USERS}/{{id}}/status", "patch", {"is_active": False}),
        (f"{USERS}/{{id}}/reset-password", "post", {"password": PASSWORD}),
        (ROBOTS, "post", {"name": "Unauthorized", "device_id": "esp32"}),
        (f"{ROBOTS}/{{id}}", "patch", {"name": "hacked"}),
        (f"{ROBOTS}/{{id}}/status", "patch", {"is_active": False}),
        (f"{ROBOTS}/{{id}}/credentials/rotate", "post", None),
    ],
)
def test_every_admin_mutation_requires_admin(auth_client, path, method, payload):
    auth_client.headers.update(bearer(login(auth_client)))
    assert getattr(auth_client, method)(path.format(id=uuid4()), json=payload).status_code == 403


@pytest.mark.parametrize("changes", [{"username": "NEWUSER"}, {"email": "NEWUSER@example.com"}])
def test_duplicate_user_identity_is_rejected(manager, changes):
    assert manager.post(USERS, json=user_payload()).status_code == 201
    assert (
        manager.post(
            USERS, json=user_payload(username="different", email="different@example.com") | changes
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "changes",
    [{"username": "bad name"}, {"email": "invalid"}, {"password": "short"}, {"role": "ROOT"}],
)
def test_user_create_validation(manager, changes):
    response = manager.post(USERS, json=user_payload(**changes))
    assert response.status_code == 422
    assert PASSWORD not in response.text


def test_patch_rejects_null_empty_and_privilege_smuggling(manager, accounts):
    target = f"{USERS}/{accounts['user']}"
    for body in [{}, {"email": None}, {"role": "ADMIN"}, {"is_active": False}]:
        assert manager.patch(target, json=body).status_code == 422


def test_user_list_pagination_search_and_filters(manager):
    manager.post(USERS, json=user_payload())
    page = manager.get(USERS, params={"page_size": 1}).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert manager.get(USERS, params={"q": "NEWUSER@example.com"}).json()["total"] == 1
    assert manager.get(USERS, params={"role": "ADMIN", "is_active": True}).json()["total"] == 1
    assert manager.get(USERS, params={"q": "%"}).json()["total"] == 0
    assert manager.get(USERS, params={"page_size": 101}).status_code == 422
    assert manager.get(USERS, params={"page": 0}).status_code == 422


def test_role_change_and_last_admin_protection(manager, accounts):
    assert (
        manager.patch(f"{USERS}/{accounts['admin']}/role", json={"role": "USER"}).status_code == 409
    )
    assert (
        manager.patch(f"{USERS}/{accounts['user']}/role", json={"role": "ADMIN"}).status_code == 200
    )
    assert (
        manager.patch(f"{USERS}/{accounts['admin']}/role", json={"role": "USER"}).status_code == 200
    )
    assert manager.get(USERS).status_code == 403


def test_admin_cannot_disable_self_even_with_second_admin(manager, accounts):
    manager.patch(f"{USERS}/{accounts['user']}/role", json={"role": "ADMIN"})
    assert (
        manager.patch(f"{USERS}/{accounts['admin']}/status", json={"is_active": False}).status_code
        == 409
    )


def test_last_admin_cannot_be_disabled(manager, accounts):
    assert (
        manager.patch(f"{USERS}/{accounts['admin']}/status", json={"is_active": False}).status_code
        == 409
    )


def test_disable_revokes_sessions_even_after_reactivation(
    manager, accounts, db_engine, auth_settings
):
    from app.services.auth import AuthService

    with Session(db_engine) as db:
        tokens = AuthService(db, auth_settings).login("operator", PASSWORD, "target")
        robot = add_robot(db)
        db.add(lease(accounts["user"], robot.id))
        db.commit()
    access = {"Authorization": f"Bearer {tokens.access_token}"}
    assert (
        manager.patch(f"{USERS}/{accounts['user']}/status", json={"is_active": False}).status_code
        == 200
    )
    assert manager.get("/api/v1/auth/me", headers=access).status_code == 401
    assert (
        manager.patch(f"{USERS}/{accounts['user']}/status", json={"is_active": True}).status_code
        == 200
    )
    assert manager.get("/api/v1/auth/me", headers=access).status_code == 401
    with Session(db_engine) as db:
        assert (
            db.scalar(select(AuthSession.revoked_at).where(AuthSession.user_id == accounts["user"]))
            is not None
        )
        assert db.scalar(select(ControlSession.ended_at)) is not None
        with pytest.raises(AppError):
            AuthService(db, auth_settings).refresh(tokens.refresh_token, tokens.csrf_token)


def test_reset_password_hashes_and_revokes_old_sessions(
    manager, accounts, db_engine, auth_settings
):
    from app.services.auth import AuthService

    with Session(db_engine) as db:
        tokens = AuthService(db, auth_settings).login("operator", PASSWORD, "target")
    password = secrets.token_urlsafe(24)
    assert (
        manager.post(
            f"{USERS}/{accounts['user']}/reset-password", json={"password": password}
        ).status_code
        == 204
    )
    assert (
        manager.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens.access_token}"}
        ).status_code
        == 401
    )
    assert login(manager, password=PASSWORD).status_code == 401
    assert login(manager, password=password).status_code == 200
    with Session(db_engine) as db:
        assert verify_password(password, db.get(User, accounts["user"]).password_hash)


def test_concurrent_self_demotions_preserve_one_admin(db_engine, accounts):
    with Session(db_engine) as db:
        db.get(User, accounts["user"]).role = UserRole.ADMIN
        db.commit()
    barrier = Barrier(2)

    def demote(actor):
        with Session(db_engine) as db:
            barrier.wait(timeout=10)
            try:
                UserManagementService(db, actor).set_role(actor, UserRole.USER)
                return 200
            except AppError as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(demote, [accounts["user"], accounts["admin"]]))
    assert sorted(results) == [200, 409]
    with Session(db_engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.role == UserRole.ADMIN, User.is_active)
            )
            == 1
        )


def test_robot_creation_is_offline_and_secret_is_one_time(manager, db_engine):
    data = new_robot(manager)
    assert data["robot"]["status"] == "OFFLINE" and data["robot"]["last_seen_at"] is None
    assert len(data["credential"]) >= 64
    robot_id = data["robot"]["id"]
    detail = manager.get(f"{ROBOTS}/{robot_id}")
    assert detail.status_code == 200
    assert "credential" not in detail.text and "credential" not in manager.get(ROBOTS).text
    with Session(db_engine) as db:
        robot = authenticate_device(db, "esp32-01", data["credential"])
        assert robot is not None and robot.device_credential_hash != data["credential"]
        assert authenticate_device(db, "esp32-01", "wrong") is None


def test_duplicate_device_id_and_robot_validation(manager):
    new_robot(manager)
    assert manager.post(ROBOTS, json={"name": "Other", "device_id": "esp32-01"}).status_code == 409
    assert manager.post(ROBOTS, json={"name": " ", "device_id": "esp32-02"}).status_code == 422
    assert (
        manager.post(
            ROBOTS,
            json={
                "name": "Other",
                "device_id": "esp32-02",
                "last_seen_at": datetime.now(UTC).isoformat(),
            },
        ).status_code
        == 422
    )


def test_robot_update_and_device_id_conflict(manager):
    first = new_robot(manager)["robot"]
    new_robot(manager, device_id="esp32-02")
    assert (
        manager.patch(f"{ROBOTS}/{first['id']}", json={"name": "Tên mới"}).json()["name"]
        == "Tên mới"
    )
    assert (
        manager.patch(f"{ROBOTS}/{first['id']}", json={"device_id": "esp32-02"}).status_code == 409
    )
    assert (
        manager.patch(
            f"{ROBOTS}/{first['id']}", json={"device_credential_hash": "fake"}
        ).status_code
        == 422
    )


def test_status_uses_real_heartbeat_lease_and_active_flag(manager, db_engine, accounts):
    data = new_robot(manager)["robot"]
    path = f"{ROBOTS}/{data['id']}"
    with Session(db_engine) as db:
        robot = db.get(Robot, data["id"])
        robot.last_seen_at = datetime.now(UTC)
        db.commit()
    assert manager.get(path).json()["status"] == "ONLINE"
    with Session(db_engine) as db:
        db.add(lease(accounts["user"], data["id"]))
        db.commit()
    assert manager.get(path).json()["status"] == "BUSY"
    assert manager.get(ROBOTS, params={"status": "BUSY"}).json()["total"] == 1
    with Session(db_engine) as db:
        db.get(Robot, data["id"]).last_seen_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    assert manager.get(path).json()["status"] == "OFFLINE"
    disabled = manager.patch(path + "/status", json={"is_active": False})
    assert disabled.status_code == 200 and not disabled.json()["is_active"]
    assert manager.patch(path + "/status", json={"is_active": True}).json()["status"] == "OFFLINE"
    with Session(db_engine) as db:
        assert db.scalar(select(ControlSession.ended_at)) is not None


def test_rotate_revokes_previous_secret_and_invalidates_connection(manager, db_engine, accounts):
    first = new_robot(manager)
    robot_id = first["robot"]["id"]
    with Session(db_engine) as db:
        db.get(Robot, robot_id).last_seen_at = datetime.now(UTC)
        db.add(lease(accounts["user"], robot_id))
        db.commit()
    response = manager.post(f"{ROBOTS}/{robot_id}/credentials/rotate")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    current = response.json()
    assert current["credential"] != first["credential"] and current["robot"]["status"] == "OFFLINE"
    with Session(db_engine) as db:
        assert authenticate_device(db, "esp32-01", first["credential"]) is None
        assert authenticate_device(db, "esp32-01", current["credential"]) is not None
        assert db.scalar(select(ControlSession.ended_at)) is not None
    assert current["credential"] not in manager.get(f"{ROBOTS}/{robot_id}").text


def test_disabled_device_cannot_authenticate(manager, db_engine):
    data = new_robot(manager)
    manager.patch(f"{ROBOTS}/{data['robot']['id']}/status", json={"is_active": False})
    with Session(db_engine) as db:
        assert authenticate_device(db, "esp32-01", data["credential"]) is None


def test_robot_search_filters_and_pagination(manager):
    first = new_robot(manager)["robot"]
    new_robot(manager, device_id="esp32-02", name="Xe thứ hai")
    manager.patch(f"{ROBOTS}/{first['id']}/status", json={"is_active": False})
    assert manager.get(ROBOTS, params={"page_size": 1}).json()["total"] == 2
    assert manager.get(ROBOTS, params={"q": "esp32-02"}).json()["total"] == 1
    assert manager.get(ROBOTS, params={"is_active": False}).json()["total"] == 1
    assert manager.get(ROBOTS, params={"status": "OFFLINE"}).json()["total"] == 2
    assert manager.get(ROBOTS, params={"page_size": 101}).status_code == 422


def test_audit_logs_have_actor_target_action_without_secrets(manager, db_engine):
    user = manager.post(USERS, json=user_payload()).json()
    manager.patch(f"{USERS}/{user['id']}/role", json={"role": "ADMIN"})
    manager.patch(f"{USERS}/{user['id']}/status", json={"is_active": False})
    created = new_robot(manager)
    rotated = manager.post(f"{ROBOTS}/{created['robot']['id']}/credentials/rotate").json()
    manager.patch(f"{ROBOTS}/{created['robot']['id']}/status", json={"is_active": False})
    with Session(db_engine) as db:
        events = list(db.scalars(select(AuditLog)))
        assert {
            "user.created",
            "user.role_changed",
            "user.disabled",
            "robot.created",
            "robot.credential_rotated",
            "robot.disabled",
        } <= {e.action for e in events}
        assert all(e.user_id is not None for e in events)
        serialized = json.dumps([e.event_metadata for e in events])
        assert PASSWORD not in serialized and created["credential"] not in serialized
        assert rotated["credential"] not in serialized and "password_hash" not in serialized


def test_not_found_and_no_hard_delete(manager):
    for base in [USERS, ROBOTS]:
        assert manager.get(f"{base}/{uuid4()}").status_code == 404
        assert manager.delete(f"{base}/{uuid4()}").status_code == 405


@pytest.mark.parametrize("operation", ["disable", "password"])
def test_login_racing_with_revocation_cannot_leave_live_session(
    db_engine, accounts, auth_settings, monkeypatch, operation
):
    import app.services.auth as auth_module

    entered, proceed = Event(), Event()
    original = auth_module.verify_password

    def hold_verification(password, encoded):
        entered.set()
        assert proceed.wait(5)
        return original(password, encoded)

    monkeypatch.setattr(auth_module, "verify_password", hold_verification)

    def sign_in():
        with Session(db_engine) as db:
            return auth_module.AuthService(db, auth_settings).login("operator", PASSWORD, "race")

    def revoke():
        with Session(db_engine) as db:
            service = UserManagementService(db, accounts["admin"])
            if operation == "disable":
                service.set_active(accounts["user"], False)
            else:
                service.reset_password(accounts["user"], secrets.token_urlsafe(24))

    with ThreadPoolExecutor(max_workers=2) as pool:
        signed_in = pool.submit(sign_in)
        assert entered.wait(5)
        revoked = pool.submit(revoke)
        try:
            revoked.result(timeout=0.3)
        except TimeoutError:
            pass  # Expected when login holds the user row lock.
        finally:
            proceed.set()
        signed_in.result(timeout=10)
        revoked.result(timeout=10)
    with Session(db_engine) as db:
        families = list(
            db.scalars(select(AuthSession).where(AuthSession.user_id == accounts["user"]))
        )
        assert families and all(f.revoked_at is not None for f in families)


def test_failed_robot_edit_rolls_back_connection_and_lease(manager, db_engine, accounts):
    first = new_robot(manager)["robot"]
    new_robot(manager, device_id="esp32-02")
    with Session(db_engine) as db:
        db.get(Robot, first["id"]).last_seen_at = datetime.now(UTC)
        db.add(lease(accounts["user"], first["id"]))
        db.commit()
    assert (
        manager.patch(f"{ROBOTS}/{first['id']}", json={"device_id": "esp32-02"}).status_code == 409
    )
    with Session(db_engine) as db:
        robot = db.get(Robot, first["id"])
        assert robot.last_seen_at is not None and robot.device_id == "esp32-01"
        assert db.scalar(select(ControlSession.ended_at)) is None


@pytest.mark.parametrize(
    "seconds,expected", [(None, "OFFLINE"), (-5, "ONLINE"), (-60, "OFFLINE"), (60, "OFFLINE")]
)
def test_heartbeat_boundaries(manager, db_engine, seconds, expected):
    robot = new_robot(manager)["robot"]
    with Session(db_engine) as db:
        db.get(Robot, robot["id"]).last_seen_at = (
            None if seconds is None else datetime.now(UTC) + timedelta(seconds=seconds)
        )
        db.commit()
    assert manager.get(f"{ROBOTS}/{robot['id']}").json()["status"] == expected


def test_expired_lease_does_not_mark_robot_busy(manager, db_engine, accounts):
    robot = new_robot(manager)["robot"]
    now = datetime.now(UTC)
    with Session(db_engine) as db:
        db.get(Robot, robot["id"]).last_seen_at = now
        db.add(
            lease(
                accounts["user"],
                robot["id"],
                started_at=now - timedelta(minutes=2),
                expires_at=now - timedelta(minutes=1),
            )
        )
        db.commit()
    assert manager.get(f"{ROBOTS}/{robot['id']}").json()["status"] == "ONLINE"


def test_cors_allows_authenticated_admin_patch(manager):
    response = manager.options(
        USERS,
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert "PATCH" in response.headers["access-control-allow-methods"]
