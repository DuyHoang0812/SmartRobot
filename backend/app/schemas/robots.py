from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, computed_field

from app.models.enums import RobotStatus


class UserRobotResponse(BaseModel):
    id: UUID
    name: str
    device_id: str
    is_active: bool
    last_seen_at: datetime | None
    status: RobotStatus

    @computed_field
    @property
    def available(self) -> bool:
        # Informational eligibility only. Acquiring a lease will be implemented in Phase 5.
        return self.is_active and self.status == RobotStatus.ONLINE
