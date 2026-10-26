"""Tek tip hata cevabı: {"error": {"code", "message", "trace_id", "details"}}.

Mesajlar Türkçe ve kullanıcıya gösterilebilir. Ayrıntı (yığın izi) yalnız loga yazılır; destek takip numarasıyla bulunur.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logging_setup import trace_id_var

log = logging.getLogger("smartchain.errors")


class AppError(Exception):
    """İş kuralı hatası. code: makinece okunur kısa kod; message: kullanıcıya gösterilecek Türkçe metin."""

    def __init__(self, code: str, message: str, status_code: int = 400, details: list | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []


HTTP_MESSAGES = {
    400: "İstek geçersiz.",
    401: "Oturum açmanız gerekiyor.",
    403: "Bu işlem için yetkiniz yok.",
    404: "İstenen kayıt ya da adres bulunamadı.",
    405: "Bu adres bu işlemi desteklemiyor.",
    409: "İşlem başka bir değişiklikle çakıştı; sayfayı yenileyip tekrar deneyin.",
}


def error_body(code: str, message: str, details: list | None = None) -> dict:
    return {"error": {"code": code, "message": message, "trace_id": trace_id_var.get(), "details": details or []}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        log.warning("%s: %s", exc.code, exc.message)
        return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=exc.status_code)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        message = HTTP_MESSAGES.get(exc.status_code, "İstek tamamlanamadı.")
        return JSONResponse(error_body(f"http_{exc.status_code}", message), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e.get("loc", [])), "problem": e.get("msg", "")}
                   for e in exc.errors()]
        return JSONResponse(error_body("validation", "Gönderilen veri geçersiz.", details), status_code=422)

    # Beklenmeyen hatalar TraceMiddleware'de yakalanır (takip numarasıyla).
