from fastapi import APIRouter, Depends

from app.api.dependencies import AuthSettings, Database, no_store
from app.api.device_dependencies import DeviceCredentials, DeviceSessionHeader
from app.schemas.devices import (
    AckInput,
    AckReceipt,
    CommandDelivery,
    DeviceBoot,
    DeviceConnected,
    HeartbeatInput,
    HeartbeatReceipt,
    TelemetryInput,
    TelemetryReceipt,
)
from app.services.devices import DeviceService

router = APIRouter(prefix="/devices", tags=["devices"], dependencies=[Depends(no_store)])


@router.post("/authenticate", response_model=DeviceConnected)
def authenticate(
    payload: DeviceBoot, db: Database, settings: AuthSettings, device: DeviceCredentials
) -> DeviceConnected:
    return DeviceService(db, settings, device.device_id, device.secret).authenticate(payload)


@router.post("/heartbeat", response_model=HeartbeatReceipt)
def heartbeat(
    payload: HeartbeatInput,
    db: Database,
    settings: AuthSettings,
    device: DeviceCredentials,
    session: DeviceSessionHeader,
) -> HeartbeatReceipt:
    return DeviceService(db, settings, device.device_id, device.secret).heartbeat(session, payload)


@router.get("/commands/current", response_model=CommandDelivery)
def command(
    db: Database, settings: AuthSettings, device: DeviceCredentials, session: DeviceSessionHeader
) -> CommandDelivery:
    return DeviceService(db, settings, device.device_id, device.secret).command(session)


@router.post("/commands/ack", response_model=AckReceipt)
def acknowledge(
    payload: AckInput,
    db: Database,
    settings: AuthSettings,
    device: DeviceCredentials,
    session: DeviceSessionHeader,
) -> AckReceipt:
    return DeviceService(db, settings, device.device_id, device.secret).acknowledge(
        session, payload
    )


@router.post("/telemetry", response_model=TelemetryReceipt)
def telemetry(
    payload: TelemetryInput,
    db: Database,
    settings: AuthSettings,
    device: DeviceCredentials,
    session: DeviceSessionHeader,
) -> TelemetryReceipt:
    return DeviceService(db, settings, device.device_id, device.secret).telemetry(session, payload)
