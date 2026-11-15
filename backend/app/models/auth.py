from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey


class AuthSession(UUIDPrimaryKey, CreatedAt, Base):
    """One login and its entire refresh-token family; expiry is absolute."""

    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        CheckConstraint("length(csrf_token_hash) = 64", name="csrf_hash_length"),
        Index("ix_auth_sessions_expires_at", "expires_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        CheckConstraint("length(token_hash) = 64", name="token_hash_length"),
        Index(
            "uq_refresh_tokens_current_family",
            "session_id",
            unique=True,
            postgresql_where=text("rotated_at IS NULL"),
        ),
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("auth_sessions.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginRateLimit(Base):
    """Shared, atomic fixed-window limits across API workers. No raw IP/identity stored."""

    __tablename__ = "login_rate_limits"
    __table_args__ = (CheckConstraint("attempts > 0", name="positive_attempts"),)

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
