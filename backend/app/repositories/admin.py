from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models import AuthSession, ControlSession, Robot, User
from app.models.enums import RobotStatus, UserRole
from app.services.robot_status import RobotStatusService


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: UUID, *, lock: bool = False) -> User | None:
        statement = select(User).where(User.id == user_id).execution_options(populate_existing=True)
        return self.db.scalar(statement.with_for_update() if lock else statement)

    def list(
        self, page: int, size: int, q: str, role: UserRole | None, active: bool | None
    ) -> tuple[list[User], int]:
        filters = []
        if q:
            filters.append(
                or_(
                    User.username.icontains(q, autoescape=True),
                    User.email.icontains(q, autoescape=True),
                )
            )
        if role is not None:
            filters.append(User.role == role)
        if active is not None:
            filters.append(User.is_active == active)
        total = self.db.execute(select(func.count()).select_from(User).where(*filters)).scalar_one()
        rows = self.db.scalars(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc(), User.id)
            .offset((page - 1) * size)
            .limit(size)
        ).all()
        return list(rows), total

    def active_admin_count(self) -> int:
        return self.db.execute(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN, User.is_active)
        ).scalar_one()

    def revoke_sessions(self, user_id: UUID, now: datetime) -> None:
        self.db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    def close_leases(self, user_id: UUID, now: datetime) -> None:
        self.db.execute(
            update(ControlSession)
            .where(ControlSession.user_id == user_id, ControlSession.ended_at.is_(None))
            .values(ended_at=now)
        )


class RobotRepository:
    def __init__(self, db: Session, offline_seconds: int):
        self.db, self.offline_seconds = db, offline_seconds
        self.status_service = RobotStatusService(offline_seconds)

    def status_expression(self, now: datetime) -> ColumnElement[str]:
        return self.status_service.expression(now)

    def get(self, robot_id: UUID, *, lock: bool = False) -> Robot | None:
        statement = (
            select(Robot).where(Robot.id == robot_id).execution_options(populate_existing=True)
        )
        return self.db.scalar(statement.with_for_update() if lock else statement)

    def list(
        self,
        page: int,
        size: int,
        q: str,
        active: bool | None,
        status: RobotStatus | None,
        now: datetime,
        *,
        name_only: bool = False,
    ) -> tuple[list[tuple[Robot, RobotStatus]], int]:
        state = self.status_expression(now).label("status")
        filters = []
        if q:
            name_match = Robot.name.icontains(q, autoescape=True)
            filters.append(
                name_match
                if name_only
                else or_(name_match, Robot.device_id.icontains(q, autoescape=True))
            )
        if active is not None:
            filters.append(Robot.is_active == active)
        if status is not None:
            filters.append(state == status.value)
        total = self.db.execute(
            select(func.count()).select_from(Robot).where(*filters)
        ).scalar_one()
        rows = self.db.execute(
            select(Robot, state)
            .where(*filters)
            .order_by(Robot.created_at.desc(), Robot.id)
            .offset((page - 1) * size)
            .limit(size)
        ).all()
        return [(robot, RobotStatus(status)) for robot, status in rows], total

    def status(self, robot_id: UUID, now: datetime) -> RobotStatus:
        return self.status_service.get(self.db, robot_id, now)

    def get_active_with_status(
        self, robot_id: UUID, now: datetime
    ) -> tuple[Robot, RobotStatus] | None:
        row = self.db.execute(
            select(Robot, self.status_expression(now)).where(Robot.id == robot_id, Robot.is_active)
        ).one_or_none()
        return (row[0], RobotStatus(row[1])) if row is not None else None

    def close_leases(self, robot_id: UUID, now: datetime) -> None:
        self.db.execute(
            update(ControlSession)
            .where(ControlSession.robot_id == robot_id, ControlSession.ended_at.is_(None))
            .values(ended_at=now)
        )
