"""Veri kalitesi (K-174; fonksiyon 20, 21; ekran 05): takipli kurallar core'da, kimlik ve devam, silinme, yok say ve yeniden açılma, önem (talep
zinciri), kısmi kapsam, gün dönümü, kuyruk, tarih verilerek tarihli kurallar, talep zinciri yolları, yetkiler ve validasyon kuralında takip.

Sentetik v0 (6.5 durumları dahil) test veritabanında; her test değiştirdiğini geri alır, uyarılar ve işler silinir.
"""
import json
from datetime import date, datetime, timedelta

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import quality
from app.api.main import create_app
from app.api.permissions import END_USER, KEY_USER, SYSTEM_OWNER
from app.data.synthetic import dataset as d
from app.engine import transfer_job
from app.jobs.constants import TYPE_QUALITY
from app.quality import chain, run
from app.validation import catalog as cat

from auth_helpers import auth, ensure_user

pytestmark = pytest.mark.db


def _sql(engine, q, **p):
    """Kendi işleminde; satır döndürüyorsa sonuç tamponlanır (bağlantı kapandıktan sonra da okunur)."""
    with engine.begin() as c:
        r = c.execute(sa.text(q), p)
        return r.freeze()() if r.returns_rows else r


def _clean(engine):
    with engine.begin() as c:
        c.execute(sa.text("DELETE FROM adm.DemandChainPath"))
        c.execute(sa.text("DELETE FROM adm.DataQualityWarning"))
        c.execute(sa.text("DELETE FROM adm.DemandChain"))
        c.execute(sa.text("DELETE FROM adm.Job WHERE JobType = :t"), {"t": TYPE_QUALITY})


@pytest.fixture(scope="module")
def people(db_engine):
    with db_engine.begin() as c:
        return {SYSTEM_OWNER: ensure_user(c, "pytest.dq.owner", SYSTEM_OWNER), KEY_USER: ensure_user(c, "pytest.dq.key", KEY_USER),
                END_USER: ensure_user(c, "pytest.dq.end", END_USER)}


@pytest.fixture
def eng(db_engine):
    _clean(db_engine)
    yield db_engine
    _clean(db_engine)


def check(engine, tables=None, day=None) -> dict:
    with Session(engine) as s:
        return run.run(s, tables, day)


def warning(engine, code, entity=None):
    q = "SELECT * FROM adm.DataQualityWarning WHERE CheckCode = :c" + (" AND EntityName = :e" if entity else "")
    return [dict(r) for r in _sql(engine, q, c=code, e=entity).mappings()]


def core_id(engine, table, **match):
    where = " AND ".join(f"{k} = :{k}" for k in match)
    return _sql(engine, f"SELECT Id FROM core.[{table}] WHERE VersionTo IS NULL AND {where}", **match).scalar_one()


def material(engine, code):
    return core_id(engine, "Material", Code=code)


def deep_supplier_row(engine):
    return core_id(engine, "MaterialSupplier", MaterialId=material(engine, d.DEEP_MATERIAL),
                   SupplierId=_sql(engine, "SELECT Id FROM core.Supplier WHERE Code = :c AND VersionTo IS NULL", c=d.DEEP_SUPPLIER).scalar_one())


# ------------------------------------------------------------------ kontrol

