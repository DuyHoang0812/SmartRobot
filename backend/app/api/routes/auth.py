from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.api.dependencies import (
    AUTH_COOKIE_PATH,
    CSRF_COOKIE,
    REFRESH_COOKIE,
    AuthSettings,
    Database,
    get_current_active_user,
    require_admin,
    require_csrf,
    require_trusted_origin,
)
from app.core.config import Settings
from app.core.errors import AuthError
from app.models import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.services.auth import SESSION_ERROR, AuthService, AuthTokens

router = APIRouter(prefix="/auth", tags=["auth"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    for name, path, httponly in [
        (REFRESH_COOKIE, AUTH_COOKIE_PATH, True),
        (CSRF_COOKIE, "/", False),
    ]:
        response.delete_cookie(
            name, path=path, secure=settings.cookie_secure, httponly=httponly, samesite="lax"
        )


def token_response(response: Response, tokens: AuthTokens, settings: Settings) -> TokenResponse:
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=tokens.max_age,
        path=AUTH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    response.set_cookie(
        CSRF_COOKIE,
        tokens.csrf_token,
        max_age=tokens.max_age,
        path="/",
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TokenResponse(
        access_token=tokens.access_token, expires_in=settings.access_token_minutes * 60
    )


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(require_trusted_origin)])
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Database,
    settings: AuthSettings,
) -> TokenResponse:
    tokens = AuthService(db, settings).login(
        payload.identifier,
        payload.password.get_secret_value(),
        request.client.host if request.client else "unknown",
    )
    return token_response(response, tokens, settings)


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(require_csrf)])
def refresh(
    request: Request, response: Response, db: Database, settings: AuthSettings
) -> TokenResponse:
    raw_token = request.cookies.get(REFRESH_COOKIE)
    if not raw_token:
        raise AuthError(SESSION_ERROR, clear_cookies=True)
    tokens = AuthService(db, settings).refresh(raw_token, request.headers.get("x-csrf-token", ""))
    return token_response(response, tokens, settings)


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
def logout(request: Request, response: Response, db: Database, settings: AuthSettings) -> None:
    AuthService(db, settings).logout(
        request.cookies.get(REFRESH_COOKIE), request.headers.get("x-csrf-token")
    )
    clear_auth_cookies(response, settings)
    response.headers["Cache-Control"] = "no-store"


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_active_user)], response: Response) -> UserResponse:
    response.headers["Cache-Control"] = "no-store"
    return UserResponse.model_validate(user)


@admin_router.get("/check", response_model=UserResponse)
def admin_check(user: Annotated[User, Depends(require_admin)], response: Response) -> UserResponse:
    response.headers["Cache-Control"] = "no-store"
    return UserResponse.model_validate(user)
