"""Veri kuralları (fonksiyon 16, 18, 19; K-140…K-142): işlenmiş katman, sonuç türleri, sıra, boş sonuç ve sıfıra bölme, Çalışmadı,
validasyonun işlenmiş değeri görmesi, hücre izi, kayıt denetimi, yetki, toplu uygulama."""
from datetime import date
from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.permissions import ADMIN, END_USER, KEY_USER
from app.validation import data_rule
from app.validation.data_rule import Result, RuleError
from app.validation.sqlkit import label

from auth_helpers import auth, ensure_user
from test_validation_chain import findings, material, resource, xlsx
from validation_helpers import clean, run_validations

PREFIX = "pytest.veri.kurali."


# ------------------------------------------------------------------ birim (veritabanı gerekmez)

def test_targets_exclude_key_fields():
    targets = data_rule.targets("Material")
    assert targets["Code"] and targets["LocationCode"] and targets["MinLot"] is None and targets["IsActive"] is None


def test_constant_is_normalized_by_target_type():
    assert data_rule.validate("Location", "IsFactory", Result("Değer", "Evet"), "Yalnız boşsa").value == "1"
    assert data_rule.validate("Material", "MinLot", Result("Değer", "1.234,5"), "Her zaman").value == "1234.5"
    assert data_rule.validate("PurchaseOrderLine", "ConfirmedDate", Result("Değer", "05.11.2026"), "Her zaman").value == "2026-11-05"
    assert data_rule.validate("PurchaseOrderLine", "ConfirmedDate", Result("Formül", source_field="RequestedDate", operator="+", operand_value="3"),
                              "Yalnız boşsa").operand_value == "3"


@pytest.mark.parametrize("entity,target,result,mode,problem", [
    ("Material", "Code", Result("Değer", "X"), "Her zaman", "Anahtar alan"),
    ("Material", "Yok", Result("Değer", "1"), "Her zaman", "Hedef alan yok"),
    ("Material", "MinLot", Result("Değer", "abc"), "Her zaman", "tipine uymuyor"),
    ("Material", "DefaultSupplyType", Result("Değer", "Başka"), "Her zaman", "listede yok"),
    ("Material", "MinLot", Result("Alan", source_field="Name"), "Her zaman", "tipi hedefe uymuyor"),
    ("Material", "Name", Result("Formül", source_field="Name", operator="+", operand_value="1"), "Her zaman", "yalnız sayı ve tarih"),
    ("PurchaseOrderLine", "ConfirmedDate", Result("Formül", source_field="RequestedDate", operator="×", operand_value="2"), "Her zaman", "Operatör"),
    ("PurchaseOrderLine", "ConfirmedDate", Result("Formül", source_field="RequestedDate", operator="+", operand_value="1,5"), "Her zaman", "tam sayı"),
    ("Material", "MinLot", Result("Formül", source_field="MaxLot", operator="+"), "Her zaman", "bir değer ya da bir alan"),
    ("Material", "MinLot", Result("Boşalt"), "Yalnız boşsa", "Her zaman"),
    ("Material", "MinLot", Result("Değer", "1"), "Bazen", "Seçenek yok"),
])
def test_invalid_rules_are_rejected(entity, target, result, mode, problem):
    with pytest.raises(RuleError, match=problem):
        data_rule.validate(entity, target, result, mode)


def test_result_text_is_readable():
    assert data_rule.text("Location", "IsFactory", Result("Değer", "1")) == f"{label('Location', 'IsFactory')} = Evet"
    assert data_rule.text("Material", "MaxLot", Result("Formül", source_field="MinLot", operator="×", operand_value="10")) == \
        f"{label('Material', 'MaxLot')} = {label('Material', 'MinLot')} × 10"
    assert data_rule.text("PurchaseOrderLine", "ConfirmedDate", Result("Formül", source_field="RequestedDate", operator="+", operand_value="3")).endswith("+ 3 gün")
    assert data_rule.text("Material", "MinLot", Result("Boşalt")) == f"{label('Material', 'MinLot')} boşaltılır"
    assert data_rule.text("Material", "MinLot", Result("Değer", "1234.5")).endswith("= 1.234,5")


# ------------------------------------------------------------------ veritabanı

