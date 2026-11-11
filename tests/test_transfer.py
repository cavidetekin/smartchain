"""Tam aktarım (K-149, K-153): yeni, değişmeyen, değişen, kapatılan; Hatalı satırın önceki hâli; zorunlu ve isteğe bağlı ilişki; pasif ebeveyn;
birim dönüşümünün çoğaltılması; birim oluşumu; korunan kolonlar; değerin kaynağı; tablo içi bağ; veri yok ve eşik.

Satırlar doğrudan ham katmana yazılır, işlenmiş katman kurulur. Aktarım commit edilmez: aynı oturumda denetlenir ve geri alınır (test
veritabanının sentetik core verisi değişmez)."""
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.transfer import engine as transfer, mapping
from app.integration.contract import ENTITIES
from db.models import metadata

from test_validation_references import put
from validation_helpers import clean

pytestmark = pytest.mark.db

L1, L2 = "TL-1", "TL-2"


def mat(code, loc=L1, **extra):
    return {"LocationCode": loc, "Code": code, "Name": f"Ad {code}", "BaseUom": "ADET", "IsActive": 1, "DefaultSupplyType": "Satın alma", **extra}


SO = {"RequestedDate": "2026-12-01", "OrderedQuantity": 5, "DeliveredQuantity": 0, "IsOnHold": 0, "IsQuote": 0, "IsCustomTracked": 0}
WO = {"OpenQuantity": 1, "OrderedQuantity": 1, "CompletedQuantity": 0, "StartDate": "2026-12-01", "DueDate": "2026-12-10", "IsProduction": 1,
      "IsSubcontract": 0, "IsRework": 0, "IsReleased": 1, "IsOnHold": 0, "IsCustomTracked": 0}
DATA = {
    "Location": [{"Code": L1, "Name": "Test 1", "IsFactory": 1, "IsActive": 1}, {"Code": L2, "Name": "Test 2", "IsDepot": 1, "IsActive": 1}],
    "Material": [mat("T-OK", MaterialGroup="G1"), mat("T-OK", L2), mat("T-ERR"), mat("T-PAS"), mat("T-OFF", IsActive=0), mat("T-KUTU", BaseUom="TKUTU")],
    "UomConversion": [{"MaterialCode": "T-OK", "FromUom": "KOLI", "ToUom": "ADET", "Factor": 12},
                      {"MaterialCode": "T-NOPE", "FromUom": "KG", "ToUom": "ADET", "Factor": 2},
                      {"MaterialCode": None, "FromUom": "PAKET", "PakName": None, "ToUom": "ADET", "Factor": 6} if False else
                      {"MaterialCode": None, "FromUom": "PAKET", "FromUomName": "Paket", "ToUom": "ADET", "Factor": 6}],
    "Customer": [{"Code": "TC-1", "Name": "Müşteri", "IsActive": 1}],
    "Resource": [{"LocationCode": L1, "Code": "TR-1", "Name": "Tezgâh", "IsMachine": 1, "CapacityUnit": "SAAT", "IsActive": 1}],
    "SalesOrderLine": [
        {"LocationCode": L1, "OrderNo": "TS-1", "LineNo": 1, "LineItemNo": 0, "CustomerCode": "TC-1", "MaterialCode": "T-OK", "OpenQuantity": 5, "IsActive": 1,
         "ProjectCode": "TP-NOPE", **SO},
        {"LocationCode": L1, "OrderNo": "TS-2", "LineNo": 1, "LineItemNo": 0, "CustomerCode": "TC-1", "MaterialCode": "T-NOPE", "OpenQuantity": 5, "IsActive": 1, **SO},
        {"LocationCode": L1, "OrderNo": "TS-3", "LineNo": 1, "LineItemNo": 0, "CustomerCode": "TC-1", "MaterialCode": "T-PAS", "OpenQuantity": 5, "IsActive": 1, **SO},
        {"LocationCode": L1, "OrderNo": "TS-4", "LineNo": 1, "LineItemNo": 0, "CustomerCode": "TC-1", "MaterialCode": "T-OK", "OpenQuantity": 5, "IsActive": 1,
         **{**SO, "RequestedDate": None}}],  # validasyon çalışmadı: savunma
    "WorkOrder": [{"LocationCode": L1, "WorkOrderNo": "TW-1", "MaterialCode": "T-OK", **WO},
                  {"LocationCode": L1, "WorkOrderNo": "TW-2", "MaterialCode": "T-OK", "ParentWorkOrderNo": "TW-1", **WO}],
}


