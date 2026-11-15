from datetime import datetime
from enum import StrEnum
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
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import RobotMode


class Direction(StrEnum):
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"
    TURN_LEFT = "TURN_LEFT"
    TURN_RIGHT = "TURN_RIGHT"
    STOP = "STOP"


class Obstacle(StrEnum):
    CLEAR = "CLEAR"
    BLOCKED = "BLOCKED"
    SENSOR_ERROR = "SENSOR_ERROR"


class CommandKind(StrEnum):
    MOVE = "MOVE"
    STOP = "STOP"
    MODE = "MODE"
    KEEPALIVE = "KEEPALIVE"


class CommandStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    RECEIVED = "RECEIVED"
    EXECUTED = "EXECUTED"
    APPLIED = "APPLIED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"


def enum_column(enum_class, name):
    return Enum(enum_class, name=name, native_enum=False, create_constraint=True)


class RobotControlState(Timestamps, Base):
    __tablename__ = "robot_control_states"
    __table_args__ = (
        CheckConstraint("sequence >= 0 AND generation >= 0", name="positive_versions"),
        CheckConstraint(
            "distance_cm IS NULL OR (distance_cm >= 0 AND distance_cm < 'Infinity'::float8)",
            name="distance_valid",
        ),
    )
    robot_id: Mapped[UUID] = mapped_column(
        ForeignKey("robots.id", ondelete="CASCADE"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(BigInteger, server_default="0")
    generation: Mapped[int] = mapped_column(Integer, server_default="0")
    requested_mode: Mapped[RobotMode] = mapped_column(
        enum_column(RobotMode, "requested_mode"), server_default="MANUAL"
    )
    actual_mode: Mapped[RobotMode | None] = mapped_column(enum_column(RobotMode, "actual_mode"))
    mode_pending: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    confirmed_generation: Mapped[int | None] = mapped_column(Integer)
    actual_movement: Mapped[Direction | None] = mapped_column(
        enum_column(Direction, "actual_movement")
    )
    obstacle: Mapped[Obstacle | None] = mapped_column(enum_column(Obstacle, "obstacle"))
    distance_cm: Mapped[float | None] = mapped_column(Float)
    buzzer: Mapped[bool | None] = mapped_column(Boolean)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_report_sequence: Mapped[int] = mapped_column(BigInteger, server_default="0")


class RobotCommand(UUIDPrimaryKey, Base):
    __tablename__ = "robot_commands"
    __table_args__ = (
        UniqueConstraint("robot_id", "sequence", name="uq_robot_commands_sequence"),
        UniqueConstraint("robot_id", "request_id", name="uq_robot_commands_request"),
        CheckConstraint("sequence > 0 AND generation >= 0", name="positive_versions"),
        CheckConstraint("expires_at > issued_at", name="positive_ttl"),
        CheckConstraint(
            "acknowledgement IS NULL OR acknowledgement IN "
            "('RECEIVED','APPLIED','REJECTED','FAILED')",
            name="valid_acknowledgement",
        ),
        Index("ix_robot_commands_expiry", "status", "expires_at"),
        Index("ix_robot_commands_issued_at", "issued_at"),
        Index("ix_robot_commands_robot_ack", "robot_id", "acknowledged_at"),
    )
    robot_id: Mapped[UUID] = mapped_column(ForeignKey("robots.id", ondelete="RESTRICT"))
    control_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("control_sessions.id", ondelete="RESTRICT"), index=True
    )
    sequence: Mapped[int] = mapped_column(BigInteger)
    generation: Mapped[int] = mapped_column(Integer)
    request_id: Mapped[UUID | None]
    request_hash: Mapped[str | None] = mapped_column(String(64))
    client_sequence: Mapped[int | None] = mapped_column(BigInteger)
    kind: Mapped[CommandKind] = mapped_column(enum_column(CommandKind, "command_kind"))
    mode: Mapped[RobotMode] = mapped_column(enum_column(RobotMode, "command_mode"))
    direction: Mapped[Direction] = mapped_column(enum_column(Direction, "command_direction"))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[CommandStatus] = mapped_column(
        enum_column(CommandStatus, "command_status"), server_default="ACCEPTED"
    )
    acknowledgement: Mapped[str | None] = mapped_column(String(16))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledgement_hash: Mapped[str | None] = mapped_column(String(64))