@pytest.fixture
def env(db_engine):
    clean(db_engine)
    with db_engine.begin() as c:
        people = {role: ensure_user(c, PREFIX + role.lower().replace(" ", ""), role, role) for role in (ADMIN, KEY_USER, END_USER)}
        c.execute(sa.text("DELETE FROM adm.AuditLog WHERE Action IN (N'Veri kuralı', N'Kural sırası', N'Kuralları yeniden uygula')"))
    yield TestClient(create_app(), raise_server_exceptions=False), people, db_engine
    clean(db_engine)


def upload(env, entity: str, rows) -> None:
    client, people, eng = env
    user = people[ADMIN]
    r = client.post(f"/api/imports/{entity}?mode=Tam", content=xlsx(entity, rows), headers={**auth(user), "X-File-Name": f"{entity}.xlsx"})
    assert r.status_code == 200, r.text
    assert client.post(f"/api/imports/{r.json()['batch_id']}/continue", headers=auth(user)).status_code == 200
    run_validations(eng)


def save(env, changes, orders=(), role=ADMIN, status=200) -> dict:
    client, people, _ = env
    r = client.put("/api/data-rules", json={"changes": list(changes), "orders": list(orders)}, headers=auth(people[role]))
    assert r.status_code == status, r.text
    return r.json()


def apply(env, entity: str | None) -> list[int]:
    client, people, eng = env
    r = client.post("/api/data-rules/apply", json={"entity": entity}, headers=auth(people[ADMIN]))
    assert r.status_code == 202, r.text
    run_validations(eng)
    return r.json()["job_ids"]


def rule(name: str, target: str, result: dict, mode: str = "Her zaman", groups=None, entity: str = "Material", active: bool = True) -> dict:
    return {"entity": entity, "name": name, "target": target, "result": result, "mode": mode, "groups": groups or [], "active": active}


def rows(eng, schema: str, entity: str, fields: str, key: str = "Code") -> dict:
    where = " WHERE IsCurrent = 1" if schema == "stg" else ""
    with eng.connect() as c:
        return {r[0]: tuple(r[1:]) for r in c.execute(sa.text(f"SELECT [{key}], {fields} FROM {schema}.[{entity}]{where}")).all()}


def ids(eng, entity: str = "Material") -> dict:
    with eng.connect() as c:
        return dict(c.execute(sa.text("SELECT Name, Id FROM adm.DataRule WHERE EntityName = :e"), {"e": entity}).all())


def status(eng) -> dict:
    with eng.connect() as c:
        return {r[0]: (r[1], r[2]) for r in c.execute(sa.text("SELECT Name, LastRunStatus, LastRunMessage FROM adm.DataRule")).all()}


db = pytest.mark.db  # veritabanı testleri (K-103)


@db
def test_rules_run_in_order_on_processed_layer_raw_untouched(env):
    _, _, eng = env
    upload(env, "Material", [material("A", MinLot=5), material("B")])
    save(env, [rule("Minimum lot", "MinLot", {"kind": "Değer", "value": "1"}, "Yalnız boşsa"),
               rule("Maksimum lot", "MaxLot", {"kind": "Formül", "source_field": "MinLot", "operator": "×", "operand_value": "10"})])
    apply(env, "Material")
    assert rows(eng, "prc", "Material", "MinLot, MaxLot") == {"A": (Decimal("5"), Decimal("50")), "B": (Decimal("1"), Decimal("10"))}  # X → Y
    assert rows(eng, "stg", "Material", "MinLot, MaxLot") == {"A": (Decimal("5"), None), "B": (None, None)}  # ham katman değişmez
    with eng.connect() as c:
        effects = sorted(tuple(r) for r in c.execute(sa.text(
            "SELECT p.Code, e.FieldName, r.Name, e.RawValue FROM adm.DataRuleEffect e JOIN adm.DataRule r ON r.Id = e.DataRuleId "
            "JOIN prc.Material p ON p.StagingRowId = e.StagingRowId")).all())
    assert effects == [("A", "MaxLot", "Maksimum lot", None), ("B", "MaxLot", "Maksimum lot", None), ("B", "MinLot", "Minimum lot", None)]
    assert set(status(eng).values()) == {("Çalıştı", None)}