def test_tracked_rules_run_on_core_and_identity_continues(eng):
    """Durum 6 (MS.NO_LEADTIME) core'da: Yeni, Yüksek (MAM-002'nin ağacında); ikinci kontrolde Açık, ilk görülme korunur. Durum 7 Normal."""
    stats = check(eng)
    assert stats["rules"] > 40 and stats["added"] > 0
    ms = [w for w in warning(eng, "MS.NO_LEADTIME") if w["RecordKey"] == str(deep_supplier_row(eng))]
    assert len(ms) == 1 and (ms[0]["State"], ms[0]["Importance"], ms[0]["Source"]) == ("Yeni", "Yüksek", "Kural")
    assert ms[0]["RecordLabel"] == f"Malzeme: {d.DEEP_MATERIAL} · Tedarikçi: {d.DEEP_SUPPLIER}" and ms[0]["FixField"] == "FixedLeadTimeDays"
    bom = warning(eng, "BOM.ZERO_QTY")
    assert bom and {w["Importance"] for w in bom if w["RecordLabel"].startswith(f"Üretilen malzeme: {d.NO_DEMAND_MATERIAL} · ")} == {"Normal"}
    cap = warning(eng, "SC.RES_NO_CAPACITY")
    # K-185: ne kendisinde ne grubunda çalışma düzeni olan kaynak; bütün gruplar için çıkar. Önem: grup kritik ve talep zincirinde ise Yüksek
    by_label = {w["RecordLabel"]: w for w in cap}
    assert sorted(by_label) == sorted([f"Kaynak: {d.NO_CAPACITY_RESOURCE}", f"Kaynak: {d.FASON_NO_CAPACITY}"])
    critical, fason = by_label[f"Kaynak: {d.NO_CAPACITY_RESOURCE}"], by_label[f"Kaynak: {d.FASON_NO_CAPACITY}"]
    assert (critical["Importance"], fason["Importance"]) == ("Yüksek", "Normal") and critical["Source"] == "Smartchain" and critical["FixField"] is None
    assert critical["Message"] == f"Kapasite tanımsız (çalışma düzeni yok): {d.NO_CAPACITY_RESOURCE}"
    conflict = warning(eng, "SC.RES_GROUP_CONFLICT")                 # CG-MON (7,5) ve CG-KAL (7,0) gruplarının ikisine üye işçiler
    both = {r[0] for r in _sql(eng, "SELECT r.Code FROM core.Resource r WHERE r.VersionTo IS NULL AND (SELECT COUNT(*) FROM core.ResourceGroupMember m "
                                    "JOIN core.ResourceGroup g ON g.Id = m.ResourceGroupId AND g.VersionTo IS NULL WHERE m.ResourceId = r.Id AND m.VersionTo IS NULL "
                                    "AND g.Code IN (:a, N'CG-KAL')) = 2", a=d.LABOR_GROUP).all()}
    assert both and {w["RecordLabel"] for w in conflict} >= {f"Kaynak: {code}" for code in both} and {w["Importance"] for w in conflict} <= {"Normal", "Yüksek"}
    first = ms[0]["FirstSeenAt"]
    check(eng)
    again = [w for w in warning(eng, "MS.NO_LEADTIME") if w["RecordKey"] == ms[0]["RecordKey"]][0]
    assert (again["Id"], again["State"], again["FirstSeenAt"]) == (ms[0]["Id"], "Açık", first)
    assert not warning(eng, "SO.DELIVERED")  # takip Hayır olan kural core'da çalışmaz


def test_removed_problem_deletes_even_ignored_and_change_reopens(eng, people):
    row = deep_supplier_row(eng)
    check(eng)
    w = [x for x in warning(eng, "MS.NO_LEADTIME") if x["RecordKey"] == str(row)][0]
    with Session(eng) as s:
        assert quality.ignore.ignore(s, people[KEY_USER], [w["Id"]], "Numune") == 1
        s.commit()
    check(eng)
    assert [x["State"] for x in warning(eng, "MS.NO_LEADTIME") if x["RecordKey"] == str(row)] == ["Yok sayıldı"]   # sorun sürüyor, korunur
    _sql(eng, "INSERT INTO adm.FieldChange (TableName, RecordKey, FieldName, ChangeType, OldValue, NewValue, At, Source) "
              "VALUES (N'MaterialSupplier', :k, N'Priority', N'Değişti', N'1', N'2', DATEADD(second, 5, SYSUTCDATETIME()), N'Aktarım')", k=str(row))
    try:
        check(eng)
        w2 = [x for x in warning(eng, "MS.NO_LEADTIME") if x["RecordKey"] == str(row)][0]
        assert (w2["State"], w2["IgnoreReason"]) == ("Açık", None)                                          # kayıt değişti: yeniden Açık
        with Session(eng) as s:
            quality.ignore.ignore(s, people[KEY_USER], [w2["Id"]], "Yine numune")
            s.commit()
        _sql(eng, "UPDATE core.MaterialSupplier SET FixedLeadTimeDays = 5 WHERE Id = :i AND VersionTo IS NULL", i=row)
        check(eng)
        assert not [x for x in warning(eng, "MS.NO_LEADTIME") if x["RecordKey"] == str(row)]               # sorun kalktı: yok sayılan da silinir
    finally:
        _sql(eng, "UPDATE core.MaterialSupplier SET FixedLeadTimeDays = NULL WHERE Id = :i AND VersionTo IS NULL", i=row)
        _sql(eng, "DELETE FROM adm.FieldChange WHERE TableName = N'MaterialSupplier' AND RecordKey = :k AND FieldName = N'Priority' AND NewValue = N'2'", k=str(row))


