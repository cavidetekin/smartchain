"""Her isteğe takip numarası verir, cevaba X-Trace-Id başlığı ekler, isteği loglar ve beklenmeyen hatayı yakalar."""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .errors import error_body
from .logging_setup import trace_id_var

log = logging.getLogger("smartchain.request")


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = uuid.uuid4().hex[:12]
        token = trace_id_var.set(trace_id)
        start = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                log.exception("Beklenmeyen hata: %s %s", request.method, request.url.path)
                message = f"Beklenmeyen bir hata oluştu. Destek için takip numarası: {trace_id}"
                response = JSONResponse(error_body("unexpected", message), status_code=500)
            elapsed = (time.perf_counter() - start) * 1000
            log.info("%s %s → %s (%.0f ms)", request.method, request.url.path, response.status_code, elapsed)
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            trace_id_var.reset(token)
