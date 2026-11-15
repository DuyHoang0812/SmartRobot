import asyncio
from uuid import UUID

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.models import AuthSession, User
from app.repositories.auth import AuthRepository
from app.schemas.control import WebSocketAuth
from app.services.control import ControlActor, ControlService

router = APIRouter()


def socket_state(application, robot_id: UUID, token: str):
    settings = application.state.settings
    claims = decode_access_token(token, settings)
    with application.state.session_factory() as db:
        family = db.get(AuthSession, UUID(claims["sid"]))
        user = db.get(User, UUID(claims["sub"]))
        if (
            not family
            or not user
            or not user.is_active
            or family.user_id != user.id
            or family.revoked_at is not None
            or family.expires_at <= AuthRepository(db).now()
        ):
            raise AppError("Invalid authentication", 401)
        actor = ControlActor(user.id, family.id)
        return actor, ControlService(db, settings).state(robot_id, actor).model_dump(mode="json")


def socket_release(application, robot_id: UUID, family_id: UUID) -> None:
    with application.state.session_factory() as db:
        ControlService(db, application.state.settings).disconnect(robot_id, family_id)


@router.websocket("/ws/robots/{robot_id}")
async def robot_socket(websocket: WebSocket, robot_id: UUID) -> None:
    settings = websocket.app.state.settings
    if websocket.headers.get("origin") not in settings.cors_origins or websocket.query_params:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    authenticated = None
    try:
        raw = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        auth = WebSocketAuth.model_validate(raw)
        token = auth.access_token.get_secret_value()
        previous = None
        while True:
            authenticated, data = await run_in_threadpool(
                socket_state, websocket.app, robot_id, token
            )
            fingerprint = {k: v for k, v in data.items() if k != "server_time"}
            if fingerprint != previous:
                await websocket.send_json({"type": "robot.state", "data": data})
                previous = fingerprint
            else:
                await websocket.send_json({"type": "ping", "server_time": data["server_time"]})
            # Consume disconnects promptly. Control commands only use the REST API.
            try:
                message = await asyncio.wait_for(
                    websocket.receive(), timeout=settings.websocket_interval_seconds
                )
                if message["type"] == "websocket.disconnect":
                    break
                await websocket.close(code=1008)
                break
            except TimeoutError:
                pass
    except (jwt.InvalidTokenError, ValidationError, ValueError, TimeoutError):
        await websocket.close(code=4001)
    except AppError as error:
        await websocket.close(code=4001 if error.status_code == 401 else 4003)
    except SQLAlchemyError:
        await websocket.close(code=1011)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        if authenticated:
            try:
                await run_in_threadpool(
                    socket_release, websocket.app, robot_id, authenticated.auth_session_id
                )
            except (SQLAlchemyError, AppError):
                pass  # TTL/sweeper still enforce invalidation if the DB is unavailable here.
