from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey


class Robot(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "robots"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("length(trim(device_id)) > 0", name="device_id_not_blank"),
        CheckConstraint("length(device_credential_hash) > 0", name="credential_hash_not_blank"),
        Index("ix_robots_active_last_seen", "is_active", "last_seen_at"),
    )

    name: Mapped[str] = mapped_column(String(120))
    device_id: Mapped[str] = mapped_column(String(128), unique=True)
    device_credential_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
