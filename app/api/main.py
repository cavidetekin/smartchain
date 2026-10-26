"""Smartchain API uygulaması.

Çalıştırma (geliştirme):  uvicorn app.api.main:app --reload --port 8000
"""
import logging

from fastapi import FastAPI

from app import __version__
from .errors import install_error_handlers
from .logging_setup import setup_logging
from .middleware import TraceMiddleware
from .routers import health
from .settings import get_settings

log = logging.getLogger("smartchain")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings)
    app = FastAPI(title="Smartchain API", version=__version__, redoc_url=None,
                  docs_url="/api/docs" if settings.enable_docs else None,
                  openapi_url="/api/openapi.json")
    app.add_middleware(TraceMiddleware)
    install_error_handlers(app)
    app.include_router(health.router, prefix="/api")
    log.info("Smartchain API %s başladı", __version__)
    return app


app = create_app()
