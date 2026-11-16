"""Keep borrowed robots reserved until explicit return.

Revision ID: 0005_persistent_borrow
Revises: 0004_devices
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_persistent_borrow"
down_revision = "0004_devices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "control_sessions", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=True
    )
    op.execute("UPDATE control_sessions SET expires_at = NULL WHERE ended_at IS NULL")
    # Logout/revocation still stops motion immediately; it does not return the robot.
    op.execute("""
        CREATE OR REPLACE FUNCTION smartrobot_revoke_auth_leases() RETURNS trigger
        LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
        BEGIN
            IF OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL THEN
                UPDATE robot_commands SET status = 'SUPERSEDED'
                WHERE status IN ('ACCEPTED','RECEIVED','EXECUTED','APPLIED')
                  AND control_session_id IN (
                    SELECT id FROM control_sessions
                    WHERE auth_session_id = NEW.id AND ended_at IS NULL);
                UPDATE robot_control_states SET generation = generation + 1,
                    requested_mode = 'MANUAL', mode_pending = true, confirmed_generation = NULL,
                    updated_at = clock_timestamp()
                WHERE robot_id IN (
                    SELECT robot_id FROM control_sessions
                    WHERE auth_session_id = NEW.id AND ended_at IS NULL);
            END IF;
            RETURN NEW;
        END; $$;
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION smartrobot_revoke_auth_leases() RETURNS trigger
        LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
        BEGIN
            IF OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL THEN
                UPDATE control_sessions SET ended_at = GREATEST(clock_timestamp(), started_at)
                WHERE auth_session_id = NEW.id AND ended_at IS NULL;
            END IF;
            RETURN NEW;
        END; $$;
    """)
    op.execute("""
        UPDATE control_sessions SET expires_at = GREATEST(started_at, clock_timestamp())
            + INTERVAL '10 seconds' WHERE expires_at IS NULL
    """)
    op.alter_column(
        "control_sessions", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=False
    )
