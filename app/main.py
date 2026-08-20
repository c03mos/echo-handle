from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import health, tasks
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(health.router)
    app.include_router(tasks.router)

    static_dir = settings.resolve_path(settings.data_dir)
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount(settings.static_mount_path, StaticFiles(directory=str(static_dir)), name='static')
    return app


app = create_app()
