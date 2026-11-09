"""Validasyon kuralları ve validasyon API'si (ekran 27 ve 02, fonksiyon 100 ve 04; K-135, K-136, K-139): yetki, toplu kayıt, kilit, düzenleme ve ilk hâl, eşik, iz, listeler."""
import io

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.api.permissions import ADMIN, END_USER, KEY_USER, SYSTEM_OWNER
from app.validation import engine

from auth_helpers import auth, ensure_user
from validation_helpers import clean, run_validations
from test_validation_chain import load, resource

pytestmark = pytest.mark.db

PREFIX = "pytest.kural."
ROLES = (SYSTEM_OWNER, ADMIN, KEY_USER, END_USER)
GROUPS = [[{"field": "Name", "operator": "İle başlar", "value": "Ad A", "compare_field": None}]]


@pytest.fixture
def env(db_engine):
    clean(db_engine)
    with db_engine.begin() as c:
        people = {r: ensure_user(c, PREFIX + r.replace(" ", "-").lower(), r, f"Ad {r}") for r in ROLES}
        c.execute(sa.text("DELETE FROM adm.AuditLog WHERE Action IN (N'Validasyon kuralı', N'Hata eşiği', N'Yeniden validasyon')"))
    client = TestClient(create_app(), raise_server_exceptions=False)
    with Session(db_engine) as s:
        engine.sync_rules(s, force=True)
    yield client, people, db_engine
    clean(db_engine)


def rule_id(eng, entity: str, code: str) -> int:
    with eng.connect() as c:
        return c.execute(sa.text("SELECT Id FROM adm.ValidationRule WHERE EntityName = :e AND Code = :c"), {"e": entity, "c": code}).scalar_one()


@pytest.mark.parametrize("role, read, write", [(SYSTEM_OWNER, 200, 200), (ADMIN, 200, 200), (KEY_USER, 200, 403), (END_USER, 403, 403)])
def test_roles(env, role, read, write):
    client, people, eng = env
    assert client.post("/api/validation-rules/query", json={"filters": [], "offset": 0, "limit": 5}, headers=auth(people[role])).status_code == read
    assert client.get("/api/validation-rules/fields/Material", headers=auth(people[role])).status_code == read
    assert client.put("/api/validation-rules", json={"changes": [], "thresholds": []}, headers=auth(people[role])).status_code == write


def test_list_has_builtin_rules_in_user_language_without_structural(env):
    client, people, eng = env
    body = {"fields": ["EntityLabel", "RuleName", "ConditionText", "Severity", "Kind", "IsActive", "Code"],
            "filters": [{"field": "EntityName", "op": "equals", "value": "BOM"}], "offset": 0, "limit": 100}
    rows = client.post("/api/validation-rules/query", json=body, headers=auth(people[ADMIN])).json()["rows"]
    names = {r["RuleName"]: r for r in rows}
    assert {"Ürün ağacında döngü", "Negatif değer", "Bileşen üretilen malzemenin kendisi"} <= set(names)
    assert names["Ürün ağacında döngü"]["ConditionText"] == "Malzeme dolaylı olarak kendi bileşeni" and names["Ürün ağacında döngü"]["Code"] == "BOM.CYCLE"
    assert names["Ürün ağacında döngü"]["Editable"] in (False, 0) and names["Bileşen üretilen malzemenin kendisi"]["Editable"] in (True, 1)
    assert all(r["Kind"] != "Yapısal" for r in rows)  # yapısal kontroller görünmez (K-139)
    assert all(r["EntityLabel"] == "Ürün ağacı" for r in rows)
    assert all("arsayılan" not in (r["RuleName"] + r["ConditionText"]) for r in rows)


def test_builtin_severity_and_active_change_is_saved_and_audited(env):
    client, people, eng = env
    rid = rule_id(eng, "Material", "MAT.SAFETY_MAX")
    r = client.put("/api/validation-rules", json={"changes": [{"id": rid, "severity": "Hata", "active": False}], "thresholds": []}, headers=auth(people[ADMIN]))
    assert r.status_code == 200 and r.json()["changed_entities"] == ["Material"]
    with eng.connect() as c:
        row = c.execute(sa.text("SELECT Severity, IsActive FROM adm.ValidationRule WHERE Id = :i"), {"i": rid}).one()
        audit = c.execute(sa.text("SELECT ObjectType, OldValue, NewValue FROM adm.AuditLog WHERE Action = N'Validasyon kuralı'")).one()
    assert tuple(row) == ("Hata", False)
    assert audit.ObjectType == "ValidationRule" and '"severity": "Uyarı"' in audit.OldValue and '"active": false' in audit.NewValue