@db
def test_last_rule_wins_and_order_changes_it(env):
    _, _, eng = env
    upload(env, "Material", [material("A")])
    save(env, [rule("Bir", "SafetyStock", {"kind": "Değer", "value": "1"}), rule("İki", "SafetyStock", {"kind": "Değer", "value": "2"})])
    apply(env, "Material")
    assert rows(eng, "prc", "Material", "SafetyStock") == {"A": (Decimal("2"),)}
    r = ids(eng)
    save(env, [], [{"entity": "Material", "ids": [r["İki"], r["Bir"]]}])
    apply(env, "Material")
    assert rows(eng, "prc", "Material", "SafetyStock") == {"A": (Decimal("1"),)}
    save(env, [], [{"entity": "Material", "ids": [r["İki"]]}], status=409)  # eksik liste: sıra eskidi


@db
def test_no_accumulation_and_disabled_or_deleted_rule_effect_disappears(env):
    _, _, eng = env
    upload(env, "Material", [material("A", MinLot=5)])
    save(env, [rule("Artır", "MinLot", {"kind": "Formül", "source_field": "MinLot", "operator": "+", "operand_value": "1"})])
    apply(env, "Material")
    apply(env, "Material")
    assert rows(eng, "prc", "Material", "MinLot") == {"A": (Decimal("6"),)}  # iki çalıştırma aynı sonuç
    save(env, [{"id": ids(eng)["Artır"], "active": False}])
    apply(env, "Material")
    assert rows(eng, "prc", "Material", "MinLot") == {"A": (Decimal("5"),)}
    save(env, [{"id": ids(eng)["Artır"], "active": True}])
    apply(env, "Material")
    save(env, [{"id": ids(eng)["Artır"], "delete": True}])
    apply(env, "Material")
    assert rows(eng, "prc", "Material", "MinLot") == {"A": (Decimal("5"),)} and ids(eng) == {}


@db
def test_empty_result_and_division_by_zero_leave_the_cell(env):
    _, _, eng = env
    upload(env, "Material", [material("A", MinLot=10, LotMultiple=0, MaxLot=7), material("B", MinLot=10, LotMultiple=2, MaxLot=7),
                             material("C", LotMultiple=2, MaxLot=7)])
    save(env, [rule("Böl", "MaxLot", {"kind": "Formül", "source_field": "MinLot", "operator": "÷", "operand_field": "LotMultiple"}),
               rule("Kopya", "SafetyStock", {"kind": "Alan", "source_field": "MinLot"})])
    apply(env, "Material")
    assert rows(eng, "prc", "Material", "MaxLot, SafetyStock") == {"A": (Decimal("7"), Decimal("10")), "B": (Decimal("5"), Decimal("10")),
                                                                   "C": (Decimal("7"), None)}
    assert status(eng)["Böl"] == ("Çalıştı", None)  # bölen sıfır satırda boş sonuç, kural öteki satırlarda çalışır (K-141)


@db
def test_rule_that_cannot_run_is_skipped_others_and_validation_continue(env):
    client, people, eng = env
    upload(env, "Material", [material("A")])
    save(env, [rule("Bozuk", "MinLot", {"kind": "Değer", "value": "1"}), rule("Sağlam", "MaxLot", {"kind": "Değer", "value": "9"})])
    with eng.begin() as c:  # alan sözleşmeden kalkmış gibi: kuralın tamamını etkileyen hata
        c.execute(sa.text("UPDATE adm.DataRule SET TargetField = N'EskiAlan' WHERE Name = N'Bozuk'"))
    apply(env, "Material")
    st = status(eng)
    assert st["Bozuk"][0] == "Çalışmadı" and "EskiAlan" in st["Bozuk"][1] and st["Sağlam"] == ("Çalıştı", None)
    assert rows(eng, "prc", "Material", "MinLot, MaxLot") == {"A": (None, Decimal("9"))}
    assert client.get("/api/validation/Material", headers=auth(people[ADMIN])).json()["state"] == "Bitti"
    listed = client.post("/api/data-rules/query", json={"filters": [], "offset": 0, "limit": 10, "fields": ["RuleName", "RunState"]},
                         headers=auth(people[KEY_USER])).json()["rows"]
    assert {r["RuleName"]: r["RunState"] for r in listed} == {"Bozuk": "Çalışmadı", "Sağlam": "Çalıştı"}
    assert next(r for r in listed if r["RuleName"] == "Bozuk")["LastRunMessage"]


