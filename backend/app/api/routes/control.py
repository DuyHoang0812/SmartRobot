from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import AuthSettings, Database, get_current_active_user, no_store
from app.models import User
from app.models.control import CommandKind
from app.schemas.control import (
    ActionInput,
    CommandView,
    ControlStateView,
    LeaseGrant,
    LeaseInput,
    LeaseView,
    ModeInput,
    MoveInput,
)
from app.services.control import ControlActor, ControlService

router = APIRouter(
    prefix="/robots/{robot_id}/control", tags=["control"], dependencies=[Depends(no_store)]
)


def actor(
    request: Request, user: Annotated[User, Depends(get_current_active_user)]
) -> ControlActor:
    return ControlActor(user.id, request.state.auth_session_id)


Actor = Annotated[ControlActor, Depends(actor)]


@router.post("/acquire", response_model=LeaseGrant, status_code=201)
def acquire(robot_id: UUID, db: Database, settings: AuthSettings, current: Actor) -> LeaseGrant:
    return ControlService(db, settings).acquire(robot_id, current)


@router.post("/renew", response_model=LeaseView)
def renew(
    robot_id: UUID, payload: LeaseInput, db: Database, settings: AuthSettings, current: Actor
) -> LeaseView:
    return ControlService(db, settings).renew(robot_id, current, payload)


@router.post("/release", status_code=204)
def release(
    robot_id: UUID, payload: LeaseInput, db: Database, settings: AuthSettings, current: Actor
) -> None:
    ControlService(db, settings).release(robot_id, current, payload)


@router.get("/state", response_model=ControlStateView)
def state(robot_id: UUID, db: Database, settings: AuthSettings, current: Actor) -> ControlStateView:
    return ControlService(db, settings).state(robot_id, current)


@router.get("/session", response_model=LeaseView)
def session(robot_id: UUID, db: Database, settings: AuthSettings, current: Actor) -> LeaseView:
    return ControlService(db, settings).state(robot_id, current).lease


@router.post("/move", response_model=CommandView, status_code=202)
def move(
    robot_id: UUID, payload: MoveInput, db: Database, settings: AuthSettings, current: Actor
) -> CommandView:
    return ControlService(db, settings).action(
        robot_id, current, payload, CommandKind.MOVE, payload.direction
    )


@router.post("/mode", response_model=CommandView, status_code=202)
def mode(
    robot_id: UUID, payload: ModeInput, db: Database, settings: AuthSettings, current: Actor
) -> CommandView:
    return ControlService(db, settings).action(
        robot_id, current, payload, CommandKind.MODE, mode=payload.mode
    )


@router.post("/stop", response_model=CommandView, status_code=202)
def stop(
    robot_id: UUID, payload: ActionInput, db: Database, settings: AuthSettings, current: Actor
) -> CommandView:
    return ControlService(db, settings).action(robot_id, current, payload, CommandKind.STOP)
