from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password
from app.db.locks import lock_admin_membership
from app.models import AuditLog, User
from app.models.enums import UserRole
from app.repositories.admin import UserRepository
from app.repositories.auth import AuthRepository
from app.schemas.admin import UserCreate, UserUpdate


class UserManagementService:
    def __init__(self, db: Session, actor_id: UUID):
        self.db, self.actor_id = db, actor_id
        self.repository = UserRepository(db)

    def _authorize_write(self) -> None:
        lock_admin_membership(self.db)
        actor = self.repository.get(self.actor_id)
        if actor is None or not actor.is_active or actor.role != UserRole.ADMIN:
            raise AppError("Bạn không có quyền truy cập.", 403)

    def get(self, user_id: UUID, *, lock: bool = False) -> User:
        user = self.repository.get(user_id, lock=lock)
        if user is None:
            raise AppError("Không tìm thấy người dùng.", 404)
        return user

    def _audit(self, action: str, user_id: UUID, **metadata) -> None:
        self.db.add(
            AuditLog(
                user_id=self.actor_id,
                action=action,
                event_metadata={"target_user_id": str(user_id), **metadata},
            )
        )

    def _commit(self) -> None:
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise AppError("Username hoặc email đã được sử dụng.", 409) from None

    def create(self, payload: UserCreate) -> User:
        self._authorize_write()
        user = User(
            username=payload.username,
            email=str(payload.email).lower(),
            role=payload.role,
            password_hash=hash_password(payload.password.get_secret_value()),
        )
        self.db.add(user)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            raise AppError("Username hoặc email đã được sử dụng.", 409) from None
        self._audit("user.created", user.id, role=user.role.value)
        self._commit()
        return user

    def update(self, user_id: UUID, payload: UserUpdate) -> User:
        self._authorize_write()
        user = self.get(user_id, lock=True)
        for field in payload.model_fields_set:
            value = getattr(payload, field)
            setattr(user, field, str(value).lower() if field == "email" else value)
        self._audit("user.updated", user.id, changed_fields=sorted(payload.model_fields_set))
        self._commit()
        return user

    def _protect_last_admin(self, user: User) -> None:
        if (
            user.role == UserRole.ADMIN
            and user.is_active
            and self.repository.active_admin_count() <= 1
        ):
            raise AppError("Không thể vô hiệu hóa hoặc hạ quyền Admin cuối cùng.", 409)

    def set_role(self, user_id: UUID, role: UserRole) -> User:
        self._authorize_write()
        user = self.get(user_id, lock=True)
        if user.role != role:
            if role != UserRole.ADMIN:
                self._protect_last_admin(user)
            previous = user.role.value
            user.role = role
            self._audit("user.role_changed", user.id, previous_role=previous, role=role.value)
            self._commit()
        return user

    def set_active(self, user_id: UUID, active: bool) -> User:
        self._authorize_write()
        user = self.get(user_id, lock=True)
        if not active:
            if user.id == self.actor_id:
                raise AppError("Không thể tự vô hiệu hóa tài khoản đang sử dụng.", 409)
            self._protect_last_admin(user)
        if user.is_active != active:
            user.is_active = active
            if not active:
                now = AuthRepository(self.db).now()
                self.repository.revoke_sessions(user.id, now)
                self.repository.close_leases(user.id, now)
            self._audit("user.enabled" if active else "user.disabled", user.id)
            self._commit()
        return user

    def reset_password(self, user_id: UUID, password: str) -> None:
        self._authorize_write()
        user = self.get(user_id, lock=True)
        user.password_hash = hash_password(password)
        self.repository.revoke_sessions(user.id, AuthRepository(self.db).now())
        self._audit("user.password_reset", user.id)
        self._commit()
