from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey


class AuditLog(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_robot_created", "robot_id", "created_at"),
        Index("ix_audit_logs_created_at", "created_at"),
        CheckConstraint("length(trim(action)) > 0", name="action_not_blank"),
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="metadata_object"),
    )

    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    robot_id: Mapped[UUID | None] = mapped_column(ForeignKey("robots.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(100))
    # Declarative reserves the Python attribute "metadata".
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
