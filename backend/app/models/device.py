from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey


class DeviceSession(UUIDPrimaryKey, Base):
    __tablename__ = "device_sessions"
    __table_args__ = (
        UniqueConstraint("robot_id", "boot_id"),
        Index(
            "uq_device_sessions_open_robot",
            "robot_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        CheckConstraint(
            "heartbeat_sequence >= 0 AND sample_sequence >= 0", name="positive_sequences"
        ),
    )
    robot_id: Mapped[UUID] = mapped_column(ForeignKey("robots.id", ondelete="RESTRICT"))
    boot_id: Mapped[UUID]
    firmware_version: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_sequence: Mapped[int] = mapped_column(BigInteger, server_default="0")
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sample_sequence: Mapped[int] = mapped_column(BigInteger, server_default="0")
    sample_hash: Mapped[str | None] = mapped_column(String(64))
    telemetry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
