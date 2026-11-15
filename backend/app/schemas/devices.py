from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.control import Obstacle
from app.models.enums import RobotMode
from app.schemas.control import CommandView, ControlInput


class ActualMovement(StrEnum):
    STOPPED = "STOPPED"
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"
    TURN_LEFT = "TURN_LEFT"
    TURN_RIGHT = "TURN_RIGHT"


class AckStatus(StrEnum):
    RECEIVED = "RECEIVED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class DeviceBoot(ControlInput):
    boot_id: UUID
    firmware_version: str | None = Field(default=None, min_length=1, max_length=64)


class HeartbeatInput(ControlInput):
    heartbeat_sequence: int = Field(ge=1, le=9007199254740991, strict=True)


class AckInput(ControlInput):
    command_id: UUID
    sequence: int = Field(ge=1, le=9007199254740991, strict=True)
    generation: int = Field(ge=0, strict=True)
    status: AckStatus
    safe_mode_switch: bool = False
    actual_mode: RobotMode | None = None
    actual_movement: ActualMovement | None = None

    @model_validator(mode="after")
    def safe_handoff(self) -> "AckInput":
        if self.safe_mode_switch and (
            self.status != AckStatus.APPLIED
            or self.actual_mode is None
            or self.actual_movement != ActualMovement.STOPPED
        ):
            raise ValueError("Safe handoff requires APPLIED, actual mode and STOPPED")
        if not self.safe_mode_switch and (
            self.actual_mode is not None or self.actual_movement is not None
        ):
            raise ValueError("Report actual movement via telemetry")
        return self


class TelemetryInput(ControlInput):
    robot_id: UUID
    sample_sequence: int = Field(ge=1, le=9007199254740991, strict=True)
    sequence: int = Field(ge=0, le=9007199254740991, strict=True)
    generation: int = Field(ge=0, strict=True)
    command_sequence_applied: int | None = Field(default=None, ge=1, strict=True)
    distance_cm: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    obstacle_status: Obstacle
    actual_mode: RobotMode
    actual_movement: ActualMovement
    buzzer_active: bool | None = None


class DeviceConnected(ControlInput):
    protocol_version: Literal[1] = 1
    robot_id: UUID
    device_session_id: UUID
    server_time: datetime
    sequence: int
    generation: int
    heartbeat_interval_ms: int
    offline_timeout_ms: int
    poll_interval_ms: int
    telemetry_min_interval_ms: int
    manual_command_ttl_ms: int
    mode_command_ttl_ms: int


class HeartbeatReceipt(ControlInput):
    robot_id: UUID
    device_session_id: UUID
    heartbeat_sequence: int
    last_seen_at: datetime
    server_time: datetime
    sequence: int
    generation: int
    duplicate: bool


class CommandDelivery(ControlInput):
    robot_id: UUID
    device_session_id: UUID
    server_time: datetime
    sequence: int
    generation: int
    requested_mode: RobotMode
    mode_pending: bool
    control_authorized: bool
    authorization_expires_at: datetime | None
    lease_expires_at: datetime | None
    command: CommandView | None
    fail_safe: Literal["STOP"] = "STOP"
    poll_interval_ms: int


class AckReceipt(ControlInput):
    robot_id: UUID
    command_id: UUID
    sequence: int
    status: AckStatus
    acknowledged_at: datetime
    duplicate: bool


class TelemetryReceipt(ControlInput):
    robot_id: UUID
    sample_sequence: int
    recorded_at: datetime
    duplicate: bool
