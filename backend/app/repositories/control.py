from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, exists, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import ControlSession, Robot, RobotCommand, RobotControlState
from app.models.control import CommandStatus

ACTIVE_COMMANDS = [
    CommandStatus.ACCEPTED,
    CommandStatus.RECEIVED,
    CommandStatus.EXECUTED,
    CommandStatus.APPLIED,
]


class ControlRepository:
    def __init__(self, db: Session):
        self.db = db

    def robot(self, robot_id: UUID) -> Robot | None:
        return self.db.scalar(
            select(Robot)
            .where(Robot.id == robot_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def lease(self, robot_id: UUID) -> ControlSession | None:
        return self.db.scalar(
            select(ControlSession)
            .where(ControlSession.robot_id == robot_id, ControlSession.ended_at.is_(None))
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def runtime(self, robot_id: UUID) -> RobotControlState:
        self.db.execute(
            insert(RobotControlState).values(robot_id=robot_id).on_conflict_do_nothing()
        )
        return self.db.scalars(
            select(RobotControlState)
            .where(RobotControlState.robot_id == robot_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one()

    def latest(self, state: RobotControlState) -> RobotCommand | None:
        return self.db.scalar(
            select(RobotCommand)
            .where(RobotCommand.robot_id == state.robot_id, RobotCommand.sequence == state.sequence)
            .execution_options(populate_existing=True)
        )

    def supersede(self, robot_id: UUID) -> None:
        self.db.execute(
            update(RobotCommand)
            .where(RobotCommand.robot_id == robot_id, RobotCommand.status.in_(ACTIVE_COMMANDS))
            .values(status=CommandStatus.SUPERSEDED)
        )

    def prune(self, state: RobotControlState, limit: int) -> None:
        self.db.execute(
            delete(RobotCommand).where(
                RobotCommand.robot_id == state.robot_id,
                RobotCommand.sequence <= state.sequence - limit,
                RobotCommand.status.not_in(ACTIVE_COMMANDS),
            )
        )

    def cleanup_ids(self, now: datetime, offline_seconds: int) -> list[UUID]:
        offline = or_(
            ~Robot.is_active,
            Robot.last_seen_at.is_(None),
            Robot.last_seen_at < now - timedelta(seconds=offline_seconds),
            Robot.last_seen_at > now,
        )
        needs_lease = exists(
            select(ControlSession.id).where(
                ControlSession.robot_id == Robot.id,
                ControlSession.auth_session_id.is_not(None),
                ControlSession.ended_at.is_(None),
                or_(ControlSession.expires_at <= now, offline),
            )
        )
        needs_command = exists(
            select(RobotCommand.id).where(
                RobotCommand.robot_id == Robot.id,
                RobotCommand.status.in_(ACTIVE_COMMANDS),
                RobotCommand.expires_at <= now,
            )
        )
        return list(
            self.db.scalars(
                select(Robot.id)
                .where(or_(needs_lease, needs_command))
                .order_by(Robot.id)
                .limit(100)
                .with_for_update(skip_locked=True)
            )
        )
