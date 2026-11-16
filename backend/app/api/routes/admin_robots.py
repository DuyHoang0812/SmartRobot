from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies import AuthSettings, Database, no_store, require_admin
from app.models import User
from app.repositories.admin import RobotRepository
from app.repositories.auth import AuthRepository
from app.schemas.admin import (
    CredentialResponse,
    Page,
    RobotCreate,
    RobotResponse,
    RobotStatus,
    RobotUpdate,
    StatusUpdate,
)
from app.services.admin_robots import RobotManagementService

router = APIRouter(
    prefix="/admin/robots",
    tags=["admin-robots"],
    dependencies=[Depends(require_admin), Depends(no_store)],
)
Admin = Annotated[User, Depends(require_admin)]


@router.get("", response_model=Page[RobotResponse])
def list_robots(
    db: Database,
    settings: AuthSettings,
    response: Response,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str, Query(max_length=254)] = "",
    is_active: bool | None = None,
    status: RobotStatus | None = None,
) -> Page[RobotResponse]:
    response.headers["Cache-Control"] = "no-store"
    rows, total = RobotRepository(db, settings.robot_offline_after_seconds).list(
        page, page_size, q.strip(), is_active, status, AuthRepository(db).now()
    )
    return Page[RobotResponse](
        items=[RobotManagementService.serialize(robot, status) for robot, status in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{robot_id}", response_model=RobotResponse)
def get_robot(
    robot_id: UUID, db: Database, settings: AuthSettings, admin: Admin, response: Response
) -> RobotResponse:
    response.headers["Cache-Control"] = "no-store"
    service = RobotManagementService(db, admin.id, settings.robot_offline_after_seconds)
    return service.response(service.get(robot_id))


@router.post("", response_model=CredentialResponse, status_code=201)
def create_robot(
    payload: RobotCreate, db: Database, settings: AuthSettings, admin: Admin, response: Response
) -> CredentialResponse:
    response.headers["Cache-Control"] = "no-store"
    return RobotManagementService(db, admin.id, settings.robot_offline_after_seconds).create(
        payload
    )


@router.patch("/{robot_id}", response_model=RobotResponse)
def update_robot(
    robot_id: UUID, payload: RobotUpdate, db: Database, settings: AuthSettings, admin: Admin
) -> RobotResponse:
    return RobotManagementService(db, admin.id, settings.robot_offline_after_seconds).update(
        robot_id, payload
    )


@router.patch("/{robot_id}/status", response_model=RobotResponse)
def change_status(
    robot_id: UUID, payload: StatusUpdate, db: Database, settings: AuthSettings, admin: Admin
) -> RobotResponse:
    return RobotManagementService(db, admin.id, settings.robot_offline_after_seconds).set_active(
        robot_id, payload.is_active
    )


@router.post("/{robot_id}/credentials/rotate", response_model=CredentialResponse)
def rotate_credential(
    robot_id: UUID, db: Database, settings: AuthSettings, admin: Admin, response: Response
) -> CredentialResponse:
    response.headers["Cache-Control"] = "no-store"
    return RobotManagementService(
        db, admin.id, settings.robot_offline_after_seconds
    ).rotate_credential(robot_id)
