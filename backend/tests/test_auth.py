import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import AUTH_COOKIE_PATH, CSRF_COOKIE, REFRESH_COOKIE
from app.core.config import Settings
from app.core.errors import AuthError
from app.core.security import hash_password, token_hash
from app.db.session import get_db
from app.main import create_app
from app.models import AuthSession, RefreshToken, User
from app.models.enums import UserRole
from app.services.auth import LOGIN_ERROR, AuthService
from tests.test_database import add_user

pytestmark = pytest.mark.integration
PASSWORD = "Integration-only-password!"
ORIGIN = "http://localhost:5173"


@pytest.fixture(scope="session")
def encoded_password():
    return hash_password(PASSWORD)


@pytest.fixture
def auth_settings(test_database_url):
    return Settings(
        _env_file=None,
        database_url=test_database_url.render_as_string(hide_password=False),
        jwt_secret=secrets.token_urlsafe(48),
        environment="test",
    )


@pytest.fixture
def accounts(db_engine, encoded_password):
    with Session(db_engine) as db:
        user = add_user(
            db, username="operator", email="operator@example.test", password_hash=encoded_password
        )
        admin = add_user(
            db,
            username="administrator",
            email="admin@example.test",
            password_hash=encoded_password,
            role=UserRole.ADMIN,
        )
        db.commit()
        return {"user": user.id, "admin": admin.id}


@pytest.fixture
def auth_client(db_engine, auth_settings, accounts):
    application = create_app(
        auth_settings, session_factory=sessionmaker(db_engine, expire_on_commit=False)
    )

    def override_db():
        with Session(db_engine) as db:
            yield db

    application.dependency_overrides[get_db] = override_db
    with TestClient(application, headers={"Origin": ORIGIN}) as client:
        yield client


def login(client, identifier="operator", password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"identifier": identifier, "password": password})


def csrf(client):
    return {"X-CSRF-Token": client.cookies[CSRF_COOKIE]}


def bearer(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def set_cookies(client, refresh, csrf_value):
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, refresh, domain="testserver.local", path=AUTH_COOKIE_PATH)
    client.cookies.set(CSRF_COOKIE, csrf_value, domain="testserver.local", path="/")


@pytest.mark.parametrize("identity", ["operator", "OPERATOR", "operator@example.test"])
def test_login_with_username_or_email(auth_client, identity, db_engine):
    response = login(auth_client, identity)
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["expires_in"] == 900
    assert response.headers["cache-control"] == "no-store"
    assert "HttpOnly" in response.headers.get_list("set-cookie")[0]
    assert "SameSite=lax" in response.headers.get_list("set-cookie")[0]
    assert "password" not in response.text and "refresh_token" not in response.text
    raw = auth_client.cookies[REFRESH_COOKIE]
    with Session(db_engine) as db:
        stored = db.scalar(select(RefreshToken))
        assert stored.token_hash == token_hash(raw) and stored.token_hash != raw


@pytest.mark.parametrize(
    "identifier,password",
    [
        ("missing", PASSWORD),
        ("missing@example.test", PASSWORD),
        ("operator", "incorrect-password"),
    ],
)
def test_invalid_login_is_generic(auth_client, identifier, password):
    response = login(auth_client, identifier, password)
    assert response.status_code == 401
    assert response.json() == {"detail": LOGIN_ERROR}
    assert REFRESH_COOKIE not in auth_client.cookies


def test_disabled_user_cannot_login(auth_client, db_engine, accounts):
    with Session(db_engine) as db:
        db.get(User, accounts["user"]).is_active = False
        db.commit()
    assert login(auth_client).json() == {"detail": LOGIN_ERROR}


def test_me_does_not_expose_hash(auth_client):
    response = auth_client.get("/api/v1/auth/me", headers=bearer(login(auth_client)))
    assert response.status_code == 200
    assert set(response.json()) == {"id", "username", "email", "role", "is_active"}


