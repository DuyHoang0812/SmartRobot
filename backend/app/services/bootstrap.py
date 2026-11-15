from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, SecretStr, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.locks import lock_admin_membership
from app.models import User
from app.models.enums import UserRole


class BootstrapError(ValueError):
    pass


class AdminInput(BaseModel):
    username: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{3,64}$")]
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=128)


def create_initial_admin(db: Session, username: str, email: str, password: str) -> User:
    try:
        data = AdminInput(username=username.strip(), email=email.strip(), password=password)
    except ValidationError:
        raise BootstrapError(
            "Username: 3–64 ký tự chữ/số/_.-; email hợp lệ; mật khẩu: 12–128 ký tự."
        ) from None
    # Serialize bootstrap across CLI processes without locking the entire users table.
    lock_admin_membership(db)
    if db.scalar(select(User.id).where(User.role == UserRole.ADMIN, User.is_active).limit(1)):
        raise BootstrapError("Đã có Admin hoạt động. CLI chỉ dùng để khởi tạo Admin đầu tiên.")
    if db.scalar(
        select(User.id)
        .where(
            or_(
                func.lower(User.username) == data.username.lower(),
                func.lower(User.email) == data.email.lower(),
            )
        )
        .limit(1)
    ):
        raise BootstrapError("Username hoặc email đã được sử dụng.")
    admin = User(
        username=data.username,
        email=str(data.email).lower(),
        role=UserRole.ADMIN,
        password_hash=hash_password(data.password.get_secret_value()),
    )
    db.add(admin)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BootstrapError("Username hoặc email đã được sử dụng.") from None
    return admin