def test_partial_scope_keeps_other_tables(eng):
    check(eng)
    before = len(warning(eng, "MS.NO_LEADTIME"))
    assert before
    stats = check(eng, {"Stock"})
    assert len(warning(eng, "MS.NO_LEADTIME")) == before and stats["removed"] == 0
    assert stats["rules"] < 15                                                                              # yalnız Stok'u okuyan kurallar


def test_importance_follows_the_demand_chain(eng):
    """Talebi gelen malzemenin uyarısı Yüksek olur: durum 7'nin malzemesine sipariş açılınca Normal → Yüksek."""
    check(eng)
    alt = material(eng, d.NO_DEMAND_MATERIAL)
    so = _sql(eng, "SELECT TOP 1 Id FROM core.SalesOrderLine WHERE VersionTo IS NULL AND OpenQuantity > 0 ORDER BY Id").scalar_one()
    old = _sql(eng, "SELECT MaterialId FROM core.SalesOrderLine WHERE Id = :i AND VersionTo IS NULL", i=so).scalar_one()
    try:
        _sql(eng, "UPDATE core.SalesOrderLine SET MaterialId = :m WHERE Id = :i AND VersionTo IS NULL", m=alt, i=so)
        check(eng)
        assert {w["Importance"] for w in warning(eng, "BOM.ZERO_QTY") if w["RecordLabel"].startswith(f"Üretilen malzeme: {d.NO_DEMAND_MATERIAL} · ")} == {"Yüksek"}
    finally:
        _sql(eng, "UPDATE core.SalesOrderLine SET MaterialId = :m WHERE Id = :i AND VersionTo IS NULL", m=old, i=so)
    with Session(eng) as s:
        counts = chain.rebuild(s, date.today())
        s.commit()
    assert counts["Material"] > 100 and counts.get("MaterialReference") == 1 and counts.get("Forecast") == 3
    isolated = material(eng, d.ISOLATED_MATERIAL)
    assert not _sql(eng, "SELECT 1 FROM adm.DemandChain WHERE EntityName = N'Material' AND RecordId = :m", m=isolated).first()


def test_record_label_uses_field_definition_labels(eng):
    """Kayıt metnindeki alan adları veri sözlüğünden (K-88): etiket değişince sonraki kontrolde yeni etiketle."""
    old = _sql(eng, "SELECT Label FROM adm.FieldDefinition WHERE TableName = N'MaterialSupplier' AND FieldName = N'MaterialId'").scalar_one()
    try:
        _sql(eng, "UPDATE adm.FieldDefinition SET Label = N'Parça' WHERE TableName = N'MaterialSupplier' AND FieldName = N'MaterialId'")
        check(eng)
        labels = {w["RecordLabel"] for w in warning(eng, "MS.NO_LEADTIME")}
        assert f"Parça: {d.DEEP_MATERIAL} · Tedarikçi: {d.DEEP_SUPPLIER}" in labels
    finally:
        _sql(eng, "UPDATE adm.FieldDefinition SET Label = :l WHERE TableName = N'MaterialSupplier' AND FieldName = N'MaterialId'", l=old)


def test_dated_rules_follow_the_given_day(eng):
    """Gün dönümü demosu: verilen günle SO-1044 (teslim bugün) geçmiş olur; bugünle kontrol listeyi geri alır."""
    today = date.today()
    check(eng, day=today + timedelta(days=1))
    labels = {w["RecordLabel"] for w in warning(eng, "SO.PAST_DUE")}
    assert f"Sipariş no: {d.DUE_TODAY_ORDER} · Satır no: 1" in labels and f"Sipariş no: {d.PAST_DUE_ORDER} · Satır no: 1" in labels
    check(eng)
    labels = {w["RecordLabel"] for w in warning(eng, "SO.PAST_DUE")}
    assert f"Sipariş no: {d.PAST_DUE_ORDER} · Satır no: 1" in labels and f"Sipariş no: {d.DUE_TODAY_ORDER} · Satır no: 1" not in labels