@pytest.mark.parametrize("authorization", [None, "Bearer invalid", "Basic abc"])
def test_me_requires_valid_access_token(auth_client, authorization):
    headers = {"Authorization": authorization} if authorization else {}
    assert auth_client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_expired_access_token_is_rejected(auth_client, auth_settings):
    response = login(auth_client)
    claims = jwt.decode(response.json()["access_token"], options={"verify_signature": False})
    claims["exp"] = datetime.now(UTC) - timedelta(seconds=1)
    token = jwt.encode(claims, auth_settings.jwt_secret.get_secret_value(), algorithm="HS256")
    assert (
        auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


def test_disabled_user_loses_access_and_refresh(auth_client, db_engine, accounts):
    access = bearer(login(auth_client))
    with Session(db_engine) as db:
        db.get(User, accounts["user"]).is_active = False
        db.commit()
    assert auth_client.get("/api/v1/auth/me", headers=access).status_code == 401
    assert auth_client.post("/api/v1/auth/refresh", headers=csrf(auth_client)).status_code == 401


def test_refresh_rotates_token_with_absolute_expiry(auth_client, db_engine):
    login(auth_client)
    old = auth_client.cookies[REFRESH_COOKIE]
    with Session(db_engine) as db:
        expiry = db.scalar(select(AuthSession.expires_at))
    response = auth_client.post("/api/v1/auth/refresh", headers=csrf(auth_client))
    assert response.status_code == 200
    assert auth_client.cookies[REFRESH_COOKIE] != old
    with Session(db_engine) as db:
        tokens = list(db.scalars(select(RefreshToken)))
        assert len(tokens) == 2
        assert sum(token.rotated_at is None for token in tokens) == 1
        assert db.scalar(select(AuthSession.expires_at)) == expiry


def test_reuse_revokes_family_and_existing_access(auth_client, db_engine):
    login(auth_client)
    old, csrf_value = auth_client.cookies[REFRESH_COOKIE], auth_client.cookies[CSRF_COOKIE]
    refreshed = auth_client.post("/api/v1/auth/refresh", headers=csrf(auth_client))
    current = auth_client.cookies[REFRESH_COOKIE]
    set_cookies(auth_client, old, csrf_value)
    assert auth_client.post("/api/v1/auth/refresh", headers=csrf(auth_client)).status_code == 401
    assert auth_client.get("/api/v1/auth/me", headers=bearer(refreshed)).status_code == 401
    set_cookies(auth_client, current, csrf_value)
    assert auth_client.post("/api/v1/auth/refresh", headers=csrf(auth_client)).status_code == 401
    with Session(db_engine) as db:
        assert db.scalar(select(AuthSession.revoked_at)) is not None


def test_logout_revokes_session_and_clears_cookies(auth_client):
    access = bearer(login(auth_client))
    old, csrf_value = auth_client.cookies[REFRESH_COOKIE], auth_client.cookies[CSRF_COOKIE]
    response = auth_client.post("/api/v1/auth/logout", headers=csrf(auth_client))
    assert response.status_code == 204
    assert REFRESH_COOKIE not in auth_client.cookies and CSRF_COOKIE not in auth_client.cookies
    assert auth_client.get("/api/v1/auth/me", headers=access).status_code == 401
    set_cookies(auth_client, old, csrf_value)
    assert auth_client.post("/api/v1/auth/refresh", headers=csrf(auth_client)).status_code == 401


def test_logout_only_revokes_corresponding_login(auth_client):
    first = bearer(login(auth_client))
    second = bearer(login(auth_client))
    auth_client.post("/api/v1/auth/logout", headers=csrf(auth_client))
    assert auth_client.get("/api/v1/auth/me", headers=first).status_code == 200
    assert auth_client.get("/api/v1/auth/me", headers=second).status_code == 401


@pytest.mark.parametrize("identity,status", [("operator", 403), ("administrator", 200)])
def test_admin_permissions(auth_client, identity, status):
    assert (
        auth_client.get(
            "/api/v1/admin/check", headers=bearer(login(auth_client, identity))
        ).status_code
        == status
    )


def test_role_changes_are_read_from_database(auth_client, db_engine, accounts):
    access = bearer(login(auth_client, "administrator"))
    with Session(db_engine) as db:
        db.get(User, accounts["admin"]).role = UserRole.USER
        db.commit()
    assert auth_client.get("/api/v1/admin/check", headers=access).status_code == 403


def test_client_cannot_set_own_role(auth_client):
    response = auth_client.post(
        "/api/v1/auth/login",
        json={
            "identifier": "operator",
            "password": PASSWORD,
            "role": "ADMIN",
        },
    )
    assert response.status_code == 422
    assert PASSWORD not in response.text


@pytest.mark.parametrize("path", ["refresh", "logout"])
def test_csrf_header_is_required(auth_client, path):
    login(auth_client)
    assert auth_client.post(f"/api/v1/auth/{path}").status_code == 403
    assert (
        auth_client.post(f"/api/v1/auth/{path}", headers={"X-CSRF-Token": "wrong"}).status_code
        == 403
    )


def test_injected_csrf_cookie_does_not_match_session(auth_client):
    login(auth_client)
    raw = auth_client.cookies[REFRESH_COOKIE]
    set_cookies(auth_client, raw, "injected")
    assert auth_client.post("/api/v1/auth/refresh", headers=csrf(auth_client)).status_code == 403
    assert auth_client.post("/api/v1/auth/logout", headers=csrf(auth_client)).status_code == 403


def test_login_rejects_untrusted_and_missing_origin(auth_client):
    assert (
        auth_client.post(
            "/api/v1/auth/login",
            json={"identifier": "operator", "password": PASSWORD},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    auth_client.headers.pop("origin")
    assert login(auth_client).status_code == 403


def test_refresh_rejects_untrusted_origin(auth_client):
    login(auth_client)
    assert (
        auth_client.post(
            "/api/v1/auth/refresh", headers={**csrf(auth_client), "Origin": "null"}
        ).status_code
        == 403
    )


def test_login_rate_limit_is_shared_and_persisted(auth_client, auth_settings):
    auth_settings.login_identity_limit = 2
    assert login(auth_client, password="incorrect-password").status_code == 401
    assert login(auth_client, password="incorrect-password").status_code == 401
    response = login(auth_client)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "300"


def test_login_ip_limit_ignores_spoofed_forwarded_header(auth_client, auth_settings):
    auth_settings.login_ip_limit = 1
    login(auth_client)
    assert (
        auth_client.post(
            "/api/v1/auth/login",
            json={"identifier": "administrator", "password": PASSWORD},
            headers={"X-Forwarded-For": "203.0.113.77"},
        ).status_code
        == 429
    )


def test_expired_refresh_is_rejected(auth_client, db_engine):
    login(auth_client)
    with Session(db_engine) as db:
        family = db.scalar(select(AuthSession))
        family.created_at = datetime.now(UTC) - timedelta(days=8)
        family.expires_at = datetime.now(UTC) - timedelta(days=1)
        db.commit()
    assert auth_client.post("/api/v1/auth/refresh", headers=csrf(auth_client)).status_code == 401


def test_cors_is_exact_and_supports_credentials(auth_client):
    response = auth_client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrf-token",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert (
        auth_client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        ).status_code
        == 400
    )


def test_concurrent_refresh_detects_reuse(db_engine, auth_settings, accounts):
    with Session(db_engine) as db:
        tokens = AuthService(db, auth_settings).login("operator", PASSWORD, "test-client")
    barrier = Barrier(2)

    def rotate(_):
        with Session(db_engine) as db:
            barrier.wait(timeout=10)
            try:
                AuthService(db, auth_settings).refresh(tokens.refresh_token, tokens.csrf_token)
                return 200
            except AuthError as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(rotate, range(2)))
    assert sorted(results) == [200, 401]
    with Session(db_engine) as db:
        assert db.scalar(select(AuthSession.revoked_at)) is not None


