from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.models.control import CommandKind, CommandStatus, Direction, Obstacle
from app.models.enums import RobotMode, RobotStatus


class ControlInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class LeaseInput(ControlInput):
    control_session_id: UUID
    lease_token: SecretStr = Field(min_length=32, max_length=128)


class ActionInput(LeaseInput):
    request_id: UUID
    client_sequence: int = Field(ge=1, le=9007199254740991, strict=True)


class ModeInput(ActionInput):
    mode: RobotMode


class MoveInput(ActionInput):
    direction: Literal[
        Direction.FORWARD, Direction.BACKWARD, Direction.TURN_LEFT, Direction.TURN_RIGHT
    ]


class LeaseView(BaseModel):
    id: UUID | None = None
    owned: bool = False
    expires_at: datetime | None = None


class LeaseGrant(LeaseView):
    lease_token: str = Field(repr=False)
    renew_after_ms: int = 2000


class CommandView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    command_id: UUID = Field(validation_alias="id")
    robot_id: UUID
    control_session_id: UUID
    sequence: int
    generation: int
    kind: CommandKind
    mode: RobotMode
    direction: Direction
    issued_at: datetime
    expires_at: datetime
    status: CommandStatus
    acknowledgement: str | None = None
    acknowledged_at: datetime | None = None


class AcknowledgementView(BaseModel):
    sequence: int
    status: Literal["RECEIVED", "APPLIED", "REJECTED", "FAILED"]
    acknowledged_at: datetime


class ControlStateView(BaseModel):
    robot_id: UUID
    status: RobotStatus
    lease: LeaseView
    sequence: int
    generation: int
    requested_mode: RobotMode
    actual_mode: RobotMode | None
    mode_pending: bool
    actual_movement: Direction | None
    obstacle: Obstacle | None
    distance_cm: float | None
    buzzer: bool | None
    reported_at: datetime | None
    telemetry_fresh: bool
    command: CommandView | None
    server_time: datetime
    acknowledgement: AcknowledgementView | None = None


class DeviceReport(ControlInput):
    sequence: int = Field(ge=1, strict=True)
    generation: int = Field(ge=0, strict=True)
    acknowledgement: Literal["RECEIVED", "EXECUTED", "REJECTED"]
    actual_mode: RobotMode
    movement: Direction
    safe_mode_switch: bool = False
    obstacle: Obstacle | None = None
    distance_cm: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    buzzer: bool | None = None


class WebSocketAuth(ControlInput):
    type: Literal["authenticate"]
    access_token: SecretStr = Field(min_length=1, max_length=4096)


class DeviceTelemetry(ControlInput):
    sequence: int = Field(ge=0, strict=True)
    generation: int = Field(ge=0, strict=True)
    actual_mode: RobotMode | None = None
    movement: Direction | None = None
    obstacle: Obstacle | None = None
    distance_cm: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    buzzer: bool | None = None


class DeviceCommandEnvelope(BaseModel):
    robot_id: UUID
    sequence: int
    generation: int
    server_time: datetime
    lease_expires_at: datetime | None
    command: CommandView | None
    fail_safe: Literal["STOP"] = "STOP"
