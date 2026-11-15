from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import DeviceSession, RobotTelemetry


class DeviceRepository:
    def __init__(self, db: Session):
        self.db = db

    def session(self, robot_id: UUID) -> DeviceSession | None:
        # Caller already holds the Robot lock, serializing auth, writes and credential rotation.
        return self.db.scalar(
            select(DeviceSession)
            .where(DeviceSession.robot_id == robot_id, DeviceSession.ended_at.is_(None))
            .execution_options(populate_existing=True)
        )

    def boot(self, robot_id: UUID, boot_id: UUID) -> DeviceSession | None:
        return self.db.scalar(
            select(DeviceSession).where(
                DeviceSession.robot_id == robot_id, DeviceSession.boot_id == boot_id
            )
        )

    def prune(self, robot_id: UUID, limit: int) -> None:
        ids = (
            select(RobotTelemetry.id)
            .where(RobotTelemetry.robot_id == robot_id)
            .order_by(RobotTelemetry.recorded_at.desc(), RobotTelemetry.id.desc())
            .offset(limit)
            .limit(1000)
        )
        self.db.execute(delete(RobotTelemetry).where(RobotTelemetry.id.in_(ids)))

    def cleanup(self, now: datetime, days: int) -> None:
        ids = (
            select(RobotTelemetry.id)
            .where(RobotTelemetry.recorded_at < now - timedelta(days=days))
            .order_by(RobotTelemetry.recorded_at)
            .limit(1000)
        )
        self.db.execute(delete(RobotTelemetry).where(RobotTelemetry.id.in_(ids)))
