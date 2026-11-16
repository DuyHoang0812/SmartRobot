from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.control import CommandKind, CommandStatus, Direction
from app.schemas.control import CommandView, DeviceCommandEnvelope, DeviceReport, DeviceTelemetry
from app.services.control import Context, ControlService
from app.services.device_credentials import authenticate_device


class DeviceControlService:
    """Compatibility adapter for Phase 5 callers; HTTP devices use DeviceService."""

    def __init__(self, db: Session, settings: Settings):
        self.db, self.settings = db, settings
        self.control = ControlService(db, settings)

    def _prepare(self, device_id: str, credential: str) -> Context:
        robot = authenticate_device(self.db, device_id, credential)
        if robot is None:
            raise AppError("Device authentication failed", 401)
        return self.control.prepare(robot.id)

    def telemetry(self, device_id: str, credential: str, report: DeviceTelemetry) -> None:
        ctx = self._prepare(device_id, credential)
        if report.sequence != ctx.state.sequence or report.generation != ctx.state.generation:
            raise AppError("Stale telemetry fence", 409)
        # Telemetry without a command is permitted but cannot acknowledge mode or execution.
        ctx.state.actual_mode = report.actual_mode
        ctx.state.actual_movement = report.movement
        ctx.state.obstacle = report.obstacle
        ctx.state.distance_cm = report.distance_cm
        ctx.state.buzzer = report.buzzer
        ctx.state.reported_at = ctx.now
        ctx.state.last_report_sequence = report.sequence
        self.db.commit()

    def current_command(self, device_id: str, credential: str) -> CommandView | None:
        return self.command_envelope(device_id, credential).command

    def command_envelope(self, device_id: str, credential: str) -> DeviceCommandEnvelope:
        ctx = self._prepare(device_id, credential)
        command = self.control.repo.latest(ctx.state)
        valid = bool(
            command
            and command.generation == ctx.state.generation
            and command.expires_at > ctx.now
            and command.status
            in [CommandStatus.ACCEPTED, CommandStatus.RECEIVED, CommandStatus.EXECUTED]
            and (
                command.kind == CommandKind.STOP
                or (ctx.lease and command.control_session_id == ctx.lease.id)
            )
        )
        result = CommandView.model_validate(command) if valid else None
        envelope = DeviceCommandEnvelope(
            robot_id=ctx.robot.id,
            sequence=ctx.state.sequence,
            generation=ctx.state.generation,
            server_time=ctx.now,
            lease_expires_at=ctx.lease.expires_at if ctx.lease else None,
            command=result,
        )
        self.db.commit()
        # None MUST mean stop/disable autonomy on firmware, never "continue the previous command".
        return envelope

    def report(self, device_id: str, credential: str, report: DeviceReport) -> None:
        ctx = self._prepare(device_id, credential)
        command = self.control.repo.latest(ctx.state)
        if (
            not command
            or command.sequence != report.sequence
            or report.generation != ctx.state.generation
            or command.generation != report.generation
            or command.expires_at <= ctx.now
            or command.status
            not in [CommandStatus.ACCEPTED, CommandStatus.RECEIVED, CommandStatus.EXECUTED]
        ):
            self.db.commit()
            raise AppError("Stale or expired device acknowledgement", 409)
        if command.status == CommandStatus.EXECUTED and report.acknowledgement == "RECEIVED":
            raise AppError("Acknowledgement cannot move backwards", 409)
        command.status = CommandStatus(report.acknowledgement)
        state = ctx.state
        # These fields come exclusively from authenticated device reports, never from REST moves.
        state.actual_mode = report.actual_mode
        state.actual_movement = report.movement
        state.obstacle = report.obstacle
        state.distance_cm = report.distance_cm
        state.buzzer = report.buzzer
        state.reported_at = ctx.now
        state.last_report_sequence = report.sequence
        if report.acknowledgement == "REJECTED":
            self.control._halt(ctx)
            self.db.commit()
            return
        if (
            state.mode_pending
            and command.kind in [CommandKind.MODE, CommandKind.STOP]
            and report.acknowledgement == "EXECUTED"
            and report.safe_mode_switch
            and report.actual_mode == state.requested_mode
            and report.movement == Direction.STOP
        ):
            state.mode_pending = False
            state.confirmed_generation = state.generation
        self.db.commit()
