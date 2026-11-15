import asyncio
import logging

from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.repositories.devices import DeviceRepository
from app.services.control import ControlService

logger = logging.getLogger(__name__)


async def control_cleanup_loop(application) -> None:
    def sweep() -> None:
        with application.state.session_factory() as db:
            control = ControlService(db, application.state.settings)
            control.cleanup()
            DeviceRepository(db).cleanup(
                control._now(), application.state.settings.telemetry_retention_days
            )
            db.commit()

    while True:
        await asyncio.sleep(application.state.settings.control_cleanup_interval_seconds)
        try:
            await run_in_threadpool(sweep)
        except SQLAlchemyError:
            logger.warning("Control cleanup unavailable; retrying")
