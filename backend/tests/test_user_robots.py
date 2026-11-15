from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import Robot, User
from tests.test_auth import accounts, auth_client, auth_settings, bearer, encoded_password, login
from tests.test_database import add_robot, lease

__all__ = ["accounts", "auth_client", "auth_settings", "encoded_password"]
pytestmark = pytest.mark.integration
ROOT = "/api/v1/robots"
PUBLIC_FIELDS = {"id", "name", "device_id", "is_active", "last_seen_at", "status", "available"}


@pytest.fixture
def robots(db_engine, accounts):
    now = datetime.now(UTC)
    with Session(db_engine) as db:
        records = {
            "offline": add_robot(db, name="Xe chưa kết nối", device_id="dev-offline"),
            "online": add_robot(db, name="Xe sẵn sàng", device_id="dev-online", last_seen_at=now),
            "busy": add_robot(db, name="Xe đang bận", last_seen_at=now),
            "disabled": add_robot(db, name="Xe vô hiệu", is_active=False, last_seen_at=now),
            "expired": add_robot(db, name="Xe lease hết hạn", last_seen_at=now),
            "stale": add_robot(db, name="Xe mất kết nối", last_seen_at=now - timedelta(minutes=1)),
            "future": add_robot(
                db, name="Xe heartbeat tương lai", last_seen_at=now + timedelta(minutes=1)
            ),
            "ended": add_robot(db, name="Xe lease đã đóng", last_seen_at=now),
        }
        db.add_all(
            [
                lease(accounts["user"], records["busy"].id),
                lease(accounts["user"], records["stale"].id),
                lease(
                    accounts["user"],
                    records["expired"].id,
                    started_at=now - timedelta(minutes=2),
                    expires_at=now - timedelta(minutes=1),
                ),
                lease(
                    accounts["user"],
                    records["ended"].id,
                    started_at=now - timedelta(seconds=5),
                    ended_at=now,
                ),
            ]
        )
        ids = {name: str(robot.id) for name, robot in records.items()}
        db.commit()
        return ids


@pytest.fixture
def viewer(auth_client):
    auth_client.headers.update(bearer(login(auth_client)))
    return auth_client


@pytest.mark.parametrize("identity", ["operator", "administrator"])
def test_active_user_or_admin_can_view_robots(auth_client, robots, identity):
    auth_client.headers.update(bearer(login(auth_client, identity)))
    response = auth_client.get(ROOT)
    assert response.status_code == 200 and response.json()["total"] == 7
    assert response.headers["cache-control"] == "no-store"
    detail = auth_client.get(f"{ROOT}/{robots['online']}")
    assert detail.status_code == 200 and detail.json()["available"] is True


@pytest.mark.parametrize("path", [ROOT, f"{ROOT}/{uuid4()}"])
def test_robot_reads_require_authentication(auth_client, path):
    assert auth_client.get(path).status_code == 401


def test_disabled_user_is_rejected(viewer, db_engine, accounts):
    with Session(db_engine) as db:
        db.get(User, accounts["user"]).is_active = False
        db.commit()
    assert viewer.get(ROOT).status_code == 401


def test_disabled_robot_is_hidden_even_if_client_requests_inactive(viewer, robots):
    response = viewer.get(ROOT, params={"is_active": False})
    assert robots["disabled"] not in {robot["id"] for robot in response.json()["items"]}
    assert viewer.get(f"{ROOT}/{robots['disabled']}").status_code == 404


def test_pagination_is_bounded_and_stable(viewer, robots):
    first = viewer.get(ROOT, params={"page_size": 3, "page": 1}).json()
    second = viewer.get(ROOT, params={"page_size": 3, "page": 2}).json()
    assert first["total"] == second["total"] == 7
    assert len(first["items"]) == len(second["items"]) == 3
    assert {r["id"] for r in first["items"]}.isdisjoint(r["id"] for r in second["items"])
    assert viewer.get(ROOT, params={"page": 99}).json()["items"] == []
    assert viewer.get(ROOT, params={"page_size": 101}).status_code == 422
    assert viewer.get(ROOT, params={"page": 0}).status_code == 422


