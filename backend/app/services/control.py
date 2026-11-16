import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import random_token, token_hash
from app.models import (
    AuditLog,
    AuthSession,
    ControlSession,
    Robot,
    RobotCommand,
    RobotControlState,
    User,
)
from app.models.control import CommandKind, CommandStatus, Direction
from app.models.enums import RobotMode
from app.repositories.auth import AuthRepository
from app.repositories.control import ACTIVE_COMMANDS, ControlRepository
from app.schemas.control import (
    AcknowledgementView,
    ActionInput,
    CommandView,
    ControlStateView,
    LeaseGrant,
    LeaseInput,
    LeaseView,
)
from app.services.robot_status import RobotStatusService


@dataclass(frozen=True)
class ControlActor:
    user_id: UUID
    auth_session_id: UUID


@dataclass
class Context:
    robot: Robot
    state: RobotControlState
    lease: ControlSession | None
    now: datetime


class ControlService:
    def __init__(self, db: Session, settings: Settings):
        self.db, self.settings = db, settings
        self.repo = ControlRepository(db)

    def _now(self) -> datetime:
        return AuthRepository(self.db).now()

    def _actor_lock(self, actor: ControlActor) -> None:
        user = self.db.scalar(
            select(User)
            .where(User.id == actor.user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        family = self.db.scalar(
            select(AuthSession)
            .where(AuthSession.id == actor.auth_session_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            not user
            or not user.is_active
            or not family
            or family.user_id != user.id
            or family.revoked_at is not None
            or family.expires_at <= self._now()
        ):
            raise AppError("Phiên đăng nhập đã hết hạn.", 401)

    def online(self, robot: Robot, now: datetime) -> bool:
        return bool(
            robot.is_active
            and robot.last_seen_at
            and now - timedelta(seconds=self.settings.robot_offline_after_seconds)
            <= robot.last_seen_at
            <= now
        )

    def _family_valid(self, lease: ControlSession, now: datetime) -> bool:
        family = (
            self.db.get(AuthSession, lease.auth_session_id, populate_existing=True)
            if lease.auth_session_id
            else None
        )
        user = self.db.get(User, lease.user_id, populate_existing=True)
        return bool(
            family
            and family.revoked_at is None
            and family.expires_at > now
            and user
            and user.is_active
        )

    def _end(self, ctx: Context) -> None:
        if ctx.lease is None:
            return
        previous = ctx.lease
        previous.ended_at = max(ctx.now, previous.started_at)
        self.db.flush()  # Database trigger also fences commands for logout/admin lifecycle paths.
        self.db.refresh(ctx.state)
        self._emit(ctx, previous, CommandKind.STOP, Direction.STOP)
        ctx.lease = None

    def _halt(self, ctx: Context) -> None:
        """Fence motion without returning the user's borrowed robot."""
        self.repo.supersede(ctx.robot.id)
        ctx.state.generation += 1
        ctx.state.mode_pending = True
        ctx.state.confirmed_generation = None

    def prepare(self, robot_id: UUID, actor: ControlActor | None = None) -> Context:
        if actor:
            self._actor_lock(actor)
        robot = self.repo.robot(robot_id)
        if robot is None:
            raise AppError("Không tìm thấy xe robot.", 404)
        lease = self.repo.lease(robot_id)
        state = self.repo.runtime(robot_id)
        ctx = Context(robot, state, lease, self._now())
        owner = self.db.get(User, lease.user_id) if lease else None
        if lease and (not robot.is_active or not owner or not owner.is_active):
            self._end(ctx)
        command = self.repo.latest(state)
        if (
            ctx.lease
            and command
            and command.status in ACTIVE_COMMANDS
            and (not self.online(robot, ctx.now) or not self._family_valid(ctx.lease, ctx.now))
        ):
            self._halt(ctx)
        if command and command.status in ACTIVE_COMMANDS and command.expires_at <= ctx.now:
            command.status = CommandStatus.EXPIRED
            if ctx.lease and (ctx.state.mode_pending or ctx.state.requested_mode == RobotMode.AUTO):
                self._halt(ctx)
        self.db.flush()
        return ctx

    def _emit(
        self,
        ctx: Context,
        lease: ControlSession,
        kind: CommandKind,
        direction: Direction,
        request: ActionInput | None = None,
        fingerprint: str | None = None,
    ) -> RobotCommand:
        self.repo.supersede(ctx.robot.id)
        ctx.state.sequence += 1
        ttl = (
            self.settings.manual_command_ttl_ms
            if kind in [CommandKind.MOVE, CommandKind.STOP]
            else self.settings.mode_command_ttl_ms
        )
        expiry = ctx.now + timedelta(milliseconds=ttl)
        if kind != CommandKind.STOP and lease.expires_at is not None:
            expiry = min(expiry, lease.expires_at)
        command = RobotCommand(
            robot_id=ctx.robot.id,
            control_session_id=lease.id,
            sequence=ctx.state.sequence,
            generation=ctx.state.generation,
            kind=kind,
            mode=ctx.state.requested_mode,
            direction=direction,
            issued_at=ctx.now,
            expires_at=expiry,
            status=CommandStatus.ACCEPTED,
            request_id=request.request_id if request else None,
            request_hash=fingerprint,
            client_sequence=request.client_sequence if request else None,
        )
        self.db.add(command)
        self.db.flush()
        self.repo.prune(ctx.state, self.settings.command_history_limit)
        return command

    def _owned(self, ctx: Context, actor: ControlActor, payload: LeaseInput) -> ControlSession:
        lease = ctx.lease
        if (
            not lease
            or lease.id != payload.control_session_id
            or lease.user_id != actor.user_id
            or lease.auth_session_id != actor.auth_session_id
            or not hmac.compare_digest(
                lease.lease_token_hash, token_hash(payload.lease_token.get_secret_value())
            )
        ):
            self.db.commit()  # Persist cleanup even when denying an old lease.
            raise AppError("Bạn không còn quyền điều khiển xe.", 403)
        return lease

    def _require_online(self, ctx: Context) -> None:
        if not self.online(ctx.robot, ctx.now):
            self.db.commit()
            raise AppError("Xe đang Offline hoặc đã bị vô hiệu hóa.", 409)

    def acquire(self, robot_id: UUID, actor: ControlActor) -> LeaseGrant:
        ctx = self.prepare(robot_id, actor)
        if ctx.lease and ctx.lease.user_id != actor.user_id:
            self.db.commit()
            raise AppError("Xe đang được điều khiển.", 409)
        if not ctx.lease:
            self._require_online(ctx)
        secret = random_token()
        lease = ctx.lease or ControlSession(
            user_id=actor.user_id,
            auth_session_id=actor.auth_session_id,
            robot_id=robot_id,
            lease_token_hash=token_hash(secret),
            started_at=ctx.now,
            expires_at=None,
        )
        # The same user can resume after reload/login; retire old browser credentials.
        lease.auth_session_id = actor.auth_session_id
        lease.lease_token_hash = token_hash(secret)
        lease.last_client_sequence = 0
        lease.expires_at = None
        self.db.add(lease)
        self.db.flush()
        ctx.lease = lease
        ctx.state.generation += 1
        ctx.state.confirmed_generation = None
        ctx.state.requested_mode = RobotMode.MANUAL
        ctx.state.mode_pending = True
        if self.online(ctx.robot, ctx.now):
            self._emit(ctx, lease, CommandKind.MODE, Direction.STOP)
        else:
            # The borrower can recover credentials and return even an offline robot.
            self.repo.supersede(ctx.robot.id)
        self.db.add(AuditLog(user_id=actor.user_id, robot_id=robot_id, action="control.acquired"))
        result = LeaseGrant(
            id=lease.id,
            owned=True,
            expires_at=lease.expires_at,
            lease_token=secret,
            renew_after_ms=min(2000, self.settings.mode_command_ttl_ms // 2),
        )
        self.db.commit()
        return result

    def renew(self, robot_id: UUID, actor: ControlActor, payload: LeaseInput) -> LeaseView:
        ctx = self.prepare(robot_id, actor)
        lease = self._owned(ctx, actor, payload)
        self._require_online(ctx)
        if ctx.state.mode_pending:
            latest = self.repo.latest(ctx.state)
            if not latest or latest.status not in ACTIVE_COMMANDS:
                self._emit(ctx, lease, CommandKind.MODE, Direction.STOP)
        elif ctx.state.requested_mode == RobotMode.AUTO:
            self._emit(ctx, lease, CommandKind.KEEPALIVE, Direction.STOP)
        result = LeaseView(id=lease.id, owned=True, expires_at=lease.expires_at)
        self.db.commit()
        return result

    def release(self, robot_id: UUID, actor: ControlActor, payload: LeaseInput) -> None:
        ctx = self.prepare(robot_id, actor)
        lease = self._owned(ctx, actor, payload)
        self._end(ctx)
        self.db.add(
            AuditLog(
                user_id=actor.user_id,
                robot_id=robot_id,
                action="control.released",
                event_metadata={"control_session_id": str(lease.id)},
            )
        )
        self.db.commit()

    def action(
        self,
        robot_id: UUID,
        actor: ControlActor,
        payload: ActionInput,
        kind: CommandKind,
        direction: Direction = Direction.STOP,
        mode: RobotMode | None = None,
    ) -> CommandView:
        ctx = self.prepare(robot_id, actor)
        lease = self._owned(ctx, actor, payload)
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "session": str(lease.id),
                    "kind": kind.value,
                    "direction": direction.value,
                    "mode": mode.value if mode else None,
                    "client_sequence": payload.client_sequence,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        existing = self.db.scalar(
            select(RobotCommand).where(
                RobotCommand.robot_id == robot_id, RobotCommand.request_id == payload.request_id
            )
        )
        if existing:
            if existing.request_hash != fingerprint:
                raise AppError("Idempotency key đã được dùng cho lệnh khác.", 409)
            result = CommandView.model_validate(existing)
            self.db.commit()
            return result
        if payload.client_sequence <= lease.last_client_sequence:
            raise AppError("Lệnh đã cũ hoặc sai thứ tự.", 409)
        if kind != CommandKind.STOP:
            self._require_online(ctx)
        if kind == CommandKind.MOVE and (
            ctx.state.mode_pending
            or ctx.state.actual_mode != RobotMode.MANUAL
            or ctx.state.requested_mode != RobotMode.MANUAL
            or ctx.state.confirmed_generation != ctx.state.generation
            or not ctx.state.reported_at
            or ctx.state.reported_at
            < ctx.now - timedelta(seconds=self.settings.robot_offline_after_seconds)
        ):
            raise AppError("Chờ thiết bị xác nhận Manual an toàn.", 409)
        lease.last_client_sequence = payload.client_sequence
        if kind in [CommandKind.MODE, CommandKind.STOP]:
            ctx.state.generation += 1
        if kind == CommandKind.MODE:
            ctx.state.requested_mode = mode
            ctx.state.mode_pending = True
            ctx.state.confirmed_generation = None
            self.db.add(
                AuditLog(
                    user_id=actor.user_id,
                    robot_id=robot_id,
                    action="control.mode_requested",
                    event_metadata={"mode": mode.value},
                )
            )
        elif kind == CommandKind.STOP:
            # Keep an acknowledged Manual mode usable after a normal dead-man release.
            if ctx.state.actual_mode == RobotMode.MANUAL and not ctx.state.mode_pending:
                ctx.state.confirmed_generation = ctx.state.generation
            else:
                ctx.state.requested_mode = RobotMode.MANUAL
                ctx.state.mode_pending = True
                ctx.state.confirmed_generation = None
        command = self._emit(ctx, lease, kind, direction, payload, fingerprint)
        result = CommandView.model_validate(command)
        self.db.commit()
        return result

    def state(self, robot_id: UUID, actor: ControlActor) -> ControlStateView:
        ctx = self.prepare(robot_id)
        if not ctx.robot.is_active:
            self.db.commit()
            raise AppError("Không tìm thấy xe robot.", 404)
        owned = bool(ctx.lease and ctx.lease.user_id == actor.user_id)
        lease = LeaseView(
            id=ctx.lease.id if owned else None,
            owned=owned,
            expires_at=ctx.lease.expires_at if ctx.lease else None,
        )
        latest = self.repo.latest(ctx.state)
        state = ctx.state
        last_ack = self.db.scalar(
            select(RobotCommand)
            .where(RobotCommand.robot_id == robot_id, RobotCommand.acknowledged_at.is_not(None))
            .order_by(RobotCommand.acknowledged_at.desc(), RobotCommand.sequence.desc())
            .limit(1)
        )
        fresh = bool(
            self.online(ctx.robot, ctx.now)
            and state.reported_at
            and state.reported_at
            >= ctx.now - timedelta(seconds=self.settings.robot_offline_after_seconds)
        )
        result = ControlStateView(
            robot_id=robot_id,
            status=RobotStatusService(self.settings.robot_offline_after_seconds).get(
                self.db, robot_id, ctx.now
            ),
            lease=lease,
            sequence=state.sequence,
            generation=state.generation,
            requested_mode=state.requested_mode,
            actual_mode=state.actual_mode,
            mode_pending=state.mode_pending,
            actual_movement=state.actual_movement,
            obstacle=state.obstacle,
            distance_cm=state.distance_cm,
            buzzer=state.buzzer,
            reported_at=state.reported_at,
            telemetry_fresh=fresh,
            command=CommandView.model_validate(latest) if latest and owned else None,
            server_time=ctx.now,
            acknowledgement=AcknowledgementView(
                sequence=last_ack.sequence,
                status=last_ack.acknowledgement,
                acknowledged_at=last_ack.acknowledged_at,
            )
            if last_ack
            else None,
        )
        self.db.commit()
        return result

    def disconnect(self, robot_id: UUID, family_id: UUID) -> None:
        ctx = self.prepare(robot_id)
        if ctx.lease and ctx.lease.auth_session_id == family_id:
            self._halt(ctx)
        self.db.commit()

    def cleanup(self) -> None:
        now = self._now()
        for robot_id in self.repo.cleanup_ids(now, self.settings.robot_offline_after_seconds):
            self.prepare(robot_id)
        old_ids = (
            select(RobotCommand.id)
            .where(
                RobotCommand.issued_at < now - timedelta(days=self.settings.command_retention_days),
                RobotCommand.status.not_in(ACTIVE_COMMANDS),
            )
            .limit(1000)
        )
        self.db.execute(delete(RobotCommand).where(RobotCommand.id.in_(old_ids)))
        self.db.commit()
