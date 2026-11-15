import re
from dataclasses import dataclass, field
from ipaddress import ip_address
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from app.api.dependencies import AuthSettings
from app.core.errors import AppError


@dataclass(frozen=True)
class DeviceIdentity:
    device_id: str
    secret: str = field(repr=False)


def credentials(request: Request, settings: AuthSettings) -> DeviceIdentity:
    if request.query_params:
        raise AppError("Device API does not accept query parameters", 400)
    if request.url.scheme != "https" and (
        settings.environment == "production" or not settings.device_allow_insecure_http
    ):
        raise AppError("Device API requires HTTPS", 403)
    if request.url.scheme != "https":
        host = request.client.host if request.client else ""
        try:
            private = ip_address(host).is_private
        except ValueError:
            private = settings.environment == "test" and host == "testclient"
        if not private:
            raise AppError("Development HTTP Device API is restricted to private networks", 403)
    device_id = request.headers.get("x-device-id", "")
    secret = request.headers.get("x-device-secret", "")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{3,128}", device_id) or not 32 <= len(secret) <= 128:
        raise AppError("Device authentication failed", 401, headers={"WWW-Authenticate": "Device"})
    return DeviceIdentity(device_id, secret)


def session_header(request: Request) -> UUID:
    try:
        return UUID(request.headers.get("x-device-session", ""))
    except ValueError:
        raise AppError("Missing or invalid device session; authenticate first", 409) from None


DeviceCredentials = Annotated[DeviceIdentity, Depends(credentials)]
DeviceSessionHeader = Annotated[UUID, Depends(session_header)]
