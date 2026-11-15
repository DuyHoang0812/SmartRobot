from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StrictBool,
    StringConstraints,
    model_validator,
)

from app.models.enums import RobotStatus, UserRole
from app.schemas.auth import UserResponse

Username = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_.-]{3,64}$")
]
RobotName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
DeviceID = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_.:-]{3,128}$")
]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class UserCreate(InputModel):
    username: Username
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=128)
    role: UserRole = UserRole.USER


class PatchInput(InputModel):
    @model_validator(mode="after")
    def check_fields(self) -> "PatchInput":
        if not self.model_fields_set or any(
            getattr(self, f) is None for f in self.model_fields_set
        ):
            raise ValueError("Cần ít nhất một trường có giá trị hợp lệ.")
        return self


class UserUpdate(PatchInput):
    username: Username | None = None
    email: EmailStr | None = None


class RoleUpdate(InputModel):
    role: UserRole


class StatusUpdate(InputModel):
    is_active: StrictBool


class PasswordReset(InputModel):
    password: SecretStr = Field(min_length=12, max_length=128)


class AdminUserResponse(UserResponse):
    created_at: datetime
    updated_at: datetime


class RobotCreate(InputModel):
    name: RobotName
    device_id: DeviceID


class RobotUpdate(PatchInput):
    name: RobotName | None = None
    device_id: DeviceID | None = None


class RobotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    device_id: str
    is_active: bool
    is_simulated: bool
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
    status: RobotStatus


class CredentialResponse(BaseModel):
    robot: RobotResponse
    credential: str = Field(repr=False)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
