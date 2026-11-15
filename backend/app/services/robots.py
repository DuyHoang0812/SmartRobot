from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Robot
from app.models.enums import RobotStatus
from app.repositories.admin import RobotRepository
from app.repositories.auth import AuthRepository
from app.schemas.admin import Page
from app.schemas.robots import UserRobotResponse


class UserRobotService:
    def __init__(self, db: Session, offline_seconds: int):
        self.db = db
        self.repository = RobotRepository(db, offline_seconds)

    @staticmethod
    def response(robot: Robot, status: RobotStatus) -> UserRobotResponse:
        # Explicit allowlist: no credential/hash, lease owner, token or audit data.
        return UserRobotResponse(
            id=robot.id,
            name=robot.name,
            device_id=robot.device_id,
            is_active=robot.is_active,
            last_seen_at=robot.last_seen_at,
            status=status,
        )

    def list(
        self, page: int, page_size: int, q: str, status: RobotStatus | None
    ) -> Page[UserRobotResponse]:
        now = AuthRepository(self.db).now()
        rows, total = self.repository.list(
            page, page_size, q.strip(), True, status, now, name_only=True
        )
        return Page[UserRobotResponse](
            items=[self.response(robot, state) for robot, state in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get(self, robot_id: UUID) -> UserRobotResponse:
        row = self.repository.get_active_with_status(robot_id, AuthRepository(self.db).now())
        if row is None:
            raise AppError("Xe không tồn tại hoặc đã bị vô hiệu hóa.", 404)
        return self.response(*row)
