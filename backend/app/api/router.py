from fastapi import APIRouter

from app.api.routes.admin_robots import router as robots_router
from app.api.routes.admin_users import router as users_router
from app.api.routes.auth import admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.control import router as control_router
from app.api.routes.devices import router as devices_router
from app.api.routes.health import router as health_router
from app.api.routes.robots import router as user_robots_router
from app.websocket.robots import router as websocket_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(users_router)
api_router.include_router(robots_router)
api_router.include_router(user_robots_router)
api_router.include_router(control_router)
api_router.include_router(devices_router)
api_router.include_router(websocket_router)
