import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, sessionmaker

from app.api.router import api_router
from app.api.routes.auth import clear_auth_cookies
from app.api.routes.health import health
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import create_db_engine, create_session_factory
from app.services.control_cleanup import control_cleanup_loop


def create_app(
    settings: Settings | None = None, session_factory: sessionmaker[Session] | None = None
) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.settings = config
        engine = create_db_engine(config)
        application.state.db_engine = engine
        application.state.session_factory = session_factory or create_session_factory(engine)
        cleanup = asyncio.create_task(control_cleanup_loop(application))
        try:
            yield
        finally:
            cleanup.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup
            engine.dispose()

    application = FastAPI(title="SmartRobot API", version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, error: AppError) -> JSONResponse:
        response = JSONResponse(
            status_code=error.status_code,
            content={"detail": error.detail},
            headers={**error.headers, "Cache-Control": "no-store"},
        )
        if error.clear_cookies:
            clear_auth_cookies(response, config)
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        # FastAPI's default errors echo rejected input, including plaintext passwords.
        errors = [
            {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
            for item in error.errors()
        ]
        return JSONResponse(
            status_code=422, content={"detail": errors}, headers={"Cache-Control": "no-store"}
        )

    application.include_router(api_router, prefix="/api/v1")
    # Preserve the endpoint supplied by the initial project.
    application.add_api_route("/api/health", health, include_in_schema=False)
    return application


app = create_app()
