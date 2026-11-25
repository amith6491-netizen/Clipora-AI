from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from app.api.routes_auth import router as auth_router
from app.api.routes_clips import router as clips_router
from app.api.routes_exports import router as exports_router
from app.api.routes_health import router as health_router
from app.api.routes_videos import router as videos_router
from app.core.config import Settings, get_settings
from app.core.database import DatabaseManager


def create_app(custom_settings: Settings | None = None) -> FastAPI:
    settings = custom_settings or get_settings()
    settings.ensure_dirs()
    db = DatabaseManager(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.db = db
        await db.connect()
        try:
            yield
        finally:
            await db.close()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-powered long video to viral short clips studio.",
        lifespan=lifespan,
    )

    @app.exception_handler(PyMongoError)
    async def mongo_exception_handler(_request: Request, _exc: PyMongoError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Database unavailable: MongoDB is not reachable. Start MongoDB on localhost:27017 and retry."
            },
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(videos_router)
    app.include_router(clips_router)
    app.include_router(exports_router)
    return app


app = create_app()