def test_demand_chain_paths(eng):
    check(eng)
    w = [x for x in warning(eng, "MS.NO_LEADTIME") if x["RecordKey"] == str(deep_supplier_row(eng))][0]
    with Session(eng) as s:
        out = chain.write_paths(s, w["Id"], w["EntityName"], w["RecordKey"], date.today())
        rows = [dict(r) for r in s.execute(sa.select(chain.PATH).where(chain.PATH.c.WarningId == w["Id"])).mappings()]
    assert out["count"] == len(rows) > 0 and not out["truncated"]
    paths = {r["MaterialPath"] for r in rows}
    assert any(p.startswith("MAM-002 → ALT-004") and p.endswith(d.DEEP_MATERIAL) for p in paths)
    assert {r["DemandType"] for r in rows} <= {"Satış siparişi", "Tahmin"}
    with Session(eng) as s:
        rows, cut = chain.paths(s, "Material", material(eng, "HAM-001"), date.today(), limit=2)
    assert len(rows) == 2 and cut


# ------------------------------------------------------------------ iş, kuyruk, tetikler

def test_enqueue_merges_and_daily_due(eng, people):
    with Session(eng) as s:
        a = quality.enqueue(s, {"Stock"}, quality.TRIGGER_MANUAL, people[KEY_USER])
        b = quality.enqueue(s, {"BOM"}, quality.TRIGGER_TRANSFER)
        assert a == b
        payload = json.loads(s.execute(sa.text("SELECT Payload FROM adm.Job WHERE Id = :i"), {"i": a}).scalar_one())
        assert payload["tables"] == ["BOM", "Stock"]
        assert quality.enqueue(s, None, quality.TRIGGER_DAILY) == a
        assert json.loads(s.execute(sa.text("SELECT Payload FROM adm.Job WHERE Id = :i"), {"i": a}).scalar_one())["tables"] is None
        dev = quality.enqueue(s, None, quality.TRIGGER_DEV, day=date(2030, 1, 1))
        assert dev != a                                                                                     # verilen gün: ayrı iş
        assert not quality.daily_due(s, datetime.now())                                                     # bugün iş var
        s.execute(sa.text("UPDATE adm.Job SET CreatedAt = DATEADD(day, -2, CreatedAt) WHERE JobType = :t"), {"t": TYPE_QUALITY})
        s.commit()
        assert quality.daily_due(s, datetime.now())


def test_transfer_and_manual_value_enqueue(eng, people):
    version = _sql(eng, "SELECT TOP 1 DataVersionId FROM adm.DataVersionEntity WHERE NewCount IS NOT NULL ORDER BY DataVersionId DESC").scalar()
    if version is not None:
        transfer_job._enqueue_quality(eng, version, people[KEY_USER])
        job = _sql(eng, "SELECT Payload FROM adm.Job WHERE JobType = :t", t=TYPE_QUALITY).scalar_one()
        assert json.loads(job)["tables"]
        _clean(eng)
    client = TestClient(create_app(), raise_server_exceptions=False)
    owner, key = auth(people[SYSTEM_OWNER]), auth(people[KEY_USER])
    c0 = _sql(eng, "SELECT TOP 1 Id, Name FROM core.Customer WHERE VersionTo IS NULL ORDER BY Code").mappings().one()
    _sql(eng, "INSERT INTO adm.DataQualityWarning (Source, CheckCode, EntityName, RecordKey, RecordLabel, RuleName, Message, Importance, State, FirstSeenAt, "
              "LastSeenAt, IgnoreReason, IgnoredBy, IgnoredAt) VALUES (N'Kural', N'PYTEST.X', N'Customer', :k, N'X', N'X', N'X', N'Normal', N'Yok sayıldı', "
              "SYSUTCDATETIME(), SYSUTCDATETIME(), N'deneme', :u, DATEADD(minute, -1, SYSUTCDATETIME()))", k=str(c0["Id"]), u=people[KEY_USER])
    try:
        assert client.put("/api/field-definitions/Customer/Name/manual", headers=owner, json={"on": True}).status_code == 200
        r = client.post("/api/manual-values", headers=key, json={"list": "master-customer", "changes": [{"id": c0["Id"], "field": "Name", "value": "Kalite adı"}]})
        assert r.status_code == 200, r.text
        assert warning(eng, "PYTEST.X")[0]["State"] == "Açık"                                               # hemen yeniden Açık
        job = json.loads(_sql(eng, "SELECT Payload FROM adm.Job WHERE JobType = :t", t=TYPE_QUALITY).scalar_one())
        assert job["tables"] == ["Customer"] and job["trigger"] == quality.TRIGGER_MANUAL
        assert client.post("/api/manual-values/remove", headers=key, json={"list": "master-customer", "items": [{"id": c0["Id"], "field": "Name"}]}).status_code == 200
    finally:
        _sql(eng, "DELETE FROM adm.FieldChange WHERE TableName = N'Customer' AND Source LIKE N'Manuel%'")
        _sql(eng, "UPDATE adm.FieldDefinition SET ManualOverrides = 0 WHERE TableName = N'Customer'")