def test_login_window_can_reset(auth_client, db_engine, auth_settings):
    from app.models import LoginRateLimit

    auth_settings.login_identity_limit = 1
    assert login(auth_client).status_code == 200
    assert login(auth_client).status_code == 429
    with Session(db_engine) as db:
        for limit in db.scalars(select(LoginRateLimit)):
            limit.window_started_at = datetime.now(UTC) - timedelta(minutes=10)
        db.commit()
    assert login(auth_client).status_code == 200


def test_secure_cookies_in_secure_configuration(auth_client, auth_settings):
    auth_settings.cookie_secure = True
    response = login(auth_client)
    assert response.status_code == 200
    assert all("Secure" in cookie for cookie in response.headers.get_list("set-cookie"))


def test_authentication_without_secret_fails_closed(auth_client, auth_settings):
    auth_settings.jwt_secret = None
    assert login(auth_client).status_code == 503


def test_password_validation_does_not_echo_plaintext(auth_client):
    response = login(auth_client, password="private")
    assert response.status_code == 422
    assert "private" not in response.text


def test_unknown_refresh_token_clears_cookie(auth_client):
    set_cookies(auth_client, "unknown-token", "csrf")
    assert auth_client.post("/api/v1/auth/refresh", headers=csrf(auth_client)).status_code == 401
    assert REFRESH_COOKIE not in auth_client.cookies
