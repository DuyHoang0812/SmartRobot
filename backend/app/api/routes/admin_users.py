from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies import Database, no_store, require_admin
from app.models import User
from app.models.enums import UserRole
from app.repositories.admin import UserRepository
from app.schemas.admin import (
    AdminUserResponse,
    Page,
    PasswordReset,
    RoleUpdate,
    StatusUpdate,
    UserCreate,
    UserUpdate,
)
from app.services.admin_users import UserManagementService

router = APIRouter(
    prefix="/admin/users",
    tags=["admin-users"],
    dependencies=[Depends(require_admin), Depends(no_store)],
)
Admin = Annotated[User, Depends(require_admin)]


@router.get("", response_model=Page[AdminUserResponse])
def list_users(
    db: Database,
    response: Response,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str, Query(max_length=254)] = "",
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> Page[AdminUserResponse]:
    response.headers["Cache-Control"] = "no-store"
    users, total = UserRepository(db).list(page, page_size, q.strip(), role, is_active)
    return Page[AdminUserResponse](
        items=[AdminUserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{user_id}", response_model=AdminUserResponse)
def get_user(user_id: UUID, db: Database, admin: Admin, response: Response) -> User:
    response.headers["Cache-Control"] = "no-store"
    return UserManagementService(db, admin.id).get(user_id)


@router.post("", response_model=AdminUserResponse, status_code=201)
def create_user(payload: UserCreate, db: Database, admin: Admin, response: Response) -> User:
    response.headers["Cache-Control"] = "no-store"
    return UserManagementService(db, admin.id).create(payload)


@router.patch("/{user_id}", response_model=AdminUserResponse)
def update_user(user_id: UUID, payload: UserUpdate, db: Database, admin: Admin) -> User:
    return UserManagementService(db, admin.id).update(user_id, payload)


@router.patch("/{user_id}/role", response_model=AdminUserResponse)
def change_role(user_id: UUID, payload: RoleUpdate, db: Database, admin: Admin) -> User:
    return UserManagementService(db, admin.id).set_role(user_id, payload.role)


@router.patch("/{user_id}/status", response_model=AdminUserResponse)
def change_status(user_id: UUID, payload: StatusUpdate, db: Database, admin: Admin) -> User:
    return UserManagementService(db, admin.id).set_active(user_id, payload.is_active)


@router.post("/{user_id}/reset-password", status_code=204)
def reset_password(
    user_id: UUID, payload: PasswordReset, db: Database, admin: Admin, response: Response
) -> None:
    response.headers["Cache-Control"] = "no-store"
    UserManagementService(db, admin.id).reset_password(user_id, payload.password.get_secret_value())
