from fastapi import Query

from app.api.errors import AppError


def add_test_routes(app):
    @app.get("/api/_test/app-error")
    def app_error():
        raise AppError("material_not_found", "Malzeme bulunamadı.", status_code=404)

    @app.get("/api/_test/crash")
    def crash():
        raise ValueError("içeride bir şey bozuldu")

    @app.get("/api/_test/validate")
    def validate(qty: int = Query(...)):
        return {"qty": qty}


def test_not_found_is_turkish(client):
    r = client.get("/api/yok-boyle-bir-adres")
    assert r.status_code == 404
    err = r.json()["error"]
    assert err["code"] == "http_404"
    assert err["message"] == "İstenen kayıt ya da adres bulunamadı."
    assert err["trace_id"] == r.headers["X-Trace-Id"]


def test_app_error(app, client):
    add_test_routes(app)
    r = client.get("/api/_test/app-error")
    assert r.status_code == 404
    assert r.json()["error"] == {"code": "material_not_found", "message": "Malzeme bulunamadı.",
                                 "trace_id": r.headers["X-Trace-Id"], "details": []}


def test_validation_error(app, client):
    add_test_routes(app)
    r = client.get("/api/_test/validate", params={"qty": "on"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation"
    assert err["details"][0]["field"] == "query.qty"


def test_unexpected_error_has_trace_id(app, client):
    add_test_routes(app)
    r = client.get("/api/_test/crash")
    assert r.status_code == 500
    err = r.json()["error"]
    assert err["code"] == "unexpected"
    assert r.headers["X-Trace-Id"] in err["message"]
    assert "içeride" not in err["message"]  # iç ayrıntı kullanıcıya gösterilmez


def test_docs_closed_by_default(client):
    assert client.get("/api/docs").status_code == 404


def test_pool_timeout_and_connection_error_are_503(app, client):
    """Havuz dolu ya da bağlantı kurulamıyor: 500 değil, anlamlı 503 (docs/08)."""
    from sqlalchemy.exc import OperationalError, TimeoutError as PoolTimeout

    @app.get("/api/_test/pool")
    def pool():
        raise PoolTimeout("QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00")

    @app.get("/api/_test/connect")
    def connect():
        raise OperationalError("connect", {}, Exception("Login timeout expired"))

    for path in ("/api/_test/pool", "/api/_test/connect"):
        r = client.get(path)
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "database_unavailable"
        assert r.json()["error"]["message"] == "Veritabanına bağlanılamıyor; biraz sonra yeniden deneyin."