# ------------------------------------------------------------------ API ve yetki

def test_api_list_ignore_summary_and_permissions(eng, people):
    check(eng)
    client = TestClient(create_app(), raise_server_exceptions=False)
    end, key = auth(people[END_USER]), auth(people[KEY_USER])
    q = client.post("/api/data-quality-warnings/query", headers=end, json={"fields": ["State", "RecordLabel"], "filters": [
        {"field": "Importance", "op": "in", "values": ["Yüksek"]}, {"field": "State", "op": "in", "values": ["Yeni", "Açık"]}]})
    assert q.status_code == 200, q.text
    rows = q.json()["rows"]
    assert rows and all({"EntityName", "RecordKey", "TargetList", "FixField"} <= set(r) for r in rows)
    one = rows[0]["Id"]
    assert client.post("/api/data-quality/ignore", headers=end, json={"ids": [one], "reason": "x"}).status_code == 403   # End user yok sayamaz
    assert client.post("/api/data-quality/ignore", headers=key, json={"ids": [one], "reason": "  "}).status_code == 422  # gerekçe zorunlu
    assert client.post("/api/data-quality/ignore", headers=key, json={"ids": [one], "reason": "Numune"}).json() == {"ignored": 1}
    assert _sql(eng, "SELECT TOP 1 Action FROM adm.AuditLog ORDER BY Id DESC").scalar() == quality.ignore.ACTION_IGNORE
    s = client.get("/api/data-quality/summary", headers=end).json()
    assert set(s) == {"high", "high_new"} and s["high"] == len(rows) - 1
    assert client.post("/api/data-quality/unignore", headers=key, json={"ids": [one]}).json() == {"unignored": 1}
    chain_r = client.post(f"/api/data-quality/{one}/demand-chain", headers=end)
    assert chain_r.status_code == 200 and "count" in chain_r.json()
    lst = client.post("/api/data-quality-demand-chain/query", headers=end, json={"fields": ["DemandLabel", "MaterialPath"], "filters": [
        {"field": "WarningId", "op": "in", "values": [str(one)]}]})
    assert lst.status_code == 200 and lst.json()["filtered"] == chain_r.json()["count"]
    assert client.post("/api/data-quality/999999999/demand-chain", headers=end).status_code == 404


def test_go_to_record_filters_every_target_list(eng, people):
    """Kayda git (K-174) hedef listeyi kaydın anahtarıyla süzer: her hedef listede Id süzgeci tek satır, o kaydı verir (bileşik anahtarlı Malzeme
    tedarikçisi dahil). Hedefler uyarı çıkabilen bütün tablolar (entegrasyon tabloları); RecordKey kaydın core Id'si."""
    from app.api.lists.data_quality import TARGETS
    from db.models import metadata
    client = TestClient(create_app(), raise_server_exceptions=False)
    end = auth(people[END_USER])
    from app.integration.contract import ENTITIES
    assert set(TARGETS) == {e.table for e in ENTITIES}  # her entegrasyon tablosunun Kayda git listesi var
    for table, target in TARGETS.items():
        t = metadata.tables[f"core.{table}"]
        cur = " WHERE VersionTo IS NULL" if "VersionTo" in t.c else ""
        rows = _sql(eng, f"SELECT TOP 2 Id FROM core.[{table}]{cur} ORDER BY Id").all()
        if not rows:
            continue
        value = str(rows[-1][0])
        r = client.post(f"/api/{target}/query", headers=end, json={"filters": [{"field": "Id", "op": "in", "values": [value]}]})
        assert r.status_code == 200, (target, r.text)
        body = r.json()
        assert body["filtered"] == 1 and str(body["rows"][0]["Id"]) == value, (target, body["filtered"])
    check(eng)
    w = [x for x in warning(eng, "MS.NO_LEADTIME") if x["RecordKey"] == str(deep_supplier_row(eng))][0]
    found = client.post("/api/data-quality-warnings/query", headers=end, json={"filters": [{"field": "Id", "op": "in", "values": [str(w["Id"])]}]})
    assert found.status_code == 200, found.text
    row = found.json()["rows"][0]
    assert row["TargetList"] == "master-material-supplier"
    hit = client.post("/api/master-material-supplier/query", headers=end, json={
        "fields": ["MaterialCode", "SupplierCode"], "filters": [{"field": "Id", "op": "in", "values": [row["RecordKey"]]}]}).json()
    assert hit["filtered"] == 1 and (hit["rows"][0]["MaterialCode"], hit["rows"][0]["SupplierCode"]) == (d.DEEP_MATERIAL, d.DEEP_SUPPLIER)


