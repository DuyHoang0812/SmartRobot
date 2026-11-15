from uuid import UUID

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import AuditLog, DeviceSession, Robot
from app.repositories.admin import RobotRepository
from app.repositories.auth import AuthRepository
from app.schemas.admin import CredentialResponse, RobotCreate, RobotResponse, RobotUpdate
from app.services.device_credentials import generate_device_credential


class RobotManagementService:
    def __init__(self, db: Session, actor_id: UUID, offline_seconds: int):
        self.db, self.actor_id = db, actor_id
        self.repository = RobotRepository(db, offline_seconds)

    def get(self, robot_id: UUID, *, lock: bool = False) -> Robot:
        robot = self.repository.get(robot_id, lock=lock)
        if robot is None:
            raise AppError("Không tìm thấy xe robot.", 404)
        return robot

    def response(self, robot: Robot) -> RobotResponse:
        status = self.repository.status(robot.id, AuthRepository(self.db).now())
        return RobotResponse.model_validate({**robot.__dict__, "status": status})

    def _audit(self, action: str, robot: Robot, **metadata) -> None:
        self.db.add(
            AuditLog(
                user_id=self.actor_id, robot_id=robot.id, action=action, event_metadata=metadata
            )
        )

    def _commit(self) -> None:
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise AppError("Device ID đã được sử dụng.", 409) from None

    def create(self, payload: RobotCreate) -> CredentialResponse:
        credential = generate_device_credential()
        robot = Robot(
            name=payload.name, device_id=payload.device_id, device_credential_hash=credential.hashed
        )
        self.db.add(robot)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            raise AppError("Device ID đã được sử dụng.", 409) from None
        self._audit("robot.created", robot)
        self._commit()
        return CredentialResponse(robot=self.response(robot), credential=credential.secret)

    def _invalidate_connection(self, robot: Robot) -> None:
        robot.last_seen_at = None
        now = AuthRepository(self.db).now()
        self.repository.close_leases(robot.id, now)
        self.db.execute(
            update(DeviceSession)
            .where(DeviceSession.robot_id == robot.id, DeviceSession.ended_at.is_(None))
            .values(ended_at=now)
        )

    def update(self, robot_id: UUID, payload: RobotUpdate) -> RobotResponse:
        robot = self.get(robot_id, lock=True)
        if payload.device_id is not None and payload.device_id != robot.device_id:
            self._invalidate_connection(robot)
        for field in payload.model_fields_set:
            setattr(robot, field, getattr(payload, field))
        self._audit("robot.updated", robot, changed_fields=sorted(payload.model_fields_set))
        self._commit()
        return self.response(robot)

    def set_active(self, robot_id: UUID, active: bool) -> RobotResponse:
        robot = self.get(robot_id, lock=True)
        if robot.is_active != active:
            robot.is_active = active
            if not active:
                self._invalidate_connection(robot)
            self._audit("robot.enabled" if active else "robot.disabled", robot)
            self._commit()
        return self.response(robot)

    def rotate_credential(self, robot_id: UUID) -> CredentialResponse:
        robot = self.get(robot_id, lock=True)
        credential = generate_device_credential()
        robot.device_credential_hash = credential.hashed
        self._invalidate_connection(robot)
        self._audit("robot.credential_rotated", robot)
        self._commit()
        return CredentialResponse(robot=self.response(robot), credential=credential.secret)
