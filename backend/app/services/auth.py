import hmac
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AuthError
from app.core.security import (
    create_access_token,
    dummy_password_hash,
    hash_password,
    password_hasher,
    random_token,
    token_hash,
    verify_password,
)
from app.models import AuthSession, RefreshToken, User
from app.repositories.auth import AuthRepository

LOGIN_ERROR = "Tài khoản hoặc mật khẩu không đúng."
SESSION_ERROR = "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."


@dataclass
class AuthTokens:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    max_age: int


class AuthService:
    def __init__(self, db: Session, settings: Settings):
        self.db, self.settings = db, settings
        self.repository = AuthRepository(db)

    def _tokens(self, user: User, family: AuthSession, csrf: str) -> AuthTokens:
        raw_token = random_token()
        self.db.add(RefreshToken(session_id=family.id, token_hash=token_hash(raw_token)))
        self.db.flush()
        access = create_access_token(user.id, family.id, self.settings)
        max_age = max(0, int((family.expires_at - self.repository.now()).total_seconds()))
        return AuthTokens(access, raw_token, csrf, max_age)

    def login(self, identifier: str, password: str, ip: str) -> AuthTokens:
        if self.settings.jwt_secret is None:
            raise AuthError("Chưa cấu hình xác thực.", 503)
        now = self.repository.now()
        self.repository.prune_limits(now)
        # Sort keys so concurrent requests always acquire rate-limit row locks in the same order.
        limits = {
            token_hash(f"ip:{ip}"): self.settings.login_ip_limit,
            token_hash(
                f"identity:{identifier.strip().lower()}"
            ): self.settings.login_identity_limit,
        }
        blocked = False
        for key, limit in sorted(limits.items()):
            blocked |= (
                self.repository.consume_limit(key, now, self.settings.login_window_seconds) > limit
            )
        self.db.commit()  # Failed logins must also persist their rate-limit counters.
        if blocked:
            raise AuthError(
                "Quá nhiều lần đăng nhập. Vui lòng thử lại sau.",
                429,
                headers={"Retry-After": str(self.settings.login_window_seconds)},
            )
        user = self.repository.find_user(identifier)
        valid = verify_password(password, user.password_hash if user else dummy_password_hash())
        if not user or not valid or not user.is_active:
            raise AuthError(LOGIN_ERROR)
        if password_hasher.check_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        family = AuthSession(
            user_id=user.id,
            csrf_token_hash=token_hash(csrf := random_token()),
            expires_at=self.repository.now() + timedelta(days=self.settings.refresh_token_days),
        )
        self.db.add(family)
        self.db.flush()
        tokens = self._tokens(user, family, csrf)
        self.db.commit()
        return tokens

    def refresh(self, raw_token: str, csrf: str) -> AuthTokens:
        token = self.repository.get_token(raw_token)
        if token is None:
            raise AuthError(SESSION_ERROR, clear_cookies=True)
        family = self.repository.lock_session(token.session_id)
        # A competing rotation may have committed while this request waited on the family lock.
        self.db.refresh(token)
        now = self.repository.now()
        if family is None or not hmac.compare_digest(family.csrf_token_hash, token_hash(csrf)):
            raise AuthError("Yêu cầu CSRF không hợp lệ.", 403)
        if family.revoked_at is not None or family.expires_at <= now:
            raise AuthError(SESSION_ERROR, clear_cookies=True)
        user = self.db.get(User, family.user_id)
        if token.rotated_at is not None or user is None or not user.is_active:
            family.revoked_at = now
            self.db.commit()  # Persist revocation even though the response is an error.
            raise AuthError(SESSION_ERROR, clear_cookies=True)
        token.rotated_at = now
        self.db.flush()  # Free the unique current-token slot before inserting its replacement.
        tokens = self._tokens(user, family, csrf)
        self.db.commit()
        return tokens

    def logout(self, raw_token: str | None, csrf: str | None) -> None:
        if not raw_token:
            return
        token = self.repository.get_token(raw_token)
        if token is None:
            return
        family = self.repository.lock_session(token.session_id)
        if (
            family is None
            or not csrf
            or not hmac.compare_digest(family.csrf_token_hash, token_hash(csrf))
        ):
            raise AuthError("Yêu cầu CSRF không hợp lệ.", 403)
        family.revoked_at = self.repository.now()
        self.db.commit()
