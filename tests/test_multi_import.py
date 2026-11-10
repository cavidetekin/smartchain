"""Veri yükle: birden çok Excel dosyası (fonksiyon 03; K-129, K-158) ve şablon bilgisinin dosya açılmadan okunması.

Tablo şablondaki teknik addan anlaşılır; tanınmayan şablon, eski sürüm ve seçimde aynı tabloya ikinci dosya reddedilir (parti oluşmaz); büyük dosyanın
tablosu dosya açılmadan okunur, ön kontrol arka planda; devamda dosya başına mod. Test veritabanında (K-103)."""
import io
from pathlib import Path
from urllib.parse import quote

import pytest
from openpyxl import Workbook as OpenWorkbook, load_workbook
from sqlalchemy import text

from app.api.permissions import KEY_USER
from app.api.repositories import imports as repo
from app.integration import contract
from app.integration.reader import Workbook, quick_identity

from auth_helpers import auth
from test_imports_api import GOOD, batch_row, client, people, xlsx  # noqa: F401 (fikstürler)
from validation_helpers import clean as clean_validation

pytestmark = pytest.mark.db
MATERIAL = [{"LocationCode": "ORM-01", "Code": "MI-1", "Name": "Çoklu", "BaseUom": "ADET", "IsActive": 1, "DefaultSupplyType": "Satın alma"}]


def send(client, user, body, mode="Değişen", skip="", name="dosya.xlsx"):
    return client.post(f"/api/imports?mode={quote(mode)}&skip={quote(skip)}", content=body, headers={**auth(user), "X-File-Name": quote(name)})


def batches(engine) -> int:
    with engine.connect() as c:
        return c.execute(text("SELECT COUNT(*) FROM adm.ImportBatch")).scalar()


def resaved(body: bytes, version: int | None = None) -> bytes:
    """Excel'in yeniden kaydettiği gibi (openpyxl paylaşılan metin tablosuyla yazar); istenirse şablon sürümü değişir."""
    wb = load_workbook(io.BytesIO(body))
    if version is not None:
        ws = wb["_Surum"]
        for row in ws.iter_rows():
            if row[0].value == "Sürüm":
                row[1].value = version
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def test_quick_identity_matches_full_read(tmp_path):
    cases = {"template": xlsx(GOOD), "resaved": resaved(xlsx(GOOD), version=7)}
    plain = OpenWorkbook()
    plain.active.append(["Kod", "Ad"])
    buffer = io.BytesIO()
    plain.save(buffer)
    cases["plain"] = buffer.getvalue()
    for name, body in cases.items():
        path = tmp_path / f"{name}.xlsx"
        path.write_bytes(body)
        with Workbook(path) as wb:
            assert quick_identity(path) == wb.identity(), name
    assert quick_identity(tmp_path / "resaved.xlsx").version == 7
    assert quick_identity(tmp_path / "plain.xlsx").table is None


def test_table_from_file_and_rejections_without_batches(db_engine, client, people):  # noqa: F811
    user = people[KEY_USER]
    try:
        r = send(client, user, xlsx(GOOD), name="kaynak.xlsx")
        assert r.status_code == 200, r.text
        body = r.json()
        assert (body["entity"], body["name"], body["read"], body["mode"]) == ("Resource", "Kaynak", 3, "Değişen")
        before = batches(db_engine)
        r = send(client, user, xlsx(GOOD), skip="Resource")
        assert r.status_code == 409 and r.json()["error"]["code"] == "import_duplicate" and r.json()["error"]["details"][0]["name"] == "Kaynak"
        plain = OpenWorkbook()
        buffer = io.BytesIO()
        plain.save(buffer)
        r = send(client, user, buffer.getvalue())
        assert r.status_code == 422 and r.json()["error"]["code"] == "import_unknown_template"
        old = contract.entity("Resource").version - 1
        r = send(client, user, resaved(xlsx(GOOD), version=old))
        assert r.status_code == 422 and r.json()["error"]["code"] == "import_old_template" and f"v{old}" in r.json()["error"]["message"]
        assert send(client, user, b"bozuk").status_code == 422
        assert batches(db_engine) == before                                                    # reddedilen dosyada parti yok
        r = send(client, user, xlsx(MATERIAL, entity="Material"), skip="Resource", name="malzeme.xlsx")
        assert r.status_code == 200 and r.json()["entity"] == "Material"
    finally:
        clean_validation(db_engine)


def test_continue_with_mode_per_file(db_engine, client, people):  # noqa: F811
    user = people[KEY_USER]
    try:
        batch = send(client, user, xlsx(GOOD)).json()["batch_id"]
        assert client.post(f"/api/imports/{batch}/continue", json={"mode": "Başka"}, headers=auth(user)).status_code == 422
        r = client.post(f"/api/imports/{batch}/continue", json={"mode": "Tam"}, headers=auth(user))
        assert r.status_code == 200 and r.json()["mode"] == "Tam" and batch_row(db_engine, batch)["Status"] == "Alındı"
        other = send(client, user, xlsx(MATERIAL, entity="Material")).json()["batch_id"]
        assert client.post(f"/api/imports/{other}/continue", headers=auth(user)).json()["mode"] == "Değişen"   # gövdesiz: yüklemedeki mod
    finally:
        clean_validation(db_engine)


def test_large_file_is_identified_without_opening(db_engine, client, people, monkeypatch):  # noqa: F811
    monkeypatch.setattr(repo, "read_settings", lambda s: {"ImportSyncMaxMb": 0, "ImportMaxMb": 100, "ImportMaxRows": 200000})
    opened = []
    monkeypatch.setattr(Workbook, "__enter__", lambda self: opened.append(self.path) or (_ for _ in ()).throw(AssertionError("dosya açıldı")))
    r = send(client, people[KEY_USER], xlsx(GOOD), name="buyuk.xlsx")
    assert r.status_code == 202, r.text
    body = r.json()
    assert (body["entity"], body["name"]) == ("Resource", "Kaynak") and body["job_id"] and not opened
    assert batch_row(db_engine, body["batch_id"])["Status"] == "Ön kontrol"
    assert Path(batch_row(db_engine, body["batch_id"])["FilePath"]).exists()
