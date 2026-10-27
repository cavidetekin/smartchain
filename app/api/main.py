"""Smartchain API uygulaması.

Çalıştırma (geliştirme):  uvicorn app.api.main:app --reload --port 8000
"""
import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app import __version__
from .errors import install_error_handlers
from .logging_setup import setup_logging
from .middleware import TraceMiddleware
from .notify import ConnectionManager, JobWatcher
from .routers import data_versions, health, jobs, lists, ws
from .settings import get_settings

log = logging.getLogger("smartchain")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = None
        if settings.job_watch_seconds > 0:
            task = asyncio.create_task(JobWatcher(app.state.notifier, settings.job_watch_seconds).run())
        yield
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="Smartchain API", version=__version__, redoc_url=None,
                  docs_url="/api/docs" if settings.enable_docs else None,
                  openapi_url="/api/openapi.json", lifespan=lifespan)
    app.state.notifier = ConnectionManager()
    app.add_middleware(TraceMiddleware)
    install_error_handlers(app)
    app.include_router(health.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(data_versions.router, prefix="/api")
    for r in lists.routers:
        app.include_router(r, prefix="/api")
    app.include_router(ws.router, prefix="/api")
    log.info("Smartchain API %s başladı", __version__)
    return app


app = create_app()
