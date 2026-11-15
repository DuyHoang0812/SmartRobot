from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey
from app.models.control import Obstacle, enum_column
from app.models.enums import Movement, RobotMode


class RobotTelemetry(UUIDPrimaryKey, Base):
    __tablename__ = "robot_telemetry"
    __table_args__ = (
        UniqueConstraint("device_session_id", "sample_sequence"),
        CheckConstraint("sample_sequence IS NULL OR sample_sequence > 0", name="sample_positive"),
        CheckConstraint(
            "distance_cm IS NULL OR (distance_cm >= 0 AND distance_cm < 'Infinity'::float8)",
            name="distance_valid",
        ),
        Index("ix_robot_telemetry_robot_recorded", "robot_id", "recorded_at"),
        Index("ix_robot_telemetry_recorded_at", "recorded_at"),
    )

    robot_id: Mapped[UUID] = mapped_column(ForeignKey("robots.id", ondelete="RESTRICT"))
    distance_cm: Mapped[float | None] = mapped_column(Float)
    mode: Mapped[RobotMode] = mapped_column(
        Enum(RobotMode, name="robot_mode", native_enum=False, create_constraint=True)
    )
    movement: Mapped[Movement] = mapped_column(
        Enum(Movement, name="movement", native_enum=False, create_constraint=True)
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    device_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("device_sessions.id", ondelete="RESTRICT")
    )
    sample_sequence: Mapped[int | None] = mapped_column(BigInteger)
    generation: Mapped[int | None] = mapped_column(Integer)
    command_sequence_applied: Mapped[int | None] = mapped_column(BigInteger)
    obstacle_status: Mapped[Obstacle | None] = mapped_column(
        enum_column(Obstacle, "telemetry_obstacle")
    )
    buzzer_active: Mapped[bool | None] = mapped_column(Boolean)
