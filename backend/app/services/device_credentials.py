import hmac
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import random_token, token_hash
from app.models import Robot


@dataclass(frozen=True)
class DeviceCredential:
    secret: str = field(repr=False)
    hashed: str = field(repr=False)


def generate_device_credential() -> DeviceCredential:
    secret = random_token()
    return DeviceCredential(secret=secret, hashed="sha256:" + token_hash(secret))


def authenticate_device(db: Session, device_id: str, secret: str) -> Robot | None:
    """Callers keep this row lock through heartbeat/telemetry writes and commit.

    Exactly one credential is valid. Rotation replaces its hash, immediately revoking the old one.
    This function does not update heartbeat or commit, and never makes a new robot Online.
    """
    if not secret or len(secret) > 128:
        return None
    robot = db.scalar(
        select(Robot)
        .where(Robot.device_id == device_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    candidate = "sha256:" + token_hash(secret)
    if robot is None or not robot.is_active:
        return None
    if not hmac.compare_digest(robot.device_credential_hash.encode(), candidate.encode()):
        return None
    return robot
