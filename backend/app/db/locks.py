from sqlalchemy import text
from sqlalchemy.orm import Session


def lock_admin_membership(db: Session) -> None:
    # Share the Phase 2 bootstrap lock with every operation affecting admin membership.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('smartrobot_initial_admin'))"))
