import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, type=Type.ID)


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 128:
        raise ValueError("Mật khẩu phải có từ 12 đến 128 ký tự.")
    return password_hasher.hash(password)


@lru_cache(maxsize=1)
def dummy_password_hash() -> str:
    return password_hasher.hash(secrets.token_urlsafe(32))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def random_token() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(user_id: UUID, session_id: UUID, settings: Settings) -> str:
    if settings.jwt_secret is None:
        raise ValueError("JWT_SECRET is required for authentication")
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "sid": str(session_id),
            "jti": str(uuid4()),
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=settings.access_token_minutes),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "type": "access",
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def decode_access_token(token: str, settings: Settings) -> dict:
    if settings.jwt_secret is None:
        raise jwt.InvalidTokenError("Authentication is not configured")
    claims = jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["sub", "sid", "jti", "iat", "nbf", "exp", "iss", "aud", "type"]},
    )
    if claims["type"] != "access":
        raise jwt.InvalidTokenError("Invalid token type")
    try:
        for field in ("sub", "sid", "jti"):
            UUID(claims[field])
    except (ValueError, TypeError, AttributeError):
        raise jwt.InvalidTokenError("Invalid token claims") from None
    return claims
