from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    database_url: SecretStr
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)
    db_connect_timeout_seconds: int = Field(default=5, ge=1, le=30)
    db_statement_timeout_ms: int = Field(default=5000, ge=100, le=60000)
    environment: Literal["development", "test", "production"] = "development"
    jwt_secret: SecretStr | None = Field(default=None, repr=False)
    jwt_issuer: str = "smartrobot"
    jwt_audience: str = "smartrobot-web"
    access_token_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_days: int = Field(default=7, ge=1, le=30)
    cookie_secure: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    login_ip_limit: int = Field(default=30, ge=1, le=1000)
    login_identity_limit: int = Field(default=10, ge=1, le=100)
    login_window_seconds: int = Field(default=300, ge=1, le=3600)
    robot_offline_after_seconds: int = Field(default=15, ge=1, le=300)
    control_lease_seconds: int = Field(default=10, ge=5, le=60)
    manual_command_ttl_ms: int = Field(default=700, ge=300, le=1500)
    mode_command_ttl_ms: int = Field(default=3000, ge=2000, le=5000)
    command_history_limit: int = Field(default=1000, ge=10, le=10000)
    command_retention_days: int = Field(default=7, ge=1, le=30)
    control_cleanup_interval_seconds: float = Field(default=1, ge=0.2, le=5)
    websocket_interval_seconds: float = Field(default=1, ge=0.1, le=2)
    device_allow_insecure_http: bool = False
    device_heartbeat_interval_ms: int = Field(default=2000, ge=500, le=10000)
    device_poll_interval_ms: int = Field(default=100, ge=50, le=200)
    device_telemetry_min_interval_ms: int = Field(default=200, ge=100, le=5000)
    telemetry_retention_days: int = Field(default=7, ge=1, le=30)
    telemetry_history_limit: int = Field(default=10000, ge=10, le=100000)

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value().encode()) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 bytes")
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        if not origins:
            raise ValueError("CORS_ORIGINS must contain explicit origins")
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
                or "*" in origin
            ):
                raise ValueError("CORS_ORIGINS must contain exact HTTP(S) origins without paths")
        return origins

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.environment == "production" and self.device_allow_insecure_http:
            raise ValueError("Production Device API requires HTTPS")
        if self.environment == "production" and (
            self.jwt_secret is None
            or not self.cookie_secure
            or any(not origin.startswith("https://") for origin in self.cors_origins)
        ):
            raise ValueError("Production requires JWT_SECRET, secure cookies and HTTPS origins")
        return self

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except ArgumentError:
            raise ValueError("DATABASE_URL must be a valid PostgreSQL URL") from None
        if url.drivername not in {"postgresql", "postgresql+psycopg"} or not url.database:
            raise ValueError("DATABASE_URL must use PostgreSQL and specify a database")
        return SecretStr(
            url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
