from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.security import token_hash
from app.models import AuthSession, LoginRateLimit, RefreshToken, User


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_user(self, identifier: str) -> User | None:
        identity = identifier.strip().lower()
        column = User.email if "@" in identity else User.username
        # Serialize login with disable/password reset to prevent creating a late session.
        return self.db.scalar(select(User).where(func.lower(column) == identity).with_for_update())

    def get_token(self, raw_token: str) -> RefreshToken | None:
        return self.db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash(raw_token))
        )

    def lock_session(self, session_id: UUID) -> AuthSession | None:
        return self.db.scalar(
            select(AuthSession).where(AuthSession.id == session_id).with_for_update()
        )

    def now(self) -> datetime:
        return self.db.execute(select(func.clock_timestamp())).scalar_one()

    def consume_limit(self, key: str, now: datetime, window_seconds: int) -> int:
        table = LoginRateLimit
        reset = table.window_started_at <= now - timedelta(seconds=window_seconds)
        statement = insert(table).values(key=key, attempts=1, window_started_at=now)
        statement = statement.on_conflict_do_update(
            index_elements=[table.key],
            set_={
                "attempts": case((reset, 1), else_=table.attempts + 1),
                "window_started_at": case((reset, now), else_=table.window_started_at),
            },
        ).returning(table.attempts)
        return self.db.execute(statement).scalar_one()

    def prune_limits(self, now: datetime) -> None:
        self.db.execute(
            delete(LoginRateLimit).where(LoginRateLimit.window_started_at < now - timedelta(days=1))
        )