@pytest.fixture(scope="module")
def staged(db_engine):
    clean(db_engine)
    put(db_engine, DATA)
    yield db_engine
    clean(db_engine)


@pytest.fixture
def s(staged):
    with Session(staged) as session:
        yield session
        session.rollback()


def core_rows(s, entity: str, where: str = "", current: bool = True, **params) -> list[dict]:
    t = metadata.tables[f"core.{entity}"]
    q = f"SELECT * FROM core.[{entity}]" + (" WHERE VersionTo IS NULL" if current and "VersionTo" in t.c else " WHERE 1 = 1") + (f" AND {where}" if where else "")
    return [dict(r) for r in s.execute(sa.text(q), params).mappings()]


def loc_id(s, code):
    return s.execute(sa.text("SELECT Id FROM core.Location WHERE Code = :c"), {"c": code}).scalar()


def set_prc(s, entity, where, **values):
    sets = ", ".join(f"[{k}] = :{k}" for k in values)
    s.execute(sa.text(f"UPDATE prc.[{entity}] SET {sets} WHERE {where}"), values)


def by_entity(result) -> dict:
    return {t["entity"]: t for t in result["tables"]}


def test_core_required_columns_are_errors_in_staging():
    """Savunmanın yakaladığı durum validasyonda da Hata olsun: core'un her zorunlu kolonu staging'de ön kontrolde zorunlu (ZOR. E) ya da
    "hata (kurallardan sonra)" (STR.REQUIRED); ilişki kolonunda alan zorunlu ya da ilişki Zorunlu (doluysa) değil, Zorunlu (K-153)."""
    from app.integration.contract import AFTER_RULES, stg_columns
    for e in ENTITIES:
        m = mapping.table_map(e.table)
        spec = {c.name: c.info for c in stg_columns(e.table)}
        sources = {n: n for n in m.plain} | {r.column: r.ref.fields[0] for r in m.refs} | ({"LocationId": "LocationCode"} if m.location else {})
        for column, field in sources.items():
            if m.core.c[column].nullable:
                continue
            info = spec[field]
            assert info.get("required") or info.get("missing") == AFTER_RULES, (e.table, column, field, info.get("missing"))


def test_mapping_covers_every_core_column():
    for e in ENTITIES:
        assert mapping.unmapped(e.table) == [], e.table


def test_first_transfer_writes_new_rows_with_resolved_ids(s):
    r = transfer.run_transfer(s, None)
    v, t = r["data_version"], by_entity(r)
    ok = core_rows(s, "Material", "Code = N'T-OK' AND LocationId = :l", l=loc_id(s, L1))
    assert len(ok) == 1 and ok[0]["VersionFrom"] == v and ok[0]["BusinessKey"] == f"{L1}|T-OK"
    assert t["Material"]["new"] >= 5 and t["Material"]["not_transferred"] == 0
    assert not core_rows(s, "Material", "Code = N'T-OFF'")                                         # IsActive = Hayır aktarılmaz
    so = {x["OrderNo"]: x for x in core_rows(s, "SalesOrderLine", "OrderNo LIKE N'TS-%'")}
    assert so["TS-1"]["MaterialId"] == ok[0]["Id"] and so["TS-1"]["ProjectId"] is None              # isteğe bağlı bağlantı boş
    assert "TS-2" not in so                                                                          # zorunlu ilişki yok: aktarılmaz
    assert "TS-4" not in so                                                                          # savunma: zorunlu alan boş
    assert t["SalesOrderLine"]["note"] == ("1 satır, bağlı olduğu ana veri aktarılmadığı için aktarılmadı. "
                                           "1 satır, zorunlu alanı boş olduğu için aktarılmadı (İstek tarihi).")  # TS-2 ve TS-4 (validasyon çalışmadı)
    wo = {x["WorkOrderNo"]: x for x in core_rows(s, "WorkOrder", "WorkOrderNo LIKE N'TW-%'")}
    assert wo["TW-2"]["ParentWorkOrderId"] == wo["TW-1"]["Id"]                                      # tablo içi bağ
    assert s.execute(sa.text("SELECT COUNT(*) FROM prc.Material WHERE RowStatus = N'Aktarıldı'")).scalar() >= 5
    entities = s.execute(sa.text("SELECT EntityName, NewCount, Note FROM adm.DataVersionEntity WHERE DataVersionId = :v"), {"v": v}).all()
    assert {e for e, *_ in entities} == {e.table for e in ENTITIES}
    assert dict((e, n) for e, _, n in entities)["Forecast"] == transfer.NOTE_EMPTY                  # staging'de veri yok