@db
def test_date_formula_only_empty_and_clear(env):
    _, _, eng = env
    po = lambda no, **x: {"LocationCode": "ORM-01", "PurchaseOrderNo": no, "LineNo": 1, "MaterialCode": "M1", "OpenQuantity": 5,  # noqa: E731
                          "RequestedDate": date(2026, 11, 10), "IsActive": 1, **x}
    upload(env, "PurchaseOrderLine", [po("P1"), po("P2", ConfirmedDate=date(2026, 11, 20), OrderedQuantity=8)])
    save(env, [rule("Teyit", "ConfirmedDate", {"kind": "Formül", "source_field": "RequestedDate", "operator": "+", "operand_value": "3"}, "Yalnız boşsa",
                    entity="PurchaseOrderLine"),
               rule("Boşalt", "OrderedQuantity", {"kind": "Boşalt"}, entity="PurchaseOrderLine")])
    apply(env, "PurchaseOrderLine")
    got = rows(eng, "prc", "PurchaseOrderLine", "ConfirmedDate, OrderedQuantity", key="PurchaseOrderNo")
    assert got == {"P1": (date(2026, 11, 13), None), "P2": (date(2026, 11, 20), None)}


@db
def test_validation_sees_processed_value_and_records_carry_the_trace(env):
    client, people, eng = env
    upload(env, "Resource", [resource("A"), resource("B", IsMachine=None)])
    assert ("Resource", "RES.TYPE_FLAGS", "ORM-01 · B", "Uyarı", "Kaynağın tek bir tipi olmalı.") in findings(eng, "Resource")
    save(env, [rule("Makine", "IsMachine", {"kind": "Değer", "value": "Evet"}, "Yalnız boşsa", entity="Resource")])
    apply(env, "Resource")
    assert not [f for f in findings(eng, "Resource") if f[1] == "RES.TYPE_FLAGS"]  # kural sonrası bulgu kalkar


@db
def test_records_list_returns_rule_effects(env):
    client, people, eng = env
    upload(env, "Resource", [resource("A", CapacityUnit=None, IsMachine=None)])
    save(env, [rule("Makine", "IsMachine", {"kind": "Değer", "value": "1"}, entity="Resource")])
    apply(env, "Resource")
    recs = client.post("/api/validation-records-Resource/query", json={"filters": [], "offset": 0, "limit": 5, "fields": ["Code"]},
                       headers=auth(people[KEY_USER])).json()["rows"]
    assert recs and recs[0]["RuleEffects"].split("\x1f") == ["IsMachine", "1", "Makine", ""]


@db
def test_save_rejects_bad_rules_and_writes_the_trail(env):
    _, _, eng = env
    bad = {"data_rule_bad_target": rule("Anahtar", "Code", {"kind": "Değer", "value": "X"}),
           "data_rule_bad_result": rule("Tip", "MinLot", {"kind": "Değer", "value": "abc"}),
           "data_rule_bad_condition": rule("Koşul", "MinLot", {"kind": "Değer", "value": "1"}, groups=[[{"field": "Yok", "operator": "Boş"}]])}
    for code, change in bad.items():
        assert save(env, [change], status=422)["error"]["code"] == code
    save(env, [rule("Bir", "MinLot", {"kind": "Değer", "value": "1"})])
    assert save(env, [rule("Bir", "MaxLot", {"kind": "Değer", "value": "1"})], status=422)["error"]["code"] == "data_rule_name_taken"
    save(env, [{"id": ids(eng)["Bir"], "result": {"kind": "Değer", "value": "2"}}])
    with eng.connect() as c:
        trail = c.execute(sa.text("SELECT COUNT(*) FROM adm.AuditLog WHERE Action = N'Veri kuralı'")).scalar()
        text = c.execute(sa.text("SELECT ResultText FROM adm.DataRule")).scalar()
    assert trail == 2 and text.endswith("= 2")


