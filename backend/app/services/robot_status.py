from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import case, exists, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models import ControlSession, Robot, User
from app.models.enums import RobotStatus


class RobotStatusService:
    """Shared SQL status calculation for Admin and user reads, including status filters."""

    def __init__(self, offline_seconds: int):
        self.offline_seconds = offline_seconds

    def expression(self, now: datetime) -> ColumnElement[str]:
        online = (
            Robot.is_active
            & Robot.last_seen_at.is_not(None)
            & (Robot.last_seen_at >= now - timedelta(seconds=self.offline_seconds))
            & (Robot.last_seen_at <= now)
        )
        busy = exists(
            select(ControlSession.id)
            .join(User, User.id == ControlSession.user_id)
            .where(
                User.is_active,
                ControlSession.robot_id == Robot.id,
                ControlSession.ended_at.is_(None),
                ControlSession.started_at <= now,
                ControlSession.expires_at > now,
            )
        )
        return case(
            (online & busy, RobotStatus.BUSY.value),
            (online, RobotStatus.ONLINE.value),
            else_=RobotStatus.OFFLINE.value,
        )

    def get(self, db: Session, robot_id: UUID, now: datetime) -> RobotStatus:
        result = db.execute(select(self.expression(now)).where(Robot.id == robot_id)).scalar_one()
        return RobotStatus(result)