def test_ignored_list_shows_reason_by_default():
    """Yok sayılan sekmesi ayrı liste: Standart görünümde Gerekçe açık; ötekinde gizli. Kontrol (kural adı) ikisinde de gizli, Tespit tarihi açık."""
    from app.api.lists.data_quality import DATA_QUALITY_IGNORED, DATA_QUALITY_WARNINGS
    assert "IgnoreReason" in DATA_QUALITY_IGNORED.default_visible and "IgnoreReason" not in DATA_QUALITY_WARNINGS.default_visible
    assert DATA_QUALITY_IGNORED.default_visible == ("State", "EntityLabel", "RecordLabel", "Message", "IgnoreReason", "FirstSeenAt")
    assert DATA_QUALITY_IGNORED.fields[:6] == DATA_QUALITY_IGNORED.default_visible  # kolon sırası: Gerekçe Mesaj'ın yanında
    for defn in (DATA_QUALITY_WARNINGS, DATA_QUALITY_IGNORED):
        assert "RuleName" not in defn.default_visible and "RuleName" in defn.fields
        assert (defn.labels["RuleName"], defn.labels["FirstSeenAt"]) == ("Kontrol", "Tespit tarihi")


def test_validation_rule_tracking(eng, people):
    client = TestClient(create_app(), raise_server_exceptions=False)
    owner, key = auth(people[SYSTEM_OWNER]), auth(people[KEY_USER])
    rid = _sql(eng, "SELECT Id FROM adm.ValidationRule WHERE Code = N'MS.NO_LEADTIME'").scalar_one()
    hata = _sql(eng, "SELECT TOP 1 Id FROM adm.ValidationRule WHERE Severity = N'Hata' AND Kind = N'Hazır'").scalar_one()
    try:
        first = client.get(f"/api/validation-rules/{rid}", headers=owner)
        assert first.status_code == 200, first.text
        assert first.json()["track"] is True
        assert client.put("/api/validation-rules", headers=key, json={"changes": [{"id": rid, "track": False}], "thresholds": []}).status_code == 403
        assert client.put("/api/validation-rules", headers=owner, json={"changes": [{"id": rid, "track": False}], "thresholds": []}).status_code == 200
        assert _sql(eng, "SELECT TrackQuality FROM adm.ValidationRule WHERE Id = :i", i=rid).scalar_one() is False
        check(eng)
        assert not warning(eng, "MS.NO_LEADTIME")                                                           # takip kapandı: uyarı yok
        assert client.put("/api/validation-rules", headers=owner, json={"changes": [{"id": hata, "track": True}], "thresholds": []}).status_code == 422
        assert client.put("/api/validation-rules", headers=owner, json={"changes": [{"id": rid, "reset": True}], "thresholds": []}).status_code == 200
        assert _sql(eng, "SELECT TrackQuality FROM adm.ValidationRule WHERE Id = :i", i=rid).scalar_one() is True   # ilk hâli: Evet
        q = client.post("/api/validation-rules/query", headers=owner, json={"fields": ["RuleName", "Severity", "TrackQuality"],
                                                                             "filters": [{"field": "EntityName", "op": "equals", "value": "MaterialSupplier"}]}).json()
        tracks = {r["RuleName"]: r["TrackQuality"] for r in q["rows"]}
        assert tracks["Tedarik süresi yok"] is True and all(v is None for r in q["rows"] if r["Severity"] != "Uyarı" for v in [r["TrackQuality"]])
    finally:
        _sql(eng, "UPDATE adm.ValidationRule SET TrackQuality = 1 WHERE Id = :i", i=rid)
    assert cat.by_key()[("MaterialSupplier", "MS.NO_LEADTIME")].tracked
