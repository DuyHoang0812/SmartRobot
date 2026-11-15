import hashlib
import math
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models import AuditLog, DeviceSession, RobotCommand, RobotTelemetry
from app.models.control import CommandKind, CommandStatus, Direction
from app.models.enums import Movement, RobotMode
from app.repositories.control import ACTIVE_COMMANDS
from app.repositories.devices import DeviceRepository
from app.schemas.control import CommandView
from app.schemas.devices import (
    AckInput,
    AckReceipt,
    AckStatus,
    ActualMovement,
    CommandDelivery,
    DeviceBoot,
    DeviceConnected,
    HeartbeatInput,
    HeartbeatReceipt,
    TelemetryInput,
    TelemetryReceipt,
)
from app.services.control import Context, ControlService
from app.services.device_credentials import authenticate_device

MOVEMENTS = {
    ActualMovement.STOPPED: Movement.STOP,
    ActualMovement.FORWARD: Movement.FORWARD,
    ActualMovement.BACKWARD: Movement.BACKWARD,
    ActualMovement.TURN_LEFT: Movement.LEFT,
    ActualMovement.TURN_RIGHT: Movement.RIGHT,
}


class DeviceService:
    def __init__(self, db: Session, settings: Settings, device_id: str, secret: str):
        self.db, self.settings = db, settings
        self.device_id, self.secret = device_id, secret
        self.control = ControlService(db, settings)
        self.repo = DeviceRepository(db)

    def _prepare(self) -> Context:
        robot = authenticate_device(self.db, self.device_id, self.secret)
        if robot is None:
            raise AppError(
                "Device authentication failed", 401, headers={"WWW-Authenticate": "Device"}
            )
        return self.control.prepare(robot.id)

    def _session(self, session_id: UUID) -> tuple[Context, DeviceSession]:
        ctx = self._prepare()
        session = self.repo.session(ctx.robot.id)
        if session is None or session.id != session_id:
            self.db.commit()  # Keep safety cleanup even on a rejected old device session.
            raise AppError("Device session is no longer active; authenticate a new boot", 409)
        return ctx, session

    def authenticate(self, payload: DeviceBoot) -> DeviceConnected:
        ctx = self._prepare()
        previous = self.repo.boot(ctx.robot.id, payload.boot_id)
        if previous and previous.ended_at is not None:
            self.db.commit()
            raise AppError("Boot ID has been retired; generate a new boot ID", 409)
        if previous:
            session = previous
        else:
            current = self.repo.session(ctx.robot.id)
            if current:
                current.ended_at = ctx.now
                self.db.flush()
            self.control._end(ctx)
            self.control.repo.supersede(ctx.robot.id)
            ctx.state.generation += 1
            ctx.state.requested_mode = RobotMode.MANUAL
            ctx.state.mode_pending = True
            ctx.state.confirmed_generation = None
            ctx.state.actual_mode = None
            ctx.state.actual_movement = None
            ctx.state.obstacle = None
            ctx.state.distance_cm = None
            ctx.state.buzzer = None
            ctx.state.reported_at = None
            ctx.state.last_report_sequence = 0
            ctx.robot.last_seen_at = None
            session = DeviceSession(
                robot_id=ctx.robot.id,
                boot_id=payload.boot_id,
                firmware_version=payload.firmware_version,
                started_at=ctx.now,
            )
            self.db.add(session)
            self.db.add(AuditLog(robot_id=ctx.robot.id, action="device.boot_registered"))
            self.db.flush()
        result = DeviceConnected(
            robot_id=ctx.robot.id,
            device_session_id=session.id,
            server_time=ctx.now,
            sequence=ctx.state.sequence,
            generation=ctx.state.generation,
            heartbeat_interval_ms=min(
                self.settings.device_heartbeat_interval_ms,
                self.settings.robot_offline_after_seconds * 1000 // 3,
            ),
            offline_timeout_ms=self.settings.robot_offline_after_seconds * 1000,
            poll_interval_ms=self.settings.device_poll_interval_ms,
            telemetry_min_interval_ms=self.settings.device_telemetry_min_interval_ms,
            manual_command_ttl_ms=self.settings.manual_command_ttl_ms,
            mode_command_ttl_ms=self.settings.mode_command_ttl_ms,
        )
        self.db.commit()
        return result

    def heartbeat(self, session_id: UUID, payload: HeartbeatInput) -> HeartbeatReceipt:
        ctx, session = self._session(session_id)
        if payload.heartbeat_sequence < session.heartbeat_sequence:
            self.db.commit()
            raise AppError("Stale heartbeat sequence", 409)
        duplicate = payload.heartbeat_sequence == session.heartbeat_sequence
        if not duplicate:
            session.heartbeat_sequence = payload.heartbeat_sequence
            session.heartbeat_at = ctx.now
            ctx.robot.last_seen_at = ctx.now
        result = HeartbeatReceipt(
            robot_id=ctx.robot.id,
            device_session_id=session.id,
            heartbeat_sequence=session.heartbeat_sequence,
            last_seen_at=session.heartbeat_at,
            server_time=ctx.now,
            sequence=ctx.state.sequence,
            generation=ctx.state.generation,
            duplicate=duplicate,
        )
        self.db.commit()
        return result

    def command(self, session_id: UUID) -> CommandDelivery:
        ctx, session = self._session(session_id)
        command = self.control.repo.latest(ctx.state)
        valid = bool(
            ctx.lease
            and self.control.online(ctx.robot, ctx.now)
            and command
            and command.control_session_id == ctx.lease.id
            and command.generation == ctx.state.generation
            and command.expires_at > ctx.now
            and command.status in ACTIVE_COMMANDS
        )
        result = CommandDelivery(
            robot_id=ctx.robot.id,
            device_session_id=session.id,
            server_time=ctx.now,
            sequence=ctx.state.sequence,
            generation=ctx.state.generation,
            requested_mode=ctx.state.requested_mode if ctx.lease else RobotMode.MANUAL,
            mode_pending=ctx.state.mode_pending,
            control_authorized=valid,
            authorization_expires_at=min(command.expires_at, ctx.lease.expires_at)
            if valid
            else None,
            lease_expires_at=ctx.lease.expires_at if ctx.lease else None,
            command=CommandView.model_validate(command) if valid else None,
            poll_interval_ms=self.settings.device_poll_interval_ms,
        )
        self.db.commit()  # Polling is delivery only, never RECEIVED/APPLIED.
        return result

    def acknowledge(self, session_id: UUID, payload: AckInput) -> AckReceipt:
        ctx, _ = self._session(session_id)
        fingerprint = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
        previous = self.db.get(RobotCommand, payload.command_id)
        if (
            previous
            and previous.robot_id == ctx.robot.id
            and previous.sequence == payload.sequence
            and previous.generation == payload.generation
            and previous.acknowledgement_hash == fingerprint
        ):
            result = AckReceipt(
                robot_id=ctx.robot.id,
                command_id=previous.id,
                sequence=previous.sequence,
                status=payload.status,
                acknowledged_at=previous.acknowledged_at,
                duplicate=True,
            )
            self.db.commit()
            return result
        command = self.control.repo.latest(ctx.state)
        if (
            not ctx.lease
            or not command
            or command.id != payload.command_id
            or command.sequence != payload.sequence
            or command.generation != payload.generation
            or payload.generation != ctx.state.generation
            or command.control_session_id != ctx.lease.id
            or command.expires_at <= ctx.now
        ):
            self.db.commit()
            raise AppError("Stale, expired or foreign command acknowledgement", 409)
        duplicate = command.acknowledgement_hash == fingerprint
        if command.acknowledgement in ["APPLIED", "FAILED", "REJECTED"] and not duplicate:
            raise AppError("Command acknowledgement is terminal", 409)
        if not duplicate and command.status not in ACTIVE_COMMANDS:
            raise AppError("Command is no longer valid", 409)
        if payload.safe_mode_switch and (
            command.kind not in [CommandKind.MODE, CommandKind.STOP]
            or payload.actual_mode != ctx.state.requested_mode
        ):
            raise AppError("Safe handoff does not match requested mode", 409)
        if (
            payload.status == AckStatus.APPLIED
            and ctx.state.mode_pending
            and command.kind in [CommandKind.MODE, CommandKind.STOP]
            and not payload.safe_mode_switch
        ):
            raise AppError("Mode handoff requires an explicit safe stopped acknowledgement", 409)
        if not duplicate:
            command.acknowledgement = payload.status.value
            command.acknowledged_at = ctx.now
            command.acknowledgement_hash = fingerprint
            command.status = CommandStatus(payload.status.value)
            if payload.safe_mode_switch:
                ctx.state.mode_pending = False
                ctx.state.confirmed_generation = ctx.state.generation
                # Explicit stopped handoff report, never inferred from APPLIED alone.
                ctx.state.actual_mode = payload.actual_mode
                ctx.state.actual_movement = Direction.STOP
                ctx.state.obstacle = None
                ctx.state.distance_cm = None
                ctx.state.buzzer = None
                ctx.state.reported_at = ctx.now
                ctx.state.last_report_sequence = command.sequence
            if payload.status in [AckStatus.FAILED, AckStatus.REJECTED]:
                self.control._end(ctx)
        result = AckReceipt(
            robot_id=ctx.robot.id,
            command_id=command.id,
            sequence=command.sequence,
            status=payload.status,
            acknowledged_at=command.acknowledged_at,
            duplicate=duplicate,
        )
        self.db.commit()
        return result

    def telemetry(self, session_id: UUID, payload: TelemetryInput) -> TelemetryReceipt:
        ctx, session = self._session(session_id)
        if payload.robot_id != ctx.robot.id:
            raise AppError("Telemetry belongs to another robot", 403)
        fingerprint = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
        if payload.sample_sequence == session.sample_sequence:
            if fingerprint != session.sample_hash:
                raise AppError("Sample sequence was reused for different telemetry", 409)
            result = TelemetryReceipt(
                robot_id=ctx.robot.id,
                sample_sequence=session.sample_sequence,
                recorded_at=session.telemetry_at,
                duplicate=True,
            )
            self.db.commit()
            return result
        if (
            payload.sample_sequence < session.sample_sequence
            or payload.generation != ctx.state.generation
            or payload.sequence > ctx.state.sequence
            or payload.sequence < ctx.state.last_report_sequence
        ):
            self.db.commit()
            raise AppError("Stale telemetry sample or control fence; fetch current command", 409)
        if payload.command_sequence_applied is not None:
            applied = self.db.scalar(
                select(RobotCommand).where(
                    RobotCommand.robot_id == ctx.robot.id,
                    RobotCommand.sequence == payload.command_sequence_applied,
                    RobotCommand.generation == payload.generation,
                    RobotCommand.acknowledgement == "APPLIED",
                )
            )
            if applied is None or payload.command_sequence_applied > payload.sequence:
                raise AppError("Unknown applied command; acknowledge it before telemetry", 409)
        if session.telemetry_at:
            remaining = (
                session.telemetry_at
                + timedelta(milliseconds=self.settings.device_telemetry_min_interval_ms)
                - ctx.now
            ).total_seconds()
            if remaining > 0:
                raise AppError(
                    "Telemetry rate exceeded",
                    429,
                    headers={"Retry-After": str(max(1, math.ceil(remaining)))},
                )
        session.sample_sequence = payload.sample_sequence
        session.sample_hash = fingerprint
        session.telemetry_at = ctx.now
        self.db.add(
            RobotTelemetry(
                robot_id=ctx.robot.id,
                device_session_id=session.id,
                sample_sequence=payload.sample_sequence,
                generation=payload.generation,
                command_sequence_applied=payload.command_sequence_applied,
                distance_cm=payload.distance_cm,
                mode=payload.actual_mode,
                movement=MOVEMENTS[payload.actual_movement],
                obstacle_status=payload.obstacle_status,
                buzzer_active=payload.buzzer_active,
                recorded_at=ctx.now,
            )
        )
        ctx.state.actual_mode = payload.actual_mode
        ctx.state.actual_movement = (
            Direction.STOP
            if payload.actual_movement == ActualMovement.STOPPED
            else Direction(payload.actual_movement.value)
        )
        ctx.state.obstacle = payload.obstacle_status
        ctx.state.distance_cm = payload.distance_cm
        ctx.state.buzzer = payload.buzzer_active
        ctx.state.reported_at = ctx.now
        ctx.state.last_report_sequence = payload.sequence
        self.db.flush()
        self.repo.prune(ctx.robot.id, self.settings.telemetry_history_limit)
        result = TelemetryReceipt(
            robot_id=ctx.robot.id,
            sample_sequence=payload.sample_sequence,
            recorded_at=ctx.now,
            duplicate=False,
        )
        self.db.commit()
        return result