@pytest.mark.parametrize("change, code", [
    ({"code": "STR.TYPE", "severity": "Uyarı"}, "validation_rule_locked"),
    ({"code": "MAT.SAFETY_MAX", "delete": True}, "validation_rule_builtin_delete"),
    ({"code": "ALL.OUT_OF_LIST", "message": "Başka"}, "validation"),  # düzenlenemeyen hazır kural (K-139)
])
def test_locked_and_builtin_limits(env, change, code):
    client, people, eng = env
    c = {k: v for k, v in change.items() if k != "code"}
    r = client.put("/api/validation-rules", json={"changes": [{"id": rule_id(eng, "Material", change["code"]), **c}], "thresholds": []}, headers=auth(people[ADMIN]))
    assert r.status_code == 422 and r.json()["error"]["code"] == code


def test_save_is_all_or_nothing(env):
    client, people, eng = env
    rid = rule_id(eng, "Material", "MAT.SAFETY_MAX")
    bad = {"changes": [{"id": rid, "severity": "Hata"}, {"id": rule_id(eng, "Material", "STR.TYPE"), "active": False}], "thresholds": []}
    assert client.put("/api/validation-rules", json=bad, headers=auth(people[ADMIN])).status_code == 422
    with eng.connect() as c:
        assert c.execute(sa.text("SELECT Severity FROM adm.ValidationRule WHERE Id = :i"), {"i": rid}).scalar() == "Uyarı"


def test_user_rule_create_edit_delete(env):
    client, people, eng = env
    new = {"entity": "Resource", "name": "Ad kontrolü", "message": "Ad A ile başlıyor.", "severity": "Bilgi", "groups": GROUPS}
    assert client.put("/api/validation-rules", json={"changes": [new], "thresholds": []}, headers=auth(people[ADMIN])).status_code == 200
    rid = rule_id(eng, "Resource", "KUL-1")
    detail = client.get(f"/api/validation-rules/{rid}", headers=auth(people[KEY_USER])).json()
    assert (detail["kind"], detail["condition"], detail["groups"]) == ("Kullanıcı", "Kaynak adı Ad A ile başlar", GROUPS)
    dup = client.put("/api/validation-rules", json={"changes": [new], "thresholds": []}, headers=auth(people[ADMIN]))
    assert dup.status_code == 422 and dup.json()["error"]["code"] == "validation_rule_name_taken"
    bad = client.put("/api/validation-rules", json={"changes": [{**new, "name": "x", "groups": [[{"field": "Yok", "operator": "Boş değil"}]]}], "thresholds": []},
                     headers=auth(people[ADMIN]))
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_rule_bad_condition"
    load((client, people[KEY_USER], eng), "Resource", [resource("A")])
    run_validations(eng)
    with eng.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM adm.ValidationFinding WHERE ValidationRuleId = :r"), {"r": rid}).scalar() == 1
    edit = {"id": rid, "groups": [[{"field": "IsMachine", "operator": "=", "value": "0", "compare_field": None}]]}
    assert client.put("/api/validation-rules", json={"changes": [edit], "thresholds": []}, headers=auth(people[ADMIN])).status_code == 200
    with eng.connect() as c:
        assert c.execute(sa.text("SELECT ConditionText FROM adm.ValidationRule WHERE Id = :r"), {"r": rid}).scalar() == "Makine = Hayır"
    assert client.put("/api/validation-rules", json={"changes": [{"id": rid, "delete": True}], "thresholds": []}, headers=auth(people[ADMIN])).status_code == 200
    with eng.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM adm.ValidationFinding WHERE ValidationRuleId = :r"), {"r": rid}).scalar() == 0
        assert c.execute(sa.text("SELECT COUNT(*) FROM adm.ValidationRuleCondition WHERE ValidationRuleId = :r"), {"r": rid}).scalar() == 0