def test_uom_conversion_is_expanded_and_units_created(s):
    transfer.run_transfer(s, None)
    rows = core_rows(s, "UomConversion", "FromUom IN (N'KOLI', N'KG', N'PAKET')")
    by_from = {}
    for row in rows:
        by_from.setdefault(row["FromUom"], []).append(row["MaterialId"])
    assert len(by_from["KOLI"]) == 2 and None not in by_from["KOLI"]                                 # iki lokasyonun T-OK'u
    assert by_from["PAKET"] == [None] and "KG" not in by_from                                        # genel; malzemesi yok → aktarılmaz
    units = dict(s.execute(sa.text("SELECT Code, Name FROM core.UnitOfMeasure WHERE Code IN (N'TKUTU', N'PAKET')")).all())
    assert units == {"TKUTU": None, "PAKET": "Paket"}


def test_second_transfer_keeps_unchanged_versions_changed_and_closes(s):
    first = transfer.run_transfer(s, None)["data_version"]
    before = core_rows(s, "Material", "Code = N'T-OK' AND LocationId = :l", l=loc_id(s, L1))[0]
    s.execute(sa.text("UPDATE core.Resource SET DailyCapacity = 8 WHERE Code = N'TR-1' AND VersionTo IS NULL"))
    set_prc(s, "Material", "Code = N'T-ERR'", Name="Yeni ad", RowStatus="Hatalı")    # Hatalı: önceki hâli kalır
    set_prc(s, "Material", "Code = N'T-PAS'", IsActive=0)                           # pasif: kapanır; ona bakan sipariş de
    set_prc(s, "Resource", "Code = N'TR-1'", Name="Tezgâh 2")                         # değişen
    s.execute(sa.text("INSERT INTO prc.Customer (StagingRowId, ImportBatchId, SourceRowNo, Code, Name, IsActive, RowStatus) "
                      "SELECT (SELECT MAX(StagingRowId) + 1 FROM stg.Customer), ImportBatchId, 99, N'TC-2', N'Yeni', 1, N'Yeni' FROM prc.Customer WHERE Code = N'TC-1'"))
    s.execute(sa.text("DELETE FROM prc.Customer WHERE Code = N'TC-1'"))
    r = transfer.run_transfer(s, None)
    v, t = r["data_version"], by_entity(r)
    after = core_rows(s, "Material", "Code = N'T-OK' AND LocationId = :l", l=loc_id(s, L1))[0]
    assert (after["Id"], after["VersionFrom"]) == (before["Id"], first)                              # değişmeyen: dokunulmadı
    err = core_rows(s, "Material", "Code = N'T-ERR'")
    assert len(err) == 1 and err[0]["Name"] == "Ad T-ERR" and err[0]["VersionFrom"] == first         # Hatalı: önceki hâli açık
    assert t["Material"]["not_transferred"] == 1
    assert not core_rows(s, "Material", "Code = N'T-PAS'")
    closed = core_rows(s, "Material", "Code = N'T-PAS'", current=False)
    assert len(closed) == 1 and closed[0]["VersionTo"] == v - 1
    assert not core_rows(s, "SalesOrderLine", "OrderNo = N'TS-3'")                                   # pasif ebeveyn: kapatıldı
    res = core_rows(s, "Resource", "Code = N'TR-1'", current=False)
    old, new = sorted(res, key=lambda x: x["VersionFrom"])
    assert old["VersionTo"] == v - 1 and new["VersionFrom"] == v and new["Id"] == old["Id"] and new["Name"] == "Tezgâh 2"
    assert new["DailyCapacity"] == 8                                                                  # Smartchain alanı korunur (K-117)
    assert t["Resource"]["changed"] == 1
    assert not core_rows(s, "Customer", "Code = N'TC-1'") and core_rows(s, "Customer", "Code = N'TC-2'")  # staging'de yok: kapatıldı
    assert t["Customer"]["closed"] >= 1 and t["Customer"]["new"] == 1


