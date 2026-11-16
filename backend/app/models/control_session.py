from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey


class ControlSession(UUIDPrimaryKey, Base):
    __tablename__ = "control_sessions"
    __table_args__ = (
        # A borrowed robot stays reserved until it is explicitly returned.
        Index(
            "uq_control_sessions_open_robot",
            "robot_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index(
            "ix_control_sessions_open_expiry",
            "expires_at",
            postgresql_where=text("ended_at IS NULL"),
        ),
        CheckConstraint("expires_at > started_at", name="expiry_after_start"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="end_after_start"),
        CheckConstraint("length(lease_token_hash) > 0", name="lease_hash_not_blank"),
        CheckConstraint("last_client_sequence >= 0", name="client_sequence_positive"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    robot_id: Mapped[UUID] = mapped_column(ForeignKey("robots.id", ondelete="RESTRICT"), index=True)
    lease_token_hash: Mapped[str] = mapped_column(String(255), unique=True)
    auth_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("auth_sessions.id", ondelete="SET NULL"), index=True
    )
    last_client_sequence: Mapped[int] = mapped_column(BigInteger, server_default="0")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