@db
@pytest.mark.parametrize("role,read,write", [(ADMIN, 200, 200), (KEY_USER, 200, 403), (END_USER, 403, 403)])
def test_roles(env, role, read, write):
    client, people, _ = env
    assert client.post("/api/data-rules/query", json={"filters": [], "offset": 0, "limit": 5}, headers=auth(people[role])).status_code == read
    assert client.get("/api/data-rules/fields/Material", headers=auth(people[role])).status_code == read
    assert client.put("/api/data-rules", json={"changes": [], "orders": []}, headers=auth(people[role])).status_code == write
    expected = 409 if write == 200 else 403  # kural yok
    assert client.post("/api/data-rules/apply", json={}, headers=auth(people[role])).status_code == expected


@db
def test_fields_mark_key_fields_as_not_target(env):
    client, people, _ = env
    fields = {f["name"]: f for f in client.get("/api/data-rules/fields/Material", headers=auth(people[ADMIN])).json()}
    assert fields["Code"]["target"] is False and fields["Code"]["reason"] and fields["MinLot"]["target"] is True


@db
def test_apply_all_tables_runs_cross_validation_last(env):
    client, people, eng = env
    upload(env, "Material", [material("A")])
    upload(env, "Resource", [resource("R")])
    save(env, [rule("M", "MinLot", {"kind": "Değer", "value": "1"}), rule("R", "IsCritical", {"kind": "Değer", "value": "1"}, entity="Resource")])
    jobs = apply(env, None)
    assert len(jobs) == 2
    with eng.connect() as c:
        runs = c.execute(sa.text("SELECT Scope, TriggerType, GroupId, State FROM adm.ValidationRun WHERE GroupId = :g ORDER BY Id"), {"g": jobs[0]}).all()
    assert [(r.Scope, r.State) for r in runs] == [("Tablo içi", "Bitti"), ("Tablo içi", "Bitti"), ("Tablolar arası", "Bitti")]
    assert {r.TriggerType for r in runs[:2]} == {"Kural değişikliği"}


@db
def test_labels_follow_the_dictionary_in_editors_and_rule_texts(env):
    """K-143: editörde yalnız etiketli ek alan, etiket adıyla; kural metni etiket değişince güncel etiketle yeniden yazılır."""
    client, people, eng = env
    with eng.begin() as c:
        owner = ensure_user(c, PREFIX + "owner", "System owner", "Owner")
        c.execute(sa.text("UPDATE adm.FieldDefinition SET Label = NULL WHERE TableName = N'Material' AND FieldName LIKE N'Additional%'"))
    try:
        names = {f["name"] for f in client.get("/api/data-rules/fields/Material", headers=auth(people[ADMIN])).json()}
        assert "AdditionalNumber1" not in names and "MinLot" in names  # etiketsiz ek alan listelenmez
        assert "AdditionalNumber1" not in {f["name"] for f in client.get("/api/validation-rules/fields/Material", headers=auth(people[ADMIN])).json()}
        r = client.put("/api/field-definitions/Material/AdditionalNumber1/label", json={"label": "Test1"}, headers=auth(owner))
        assert r.status_code == 200, r.text
        fields = {f["name"]: f for f in client.get("/api/data-rules/fields/Material", headers=auth(people[ADMIN])).json()}
        assert fields["AdditionalNumber1"]["label"] == "Test1"
        save(env, [rule("Palet", "AdditionalNumber1", {"kind": "Formül", "source_field": "QtyPerPallet", "operator": "÷", "operand_field": "QtyPerBox"})])
        with eng.connect() as c:
            assert c.execute(sa.text("SELECT ResultText FROM adm.DataRule WHERE Name = N'Palet'")).scalar().startswith("Test1 = ")
        assert client.put("/api/field-definitions/Material/AdditionalNumber1/label", json={"label": "Kutu sayısı"}, headers=auth(owner)).status_code == 200
        with eng.connect() as c:
            assert c.execute(sa.text("SELECT ResultText FROM adm.DataRule WHERE Name = N'Palet'")).scalar().startswith("Kutu sayısı = ")
    finally:
        with eng.begin() as c:
            c.execute(sa.text("UPDATE adm.FieldDefinition SET Label = NULL WHERE TableName = N'Material' AND FieldName = N'AdditionalNumber1'"))