def test_empty_to_value_and_back_is_a_change(s):
    """5.2 düzeltmesi: tek değişikliği boş ↔ dolu olan kayıt değişmiş sayılır (yeni versiyon); aynı değer değişiklik değildir."""
    first = transfer.run_transfer(s, None)["data_version"]
    set_prc(s, "Material", "Code = N'T-OK' AND LocationCode = N'TL-1'", MaterialGroup=None)    # dolu → boş
    set_prc(s, "Material", "Code = N'T-ERR'", MaterialGroup="G2")                              # boş → dolu
    second = transfer.run_transfer(s, None)
    v, t = second["data_version"], by_entity(second)
    ok = core_rows(s, "Material", "Code = N'T-OK' AND LocationId = :l", l=loc_id(s, L1))[0]
    err = core_rows(s, "Material", "Code = N'T-ERR'")[0]
    assert (ok["VersionFrom"], ok["MaterialGroup"]) == (v, None) and (err["VersionFrom"], err["MaterialGroup"]) == (v, "G2")
    assert t["Material"]["changed"] == 2
    third = by_entity(transfer.run_transfer(s, None))                                           # değişiklik yok: yeni versiyon yok
    assert third["Material"]["changed"] == 0 and first < v


def test_differs_handles_empty_values(s):
    from app.transfer.engine import _differs
    def check(a, b, kind=sa.Unicode):
        x, y = (sa.literal_column(v if v is not None else "NULL", kind) for v in (a, b))
        return s.execute(sa.select(sa.case((_differs(sa.cast(x, kind), sa.cast(y, kind)), 1), else_=0))).scalar()
    assert [check(None, "N'x'"), check("N'x'", None), check(None, None), check("N'x'", "N'x'"), check("N'x'", "N'X'")] == [1, 1, 0, 0, 1]
    assert [check(None, "5", sa.Integer), check("5", "5", sa.Integer), check("5", "6", sa.Integer)] == [1, 0, 1]


def test_threshold_skips_table_and_keeps_previous_version(s, monkeypatch):
    transfer.run_transfer(s, None)
    before = core_rows(s, "Resource", "Code = N'TR-1'")
    set_prc(s, "Resource", "Code = N'TR-1'", Name="Değişti")
    monkeypatch.setattr(transfer, "threshold_note", lambda session, e: "Eşik aşıldı: %50 > %5; tablo aktarılmadı." if e == "Resource" else None)
    t = by_entity(transfer.run_transfer(s, None))
    assert t["Resource"]["note"].startswith("Eşik aşıldı") and t["Resource"]["new"] is None
    assert core_rows(s, "Resource", "Code = N'TR-1'") == before


def test_value_source_for_rule_changed_fields(s):
    rule = s.execute(sa.text("INSERT INTO adm.DataRule (EntityName, Name, Seq, TargetField, ResultKind, Value, ApplyMode, IsActive, ResultText) OUTPUT inserted.Id "
                             "VALUES (N'Material', N'Test grubu', 1, N'MaterialGroup', N'Değer', N'G1', N'Her zaman', 1, N'MaterialGroup = G1')")).scalar()
    sid = s.execute(sa.text("SELECT StagingRowId FROM prc.Material WHERE Code = N'T-OK' AND LocationCode = :l"), {"l": L1}).scalar()
    s.execute(sa.text("INSERT INTO adm.DataRuleEffect (EntityName, StagingRowId, FieldName, DataRuleId, RawValue) VALUES (N'Material', :s, N'MaterialGroup', :r, N'ERP-G')"),
              {"s": sid, "r": rule})
    transfer.run_transfer(s, None)
    rid = core_rows(s, "Material", "Code = N'T-OK' AND LocationId = :l", l=loc_id(s, L1))[0]["Id"]
    src = s.execute(sa.text("SELECT FieldName, Source, DataRuleId, ErpValue FROM adm.FieldValueSource WHERE TableName = N'Material' AND RecordId = :r"), {"r": rid}).all()
    assert [tuple(x) for x in src] == [("MaterialGroup", "Kural", rule, "ERP-G")]