def test_threshold_is_per_table_without_default(env):
    client, people, eng = env
    r = client.put("/api/validation-rules", json={"changes": [], "thresholds": [{"entity": "Resource", "value": "2,5"}]}, headers=auth(people[ADMIN]))
    assert r.status_code == 200
    assert client.get("/api/validation/Resource", headers=auth(people[KEY_USER])).json()["threshold"] == 2.5
    assert client.get("/api/validation/Material", headers=auth(people[KEY_USER])).json()["threshold"] is None  # varsayılan yok (K-135)
    bad = client.put("/api/validation-rules", json={"changes": [], "thresholds": [{"entity": "Resource", "value": "150"}]}, headers=auth(people[ADMIN]))
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_threshold_range"
    client.put("/api/validation-rules", json={"changes": [], "thresholds": [{"entity": "Resource", "value": None}]}, headers=auth(people[ADMIN]))
    assert client.get("/api/validation/Resource", headers=auth(people[KEY_USER])).json()["threshold"] is None
    with eng.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM adm.AuditLog WHERE Action = N'Hata eşiği'")).scalar() == 2


def test_rule_counts_records_rule_filter_and_download(env):
    client, people, eng = env
    user = people[KEY_USER]
    load((client, user, eng), "Resource", [resource("A"), resource("B", IsEmployee=1), resource("C", CapacityUnit=None)])
    run_validations(eng)
    rules = client.get("/api/validation/Resource", headers=auth(user)).json()["rules"]
    assert [(r["name"], r["severity"], r["rows"]) for r in rules][:2] == [("Zorunlu alan boş", "Hata", 1), ("Kaynak tipi tek değil", "Uyarı", 1)]
    type_flags = next(r for r in rules if r["name"] == "Kaynak tipi tek değil")
    only = {"filters": [{"field": "RuleIds", "op": "contains", "value": f",{type_flags['id']},"}], "offset": 0, "limit": 50}
    assert [r["Code"] for r in client.post("/api/validation-records-Resource/query", json=only, headers=auth(user)).json()["rows"]] == ["B"]
    assert client.post("/api/validation-findings-Resource/query", json={"filters": [], "offset": 0, "limit": 5}, headers=auth(user)).status_code == 404
    every = client.post("/api/validation-records-Resource/query", json={"filters": [], "offset": 0, "limit": 50}, headers=auth(user)).json()["rows"]
    assert sorted((r["Code"], r["Severity"]) for r in every) == [("A", None), ("B", "Uyarı"), ("C", "Hata")]  # Tüm satırlar (K-143)
    flagged = {"filters": [{"field": "HasFindings", "op": "in", "values": [True]}], "offset": 0, "limit": 50}
    recs = client.post("/api/validation-records-Resource/query", json=flagged, headers=auth(user)).json()["rows"]
    assert sorted((r["Code"], r["Severity"]) for r in recs) == [("B", "Uyarı"), ("C", "Hata")]  # Bulgulu satırlar
    changed = {"filters": [{"field": "HasEffects", "op": "in", "values": [True]}], "offset": 0, "limit": 50}
    assert client.post("/api/validation-records-Resource/query", json=changed, headers=auth(user)).json()["rows"] == []  # kural yok
    assert next(r for r in recs if r["Code"] == "C")["Problems"] == "Kapasite birimi: Zorunlu alan boş."
    columns = [c["field"] for c in client.get("/api/validation-records-Resource/columns", headers=auth(user)).json()["columns"]]
    assert columns[:3] == ["Problems", "Severity", "RowNo"]  # ilk kolonlar Sorun ve Sınıf (K-139)
    body = {"fields": columns, "widths": {}, "sort": [], "filters": [], "group_by": [], "aggregates": {}, "rules": [], "scope": {"rows": "all", "columns": "all"}}
    r = client.post("/api/validation-records-Resource/export", json=body, headers=auth(user))
    assert r.status_code == 200, r.text
    ws = load_workbook(io.BytesIO(r.content), read_only=True).worksheets[0]
    header = [c for c in next(ws.iter_rows(values_only=True))]
    assert header[:2] == ["Sorun", "Sınıf"] and "Kaynak kodu" in header
    assert client.post("/api/validation-records-Resource/query", json={"filters": [], "offset": 0, "limit": 5}, headers=auth(people[END_USER])).status_code == 403


