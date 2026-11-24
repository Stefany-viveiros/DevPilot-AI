from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.core.config import APP_NAME, APP_VERSION, DEFAULT_DATABASE_PATH
from app.db.base import Base
from app.db.session import engine
from app.models import Project  # noqa: F401

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

def create_app(*, initialize_database: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if initialize_database:
            if engine.url.drivername == "sqlite":
                DEFAULT_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
            Base.metadata.create_all(bind=engine)
        yield

    application = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="Fundação do agente de desenvolvimento DevPilot AI.",
        lifespan=lifespan,
    )
    application.include_router(router, prefix="/api/v1")
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.exists():
        application.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @application.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    return application

app = create_app()
