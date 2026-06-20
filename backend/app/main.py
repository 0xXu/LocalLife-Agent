"""FastAPI application factory for the Python backend."""

from fastapi import FastAPI

from app.api import auth, favorites, routes
from app.api.deps import ServiceContainer, build_services


def create_app(*, services: ServiceContainer | None = None) -> FastAPI:
    app = FastAPI(title="AI Route Planner")
    app.state.services = services or build_services()
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(routes.router, prefix="/api/route", tags=["route"])
    app.include_router(favorites.router, prefix="/api/favorites", tags=["favorites"])
    return app


app = create_app()
