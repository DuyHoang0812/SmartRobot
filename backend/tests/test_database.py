from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from alembic import command
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditLog, ControlSession, Robot, RobotTelemetry, User
from app.models.enums import Movement, RobotMode, UserRole
from tests.conftest import migration_config

pytestmark = pytest.mark.integration


def add_user(db, **overrides):
    values = {
        "username": f"user_{uuid4().hex}",
        "email": f"{uuid4().hex}@example.test",
        "password_hash": "test-only-hash",
    }
    db.add(user := User(**(values | overrides)))
    db.flush()
    return user


def add_robot(db, **overrides):
    values = {
        "name": "Xe thử nghiệm",
        "device_id": uuid4().hex,
        "device_credential_hash": "test-only-hash",
    }
    db.add(robot := Robot(**(values | overrides)))
    db.flush()
    return robot


def lease(user_id, robot_id, **overrides):
    now = datetime.now(UTC)
    values = {
        "user_id": user_id,
        "robot_id": robot_id,
        "lease_token_hash": uuid4().hex,
        "started_at": now,
        "expires_at": now + timedelta(seconds=30),
    }
    return ControlSession(**(values | overrides))


def test_migrations_create_expected_schema(db_engine):
    inspector = inspect(db_engine)
    assert set(inspector.get_table_names()) == {
        "alembic_version",
        "users",
        "robots",
        "control_sessions",
        "robot_telemetry",
        "audit_logs",
        "robot_control_states",
        "robot_commands",
        "auth_sessions",
        "refresh_tokens",
        "login_rate_limits",
        "device_sessions",
    }
    with db_engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0005_persistent_borrow"
        )
    assert len(inspector.get_foreign_keys("control_sessions")) == 3
    assert any(
        i["name"] == "uq_control_sessions_open_robot" and i["unique"]
        for i in inspector.get_indexes("control_sessions")
    )


def test_migration_upgrade_downgrade_upgrade(empty_db_engine):
    with empty_db_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        command.downgrade(config, "base")
        assert inspect(connection).get_table_names() == ["alembic_version"]
        command.upgrade(config, "head")
        command.check(config)


def test_migration_matches_models_and_upgrade_is_idempotent(db_engine):
    with db_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        command.check(config)


def test_persistent_borrow_migration_preserves_open_and_returned_history(empty_db_engine):
    with empty_db_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "0004_devices")
        with Session(connection) as db:
            user = add_user(db)
            first, second = add_robot(db), add_robot(db)
            now = datetime.now(UTC)
            opened = lease(user.id, first.id)
            returned = lease(
                user.id, second.id, started_at=now - timedelta(seconds=10), ended_at=now
            )
            db.add_all([opened, returned])
            db.flush()
            opened_id, returned_id = opened.id, returned.id
            returned_expiry = returned.expires_at
            db.commit()
        command.upgrade(config, "head")
        with Session(connection) as db:
            assert db.get(ControlSession, opened_id).expires_at is None
            assert db.get(ControlSession, opened_id).ended_at is None
            assert db.get(ControlSession, returned_id).expires_at == returned_expiry
            assert db.get(ControlSession, returned_id).ended_at is not None
        command.downgrade(config, "0004_devices")
        with Session(connection) as db:
            assert db.get(ControlSession, opened_id).expires_at is not None
        command.upgrade(config, "head")
        command.check(config)


def test_uuid_defaults_timestamps_and_jsonb_round_trip(db):
    user, robot = add_user(db), add_robot(db)
    db.add(
        audit := AuditLog(
            user_id=user.id,
            robot_id=robot.id,
            action="test",
            event_metadata={"source": "integration", "count": 2},
        )
    )
    db.commit()
    db.refresh(audit)
    assert isinstance(user.id, UUID)
    assert user.role == UserRole.USER
    assert user.is_active and robot.is_active
    assert not robot.is_simulated
    assert robot.last_seen_at is None
    assert user.created_at.tzinfo is not None
    assert user.updated_at.tzinfo is not None
    assert audit.event_metadata == {"source": "integration", "count": 2}


def test_updated_at_changes_on_orm_update(db):
    user = add_user(db)
    db.commit()
    previous = user.updated_at
    user.username = "renamed"
    db.commit()
    db.refresh(user)
    assert user.updated_at > previous