def test_revalidate_is_audited(env):
    client, people, eng = env
    load((client, people[KEY_USER], eng), "Resource", [resource("A")])
    run_validations(eng)
    assert client.post("/api/validation/Resource/revalidate", headers=auth(people[END_USER])).status_code == 403
    assert client.post("/api/validation/Resource/revalidate", headers=auth(people[KEY_USER])).status_code == 202
    jobs = client.get("/api/jobs", headers=auth(people[KEY_USER])).json()["jobs"]
    job = next(j for j in jobs if j["job_type"] == "Validasyon" and j["validation"]["trigger"] == "Yeniden valide et")
    assert job["validation"]["entity"] == "Resource" and job["channel"] == "Veri işleme"
    with eng.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM adm.AuditLog WHERE Action = N'Yeniden validasyon'")).scalar() == 1


def test_builtin_rule_edit_keeps_catalog_until_reset(env):
    """Düzenlenebilir hazır kural (K-139): ilk düzenlemede katalog koşulu veritabanına kopyalanır; eşitleme ezmez; İlk hâline döndür."""
    client, people, eng = env
    rid = rule_id(eng, "Material", "MAT.SAFETY_MAX")
    detail = client.get(f"/api/validation-rules/{rid}", headers=auth(people[ADMIN])).json()
    assert detail["editable"] is True and detail["customized"] is False and detail["name"] == "Güvenlik stoğu maksimum stoktan büyük"
    assert detail["groups"] == [[{"field": "SafetyStock", "operator": ">", "value": None, "compare_field": "MaxStock"}]]
    groups = [[*detail["groups"][0], {"field": "MaxStock", "operator": ">", "value": "0", "compare_field": None}]]
    r = client.put("/api/validation-rules", json={"changes": [{"id": rid, "name": "Güvenlik stoğu sınırı aşıyor", "groups": groups}], "thresholds": []},
                   headers=auth(people[ADMIN]))
    assert r.status_code == 200, r.text
    with Session(eng) as s:
        engine.sync_rules(s, force=True)  # sürüm yükseltmesi gibi: düzenlenmiş kural ezilmez
    detail = client.get(f"/api/validation-rules/{rid}", headers=auth(people[ADMIN])).json()
    assert (detail["name"], detail["customized"], len(detail["groups"][0])) == ("Güvenlik stoğu sınırı aşıyor", True, 2)
    assert detail["condition"] == "Güvenlik stoğu > Maksimum stok ve Maksimum stok > 0"
    assert client.put("/api/validation-rules", json={"changes": [{"id": rid, "reset": True}], "thresholds": []}, headers=auth(people[ADMIN])).status_code == 200
    detail = client.get(f"/api/validation-rules/{rid}", headers=auth(people[ADMIN])).json()
    assert (detail["name"], detail["customized"], detail["severity"], detail["active"]) == ("Güvenlik stoğu maksimum stoktan büyük", False, "Uyarı", True)
    with eng.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM adm.ValidationRuleCondition WHERE ValidationRuleId = :r"), {"r": rid}).scalar() == 0
        assert c.execute(sa.text("SELECT COUNT(*) FROM adm.AuditLog WHERE Action = N'Validasyon kuralı'")).scalar() == 2


def test_severity_only_change_does_not_customize(env):
    client, people, eng = env
    rid = rule_id(eng, "Material", "MAT.SAFETY_MAX")
    client.put("/api/validation-rules", json={"changes": [{"id": rid, "severity": "Bilgi"}], "thresholds": []}, headers=auth(people[ADMIN]))
    assert client.get(f"/api/validation-rules/{rid}", headers=auth(people[ADMIN])).json()["customized"] is False


def test_reset_only_for_builtin(env):
    client, people, eng = env
    new = {"entity": "Resource", "name": "Ad kontrolü", "message": "Ad A ile başlıyor.", "severity": "Bilgi", "groups": GROUPS}
    client.put("/api/validation-rules", json={"changes": [new], "thresholds": []}, headers=auth(people[ADMIN]))
    r = client.put("/api/validation-rules", json={"changes": [{"id": rule_id(eng, "Resource", "KUL-1"), "reset": True}], "thresholds": []}, headers=auth(people[ADMIN]))
    assert r.status_code == 422
