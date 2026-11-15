from sqlalchemy import Boolean, CheckConstraint, Enum, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import UserRole


class User(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("uq_users_username_lower", func.lower(text("username")), unique=True),
        Index("uq_users_email_lower", func.lower(text("email")), unique=True),
        CheckConstraint("length(trim(username)) > 0", name="username_not_blank"),
        CheckConstraint("length(trim(email)) > 0", name="email_not_blank"),
        CheckConstraint("length(password_hash) > 0", name="password_hash_not_blank"),
    )

    username: Mapped[str] = mapped_column(String(64))
    email: Mapped[str] = mapped_column(String(254))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False, create_constraint=True),
        server_default=UserRole.USER.value,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