@pytest.mark.parametrize("field", ["username", "email"])
def test_user_identity_is_case_insensitively_unique(db, field):
    user = add_user(db, username="Operator", email="Operator@example.test")
    with pytest.raises(IntegrityError):
        add_user(db, **{field: getattr(user, field).upper()})


def test_device_id_is_unique(db):
    robot = add_robot(db)
    with pytest.raises(IntegrityError):
        add_robot(db, device_id=robot.device_id)


def test_foreign_keys_reject_unknown_user_and_robot(db):
    db.add(lease(uuid4(), uuid4()))
    with pytest.raises(IntegrityError):
        db.flush()


def test_database_rejects_unknown_role(db):
    with pytest.raises(IntegrityError):
        add_user(db, role="ROOT")


@pytest.mark.parametrize("field", ["username", "email", "password_hash"])
def test_required_user_fields_cannot_be_empty(db, field):
    with pytest.raises(IntegrityError):
        add_user(db, **{field: ""})


def test_two_open_leases_for_same_robot_are_rejected(db):
    first, second, robot = add_user(db), add_user(db), add_robot(db)
    db.add(lease(first.id, robot.id))
    db.flush()
    db.add(lease(second.id, robot.id))
    with pytest.raises(IntegrityError):
        db.flush()


def test_expired_open_lease_must_be_closed_before_replacement(db):
    user, robot = add_user(db), add_robot(db)
    now = datetime.now(UTC)
    old = lease(
        user.id,
        robot.id,
        started_at=now - timedelta(minutes=2),
        expires_at=now - timedelta(minutes=1),
    )
    db.add(old)
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(lease(user.id, robot.id))
        db.flush()
    old.ended_at = now
    db.flush()
    db.add(lease(user.id, robot.id))
    db.flush()
    assert db.scalar(select(func.count()).select_from(ControlSession)) == 2


def test_lease_for_different_robots_is_allowed(db):
    user, first, second = add_user(db), add_robot(db), add_robot(db)
    db.add_all([lease(user.id, first.id), lease(user.id, second.id)])
    db.flush()


def test_lease_invalid_expiration_is_rejected(db):
    user, robot = add_user(db), add_robot(db)
    now = datetime.now(UTC)
    db.add(lease(user.id, robot.id, started_at=now, expires_at=now))
    with pytest.raises(IntegrityError):
        db.flush()


def test_concurrent_transactions_can_only_commit_one_lease(db_engine):
    with Session(db_engine) as session:
        first, second, robot = add_user(session), add_user(session), add_robot(session)
        user_ids, robot_id = [first.id, second.id], robot.id
        session.commit()
    barrier = Barrier(2)

    def attempt(user_id):
        with Session(db_engine) as session:
            session.add(lease(user_id, robot_id))
            barrier.wait(timeout=10)
            try:
                session.commit()
                return "committed"
            except IntegrityError:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, user_ids))
    assert sorted(results) == ["committed", "conflict"]
    with Session(db_engine) as session:
        assert session.scalar(select(func.count()).select_from(ControlSession)) == 1


@pytest.mark.parametrize("distance", [-1.0, float("inf"), float("nan")])
def test_invalid_telemetry_distance_is_rejected(db, distance):
    robot = add_robot(db)
    db.add(
        RobotTelemetry(
            robot_id=robot.id, distance_cm=distance, mode=RobotMode.MANUAL, movement=Movement.STOP
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_sensor_failure_can_be_recorded_as_null(db):
    robot = add_robot(db)
    db.add(
        telemetry := RobotTelemetry(
            robot_id=robot.id, distance_cm=None, mode=RobotMode.MANUAL, movement=Movement.STOP
        )
    )
    db.flush()
    assert telemetry.distance_cm is None
    assert telemetry.recorded_at.tzinfo is not None


def test_uncommitted_work_rolls_back_when_session_closes(db_engine):
    with Session(db_engine) as session:
        add_user(session)
    with Session(db_engine) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 0


def test_audit_history_survives_user_and_robot_deletion(db):
    user, robot = add_user(db), add_robot(db)
    db.add(audit := AuditLog(user_id=user.id, robot_id=robot.id, action="test"))
    db.flush()
    db.delete(user)
    db.delete(robot)
    db.flush()
    db.refresh(audit)
    assert audit.user_id is None and audit.robot_id is None
    assert audit.event_metadata == {}