@db
def test_sequence_is_one_based_without_gaps(env):
    """K-143: yeni kural, silme ve demo kuralı yüklemesinden sonra sıra 1, 2, 3…; liste de satır numarasını gösterir."""
    client, people, eng = env
    save(env, [rule("A", "MinLot", {"kind": "Değer", "value": "1"}), rule("B", "MaxLot", {"kind": "Değer", "value": "1"}),
               rule("C", "SafetyStock", {"kind": "Değer", "value": "1"})])
    save(env, [{"id": ids(eng)["B"], "delete": True}])
    with eng.begin() as c:  # eski verideki boşluk: liste yine 1'den gösterir
        c.execute(sa.text("UPDATE adm.DataRule SET Seq = Seq + 10 WHERE Name = N'C'"))
    listed = client.post("/api/data-rules/query", json={"filters": [], "offset": 0, "limit": 10, "fields": ["Seq", "RuleName"]}, headers=auth(people[ADMIN])).json()["rows"]
    assert [(r["Seq"], r["RuleName"]) for r in listed] == [(1, "A"), (2, "C")]
    save(env, [rule("D", "MaxLot", {"kind": "Değer", "value": "2"})])
    with eng.connect() as c:
        assert c.execute(sa.text("SELECT Name, Seq FROM adm.DataRule ORDER BY Seq")).all() == [("A", 1), ("C", 2), ("D", 3)]


@db
def test_zero_number_filter_finds_the_row(env):
    """E14: Kayıtlar · Tüm satırlar'da sayı filtresi = 0 sıfırı yakalar."""
    client, people, _ = env
    upload(env, "Material", [material("Z", QtyPerBox=0, QtyPerPallet=40), material("N", QtyPerBox=4, QtyPerPallet=40)])
    body = {"filters": [{"field": "QtyPerBox", "op": "eq", "value": 0}], "offset": 0, "limit": 10, "fields": ["Code", "QtyPerBox"]}
    rows = client.post("/api/validation-data-Material/query", json=body, headers=auth(people[KEY_USER])).json()["rows"]
    assert [r["Code"] for r in rows] == ["Z"]


@db
def test_run_state_is_always_filled(env):
    """K-145: Durum her zaman dolu: Uygulanmadı, Çalıştı, Pasif."""
    client, people, eng = env
    upload(env, "Material", [material("A")])
    save(env, [rule("Bir", "MinLot", {"kind": "Değer", "value": "1"}), rule("İki", "MaxLot", {"kind": "Değer", "value": "2"})])
    state = lambda: {r["RuleName"]: r["RunState"] for r in client.post(  # noqa: E731
        "/api/data-rules/query", json={"filters": [], "offset": 0, "limit": 10, "fields": ["RuleName", "RunState"]}, headers=auth(people[ADMIN])).json()["rows"]}
    assert state() == {"Bir": "Uygulanmadı", "İki": "Uygulanmadı"}
    apply(env, "Material")
    save(env, [{"id": ids(eng)["İki"], "active": False}])
    assert state() == {"Bir": "Çalıştı", "İki": "Pasif"}


@db
def test_inactive_rows_skip_validation(env):
    """K-145: IsActive = Hayır olan satır hiçbir validasyon kuralına girmez; IsActive boşsa zorunlu alan bulgusu yazılır."""
    _, _, eng = env
    upload(env, "Resource", [resource("A"), resource("P", IsActive=0, CapacityUnit=None, IsMachine=None), resource("N", IsActive=None)])
    found = {(f[1], f[2]) for f in findings(eng, "Resource")}
    assert not any(key.endswith(" · P") for _, key in found)  # pasif satır: zorunlu alan ve tip bulgusu yok
    assert ("STR.REQUIRED", "ORM-01 · N") in found  # IsActive boş: zorunlu alan
    save(env, [rule("Pasif yap", "IsActive", {"kind": "Değer", "value": "0"}, groups=[[{"field": "Code", "operator": "=", "value": "N"}]], entity="Resource")])
    apply(env, "Resource")
    assert not any(key.endswith(" · N") for _, key in {(f[1], f[2]) for f in findings(eng, "Resource")})  # kural kapsam dışı bıraktı
