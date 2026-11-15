import hmac
from collections.abc import Callable
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AuthError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import AuthSession, User
from app.models.enums import UserRole
from app.repositories.auth import AuthRepository
from app.services.auth import SESSION_ERROR

REFRESH_COOKIE = "smartrobot_refresh"
CSRF_COOKIE = "smartrobot_csrf"
AUTH_COOKIE_PATH = "/api/v1/auth"
bearer = HTTPBearer(auto_error=False)
Database = Annotated[Session, Depends(get_db)]


def get_auth_settings(request: Request) -> Settings:
    return request.app.state.settings


AuthSettings = Annotated[Settings, Depends(get_auth_settings)]


def require_trusted_origin(request: Request, settings: AuthSettings) -> None:
    if request.headers.get("origin") not in settings.cors_origins:
        raise AuthError("Nguồn yêu cầu không được phép.", 403)


def require_csrf(request: Request, _: Annotated[None, Depends(require_trusted_origin)]) -> None:
    if request.cookies.get(REFRESH_COOKIE):
        header, cookie = request.headers.get("x-csrf-token"), request.cookies.get(CSRF_COOKIE)
        if (
            not header
            or not cookie
            or len(header) > 128
            or not hmac.compare_digest(header.encode(), cookie.encode())
        ):
            raise AuthError("Yêu cầu CSRF không hợp lệ.", 403)


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Database,
    settings: AuthSettings,
) -> User:
    if credentials is None:
        raise AuthError(SESSION_ERROR)
    try:
        claims = decode_access_token(credentials.credentials, settings)
    except jwt.InvalidTokenError:
        raise AuthError(SESSION_ERROR) from None
    family = db.get(AuthSession, UUID(claims["sid"]))
    if (
        family is None
        or str(family.user_id) != claims["sub"]
        or family.revoked_at is not None
        or family.expires_at <= AuthRepository(db).now()
    ):
        raise AuthError(SESSION_ERROR)
    user = db.get(User, family.user_id)
    if user is None:
        raise AuthError(SESSION_ERROR)
    request.state.auth_session_id = family.id
    return user


def get_current_active_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_active:
        raise AuthError(SESSION_ERROR)
    return user


def require_role(*roles: UserRole) -> Callable[..., User]:
    def dependency(user: Annotated[User, Depends(get_current_active_user)]) -> User:
        if user.role not in roles:
            raise AuthError("Bạn không có quyền truy cập.", 403)
        return user

    return dependency


require_admin = require_role(UserRole.ADMIN)


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
