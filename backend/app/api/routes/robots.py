from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import AuthSettings, Database, get_current_active_user, no_store
from app.models.enums import RobotStatus
from app.schemas.admin import Page
from app.schemas.robots import UserRobotResponse
from app.services.robots import UserRobotService

router = APIRouter(
    prefix="/robots",
    tags=["robots"],
    dependencies=[Depends(get_current_active_user), Depends(no_store)],
)


@router.get("", response_model=Page[UserRobotResponse])
def list_robots(
    db: Database,
    settings: AuthSettings,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str, Query(max_length=120)] = "",
    status: RobotStatus | None = None,
) -> Page[UserRobotResponse]:
    return UserRobotService(db, settings.robot_offline_after_seconds).list(
        page, page_size, q, status
    )


@router.get("/{robot_id}", response_model=UserRobotResponse)
def get_robot(robot_id: UUID, db: Database, settings: AuthSettings) -> UserRobotResponse:
    return UserRobotService(db, settings.robot_offline_after_seconds).get(robot_id)
