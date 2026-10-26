"""Log düzeni: konsol + günlük dönen dosya (logs/smartchain.log). Her satırda takip numarası (trace_id) bulunur."""
import contextvars
import logging
from logging.handlers import TimedRotatingFileHandler

from .settings import Settings

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        return True


FORMAT = "%(asctime)s %(levelname)-7s [%(trace_id)s] %(name)s: %(message)s"


def setup_logging(settings: Settings) -> None:
    root = logging.getLogger()
    if getattr(root, "_smartchain_configured", False):
        return
    root.setLevel(settings.log_level.upper())
    fmt = logging.Formatter(FORMAT)
    flt = TraceIdFilter()

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.addFilter(flt)
    root.addHandler(console)

    settings.log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        settings.log_dir / "smartchain.log", when="midnight", backupCount=settings.log_retention_days,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.addFilter(flt)
    root.addHandler(file_handler)
    root._smartchain_configured = True  # type: ignore[attr-defined]