def test_search_is_by_name_not_device_id(viewer, robots):
    found = viewer.get(ROOT, params={"q": "  SẴN SÀNG  "}).json()
    assert [r["id"] for r in found["items"]] == [robots["online"]]
    assert viewer.get(ROOT, params={"q": "dev-online"}).json()["total"] == 0
    assert viewer.get(ROOT, params={"q": "%"}).json()["total"] == 0


@pytest.mark.parametrize("status,expected", [("ONLINE", 3), ("OFFLINE", 3), ("BUSY", 1)])
def test_status_filters_apply_before_pagination(viewer, robots, status, expected):
    response = viewer.get(ROOT, params={"status": status, "page_size": 1})
    assert response.status_code == 200
    assert response.json()["total"] == expected
    assert all(r["status"] == status for r in response.json()["items"])


@pytest.mark.parametrize(
    "key,status,available",
    [
        ("offline", "OFFLINE", False),
        ("online", "ONLINE", True),
        ("busy", "BUSY", False),
        ("expired", "ONLINE", True),
        ("stale", "OFFLINE", False),
        ("future", "OFFLINE", False),
        ("ended", "ONLINE", True),
    ],
)
def test_status_and_availability_from_database(viewer, robots, key, status, available):
    data = viewer.get(f"{ROOT}/{robots[key]}").json()
    assert data["status"] == status and data["available"] is available
    if data["last_seen_at"]:
        assert datetime.fromisoformat(data["last_seen_at"]).utcoffset() == timedelta(0)


def test_no_sensitive_fields_in_list_or_detail(viewer, robots):
    data = viewer.get(ROOT).json()["items"]
    assert all(set(robot) == PUBLIC_FIELDS for robot in data)
    detail = viewer.get(f"{ROOT}/{robots['busy']}").json()
    assert set(detail) == PUBLIC_FIELDS
    assert not {"credential", "device_credential_hash", "user_id", "lease_token_hash"} & set(detail)


def test_missing_robot_returns_404_without_details(viewer):
    assert viewer.get(f"{ROOT}/{uuid4()}").status_code == 404
    assert viewer.get(f"{ROOT}/invalid-id").status_code == 422


def test_status_changes_when_heartbeat_becomes_stale(viewer, robots, db_engine):
    path = f"{ROOT}/{robots['online']}"
    assert viewer.get(path).json()["status"] == "ONLINE"
    with Session(db_engine) as db:
        db.get(Robot, robots["online"]).last_seen_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    assert viewer.get(path).json()["status"] == "OFFLINE"


def test_heartbeat_timeout_uses_existing_configuration(viewer, robots, db_engine, auth_settings):
    path = f"{ROOT}/{robots['online']}"
    with Session(db_engine) as db:
        db.get(Robot, robots["online"]).last_seen_at = datetime.now(UTC) - timedelta(seconds=5)
        db.commit()
    assert viewer.get(path).json()["status"] == "ONLINE"
    auth_settings.robot_offline_after_seconds = 2
    assert viewer.get(path).json()["status"] == "OFFLINE"


def test_public_and_admin_status_calculations_agree(auth_client, robots):
    auth_client.headers.update(bearer(login(auth_client, "administrator")))
    public = auth_client.get(ROOT).json()["items"]
    admin = auth_client.get("/api/v1/admin/robots").json()["items"]
    states = {r["id"]: r["status"] for r in admin}
    assert all(r["status"] == states[r["id"]] for r in public)


def test_user_robot_api_has_no_control_or_management_mutations(viewer, robots):
    assert viewer.post(ROOT, json={"name": "fake"}).status_code == 405
    assert viewer.patch(f"{ROOT}/{robots['online']}", json={"is_active": False}).status_code == 405
    assert viewer.post(f"{ROOT}/{robots['online']}/acquire").status_code == 404
