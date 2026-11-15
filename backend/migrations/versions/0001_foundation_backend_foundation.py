"""backend foundation

Revision ID: 0001_foundation
Revises: none
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "robots",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("device_credential_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(device_credential_hash) > 0", name=op.f("ck_robots_credential_hash_not_blank")
        ),
        sa.CheckConstraint(
            "length(trim(device_id)) > 0", name=op.f("ck_robots_device_id_not_blank")
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_robots_name_not_blank")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_robots")),
        sa.UniqueConstraint("device_id", name=op.f("uq_robots_device_id")),
    )
    op.create_index(
        "ix_robots_active_last_seen", "robots", ["is_active", "last_seen_at"], unique=False
    )
    op.create_table(
        "users",
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("USER", "ADMIN", name="user_role", native_enum=False, create_constraint=True),
            server_default="USER",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(password_hash) > 0", name=op.f("ck_users_password_hash_not_blank")
        ),
        sa.CheckConstraint("length(trim(email)) > 0", name=op.f("ck_users_email_not_blank")),
        sa.CheckConstraint("length(trim(username)) > 0", name=op.f("ck_users_username_not_blank")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(
        "uq_users_email_lower", "users", [sa.literal_column("lower(email)")], unique=True
    )
    op.create_index(
        "uq_users_username_lower", "users", [sa.literal_column("lower(username)")], unique=True
    )
    op.create_table(
        "audit_logs",
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("robot_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metadata) = 'object'", name=op.f("ck_audit_logs_metadata_object")
        ),
        sa.CheckConstraint("length(trim(action)) > 0", name=op.f("ck_audit_logs_action_not_blank")),
        sa.ForeignKeyConstraint(
            ["robot_id"],
            ["robots.id"],
            name=op.f("fk_audit_logs_robot_id_robots"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_audit_logs_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)
    op.create_index(
        "ix_audit_logs_robot_created", "audit_logs", ["robot_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_audit_logs_user_created", "audit_logs", ["user_id", "created_at"], unique=False
    )
    op.create_table(
        "control_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("robot_id", sa.Uuid(), nullable=False),
        sa.Column("lease_token_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name=op.f("ck_control_sessions_end_after_start"),
        ),
        sa.CheckConstraint(
            "expires_at > started_at", name=op.f("ck_control_sessions_expiry_after_start")
        ),
        sa.CheckConstraint(
            "length(lease_token_hash) > 0", name=op.f("ck_control_sessions_lease_hash_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["robot_id"],
            ["robots.id"],
            name=op.f("fk_control_sessions_robot_id_robots"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_control_sessions_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_control_sessions")),
        sa.UniqueConstraint("lease_token_hash", name=op.f("uq_control_sessions_lease_token_hash")),
    )
    op.create_index(
        "ix_control_sessions_open_expiry",
        "control_sessions",
        ["expires_at"],
        unique=False,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_index(
        op.f("ix_control_sessions_robot_id"), "control_sessions", ["robot_id"], unique=False
    )
    op.create_index(
        op.f("ix_control_sessions_user_id"), "control_sessions", ["user_id"], unique=False
    )
    op.create_index(
        "uq_control_sessions_open_robot",
        "control_sessions",
        ["robot_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_table(
        "robot_telemetry",
        sa.Column("robot_id", sa.Uuid(), nullable=False),
        sa.Column("distance_cm", sa.Float(), nullable=True),
        sa.Column(
            "mode",
            sa.Enum("MANUAL", "AUTO", name="robot_mode", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column(
            "movement",
            sa.Enum(
                "STOP",
                "FORWARD",
                "BACKWARD",
                "LEFT",
                "RIGHT",
                name="movement",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "distance_cm IS NULL OR (distance_cm >= 0 AND distance_cm < 'Infinity'::float8)",
            name=op.f("ck_robot_telemetry_distance_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["robot_id"],
            ["robots.id"],
            name=op.f("fk_robot_telemetry_robot_id_robots"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_robot_telemetry")),
    )
    op.create_index(
        "ix_robot_telemetry_recorded_at", "robot_telemetry", ["recorded_at"], unique=False
    )
    op.create_index(
        "ix_robot_telemetry_robot_recorded",
        "robot_telemetry",
        ["robot_id", "recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_robot_telemetry_robot_recorded", table_name="robot_telemetry")
    op.drop_index("ix_robot_telemetry_recorded_at", table_name="robot_telemetry")
    op.drop_table("robot_telemetry")
    op.drop_index(
        "uq_control_sessions_open_robot",
        table_name="control_sessions",
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.drop_index(op.f("ix_control_sessions_user_id"), table_name="control_sessions")
    op.drop_index(op.f("ix_control_sessions_robot_id"), table_name="control_sessions")
    op.drop_index(
        "ix_control_sessions_open_expiry",
        table_name="control_sessions",
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.drop_table("control_sessions")
    op.drop_index("ix_audit_logs_user_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_robot_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("uq_users_username_lower", table_name="users")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_robots_active_last_seen", table_name="robots")
    op.drop_table("robots")
