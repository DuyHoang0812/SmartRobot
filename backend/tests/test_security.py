import secrets
from uuid import uuid4

import jwt
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_is_argon2id_with_random_salt():
    first, second = hash_password("long-enough-password"), hash_password("long-enough-password")
    assert first.startswith("$argon2id$") and first != second
    assert verify_password("long-enough-password", first)
    assert not verify_password("incorrect", first)
    assert not verify_password("incorrect", "invalid-hash")


@pytest.mark.parametrize("password", ["short", "x" * 129])
def test_password_length_validation(password):
    with pytest.raises(ValueError):
        hash_password(password)


def test_jwt_has_required_claims_and_rejects_wrong_signature():
    settings = Settings(
        _env_file=None,
        database_url="postgresql://localhost/example",
        jwt_secret=secrets.token_urlsafe(48),
    )
    token = create_access_token(uuid4(), uuid4(), settings)
    assert decode_access_token(token, settings)["type"] == "access"
    other = Settings(
        _env_file=None,
        database_url="postgresql://localhost/example",
        jwt_secret=secrets.token_urlsafe(48),
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, other)


@pytest.mark.parametrize(
    "overrides",
    [
        {"jwt_secret": "short"},
        {"cors_origins": ["*"]},
        {"environment": "production", "jwt_secret": None},
        {"environment": "production", "cookie_secure": False},
    ],
)
def test_insecure_configuration_is_rejected(overrides):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="postgresql://localhost/example", **overrides)
