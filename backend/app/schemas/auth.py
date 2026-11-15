from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.models.enums import UserRole


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    identifier: str = Field(min_length=1, max_length=254)
    password: SecretStr = Field(min_length=12, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    username: str
    email: str
    role: UserRole
    is_active: bool
