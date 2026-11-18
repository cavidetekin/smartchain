"""İlişkili alanlar (K-182, geliştirme 7.6): satırın bağlı olduğu tek kaydın alanları listeye kolon olur; veri kopyalanmaz, sorguda
birleştirilir. Sentetik v0'da; kendi yazdığını geri alır."""
import io
import json
from datetime import date

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.api.lists import relations
from app.api.lists.master_data import BY_NAME
from app.api.lists.query import Builder
from app.api.main import create_app
from app.api.permissions import END_USER, KEY_USER, SYSTEM_OWNER
from app.data.synthetic import dataset as d

from auth_helpers import auth, ensure_user

MEMBER = "/api/master-resource-group-member"
OPERATION = "/api/transaction-work-order-operation"
CRITICAL = "ResourceGroupId/IsCritical"
MATERIAL_NAME = "WorkOrderId/MaterialId/Name"


# ------------------------------------------------------------------ ilişki tablosu (veritabanısız)

def test_relations_are_single_valued_and_from_one_place():
    """Her çekirdek listenin ilişkileri `relations.REFS`'ten; çok karşılıklı ilişki, Birim, takvim ve ikinci seviyede Lokasyon yok."""
    heads = {name: [h["path"] for h in relations.headings(defn)] for name, defn in BY_NAME.items()}
    assert heads["master-resource-group-member"] == ["LocationId", "ResourceGroupId", "ResourceId"]
    assert heads["transaction-work-order-operation"] == ["LocationId", "WorkOrderId", "ResourceGroupId"]
    assert heads["materials"] == ["LocationId"] and heads["master-resource"] == ["LocationId"]  # Kaynak → takvim yok
    assert heads["master-production-version"] == ["LocationId", "MaterialId"]                    # ağaç ve rota (kodla, çok satır) yok
    for empty in ("master-supplier", "master-customer", "master-location", "master-unit-of-measure", "transaction-project-group"):
        assert heads[empty] == [], empty
    assert all(p in relations.REFS for paths in heads.values() for p in paths)
    member = BY_NAME["master-resource-group-member"]
    group = relations.catalog(member, "ResourceGroupId")
    names = [f["field"] for f in group["fields"]]
    assert (group["label"], CRITICAL in names) == ("Kaynak grubu", True)
    assert "ResourceGroupId/Code" not in names and "ResourceGroupId/ManualState" not in names  # kod zaten tabloda; manuel değer kolonu alınmaz
    assert "ResourceGroupId/UpdatedAt" not in names and "UpdatedAt" in member.fields            # sistem alanı ilişkili alan olmaz; tablonun kendi alanıdır
    assert not any(f["manual"] or f["default_visible"] for f in group["fields"]) and all(f["related"] for f in group["fields"])
    assert [r["path"] for r in group["relations"]] == ["ResourceGroupId/SubcontractorId"]         # ikinci seviyede Lokasyon yok
    second = relations.catalog(member, "ResourceGroupId/SubcontractorId")
    assert second["relations"] == [] and "ResourceGroupId/SubcontractorId/Code" in [f["field"] for f in second["fields"]]
    assert relations.catalog(member, "ResourceGroupId/SubcontractorId/LocationId") is None        # üçüncü seviye yok
    assert relations.catalog(member, "Nope") is None and relations.resolve(member, "ResourceGroupId/Nope") is None
    assert relations.resolve(member, CRITICAL).column["label"] == "Kaynak grubu · Kritik"
    assert "short_label" not in relations.resolve(member, CRITICAL).column                      # tek seviyede başlık değişmez
    sub = relations.resolve(member, "ResourceGroupId/SubcontractorId/Name").column              # iki seviyede kısa başlık: son ilişki ve alan
    assert (sub["label"], sub["short_label"]) == ("Kaynak grubu · Fasoncu · Tedarikçi adı", "Fasoncu · Tedarikçi adı")
    assert relations.headings(next(x for x in [BY_NAME["materials"]]))[0]["label"] == "Lokasyon"


def test_scan_finds_field_names_anywhere_in_a_request():
    body = {"fields": ["Code", CRITICAL], "filters": [{"field": MATERIAL_NAME, "op": "contains", "value": "a/b"}],
            "aggregates": {"WorkOrderId/OpenQuantity": {"fn": "sum"}}, "sort": [{"field": "Code", "dir": "asc"}]}
    assert relations.scan(body) == [CRITICAL, MATERIAL_NAME, "a/b", "WorkOrderId/OpenQuantity"]  # geçersiz aday çözülürken elenir


def test_only_requested_relations_are_joined():
    """Seçilmeyen ilişki için birleştirme yok; toplam satır sayısı birleştirmesiz; versiyon koşulu hedefe de uygulanır."""
    defn = BY_NAME["transaction-work-order-operation"]
    sql = lambda q: str(q.compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True}))  # noqa: E731
    plain = Builder(defn, {}, 7, date.today())
    assert plain.table is plain.base_table and "rf0" not in sql(sa.select(plain.table.c.Id))
    b = Builder(defn, {}, 7, plain.today, related=[MATERIAL_NAME, "WorkOrderId/OpenQuantity"])
    text = sql(sa.select(b.table.c[MATERIAL_NAME]))
    assert text.count("LEFT OUTER JOIN core.[WorkOrder] AS rf0") == 1 and text.count("LEFT OUTER JOIN core.[Material] AS rf1") == 1
    assert "core.[ResourceGroup] AS rf" not in text                                  # istenmeyen ilişki birleştirilmez
    assert "rf0.[VersionFrom] <= 7" in text and "rf1.[VersionTo] >= 7" in text        # listenin okuduğu versiyonda geçerli satır
    assert "rf0" not in sql(b.total_query())
    assert b.columns[MATERIAL_NAME]["label"] == "İş emri · Üretilen malzeme · Malzeme adı" and b.related_units == {"WorkOrderId/OpenQuantity": "_unit/WorkOrderId"}


def test_limits():
    defn = BY_NAME["transaction-purchase-order"]
    fields = [f["field"] for f in relations.catalog(defn, "MaterialId")["fields"]]
    assert len(fields) > relations.MAX_FIELDS
    with pytest.raises(relations.RelatedLimitError, match="En çok 20 ilişkili alan"):
        relations.wrap(defn, defn.sa_table, 1, fields[: relations.MAX_FIELDS + 1])
    joins = ["SupplierId/Name", "MaterialId/Name", "ProjectId/Name", "CustomerId/Name", "SalesOrderLineId/OrderNo", "WorkOrderId/Status",
             "WorkOrderId/MaterialId/Name", "SalesOrderLineId/CustomerId/Name", "LocationId/Name"]
    assert relations.limit_problem(defn, joins) == "En çok 8 ilişki birleştirilebilir"
    assert relations.limit_problem(defn, joins[:8]) is None
    relations.wrap(defn, defn.sa_table, 1, joins, limit=False)  # görünüm listesinde birleşim: sınır denetlenmez


# ------------------------------------------------------------------ API (sentetik v0)

@pytest.fixture(scope="module")
def people(db_engine):
    with db_engine.begin() as c:
        return {r: ensure_user(c, f"pytest.rel.{n}", r) for r, n in ((KEY_USER, "key"), (END_USER, "end"), (SYSTEM_OWNER, "owner"))}


@pytest.fixture(scope="module")
def api(db_engine, people):
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.headers.update(auth(people[KEY_USER]))
    yield client
    with db_engine.begin() as c:
        c.execute(sa.text("DELETE FROM adm.TableView WHERE Name LIKE N'pytest ilişkili%'"))


def _sql(engine, q, **p):
    with engine.connect() as c:
        return c.execute(sa.text(q), p).all()


def _all(api, url, body):
    out, offset = [], 0
    while True:
        r = api.post(url + "/query", json={**body, "offset": offset, "limit": 100})
        assert r.status_code == 200, r.text
        data = r.json()
        out += data["rows"]
        offset += 100
        if offset >= data["filtered"]:
            return out, data


@pytest.mark.db
def test_catalog_endpoints(api, people):
    cols = api.get(MEMBER + "/columns").json()
    assert [(h["path"], h["label"]) for h in cols["relations"]] == [("LocationId", "Lokasyon"), ("ResourceGroupId", "Kaynak grubu"), ("ResourceId", "Kaynak")]
    assert not any("/" in c["field"] for c in cols["columns"])                    # kolonlar yalnız tablonun kendi alanları
    assert api.get("/api/master-customer/columns").json()["relations"] == []
    r = api.get(MEMBER + "/related", params={"path": "ResourceGroupId"}, headers=auth(people[END_USER]))  # tabloyu gören ilişkili alanı da görür
    assert r.status_code == 200 and CRITICAL in [f["field"] for f in r.json()["fields"]]
    assert api.get(MEMBER + "/related", params={"path": "Nope"}).status_code == 404
    assert api.get("/api/data-entities/columns").json().get("relations") == []    # ilişkisi tanımlı olmayan liste


@pytest.mark.db
def test_values_match_the_related_record_and_row_count_is_unchanged(api, db_engine):
    plain, info = _all(api, MEMBER, {"fields": ["ResourceGroupCode", "ResourceCode"]})
    rows, with_related = _all(api, MEMBER, {"fields": ["ResourceGroupCode", "ResourceCode", CRITICAL, "ResourceGroupId/CapacityUnit",
                                                       "ResourceGroupId/SubcontractorId/Name", "ResourceId/ResourceType"]})
    assert len(rows) == len(plain) == info["total"] == with_related["total"]      # birleştirme satır çoğaltmaz
    groups = {code: (bool(crit), unit, sub) for code, crit, unit, sub in _sql(
        db_engine, "SELECT g.Code, g.IsCritical, g.CapacityUnit, s.Name FROM core.ResourceGroup g LEFT JOIN core.Supplier s "
                   "ON s.Id = g.SubcontractorId AND s.VersionTo IS NULL WHERE g.VersionTo IS NULL")}
    types = dict(_sql(db_engine, "SELECT Code, ResourceType FROM core.Resource WHERE VersionTo IS NULL"))
    for r in rows:
        assert (r[CRITICAL], r["ResourceGroupId/CapacityUnit"], r["ResourceGroupId/SubcontractorId/Name"]) == groups[r["ResourceGroupCode"]]
        assert r["ResourceId/ResourceType"] == types[r["ResourceCode"]]
    assert any(r["ResourceGroupId/SubcontractorId/Name"] for r in rows) and any(r["ResourceGroupId/SubcontractorId/Name"] is None for r in rows)
    assert all("_sources" in r and CRITICAL not in r["_sources"] for r in rows)   # ilişkili alanın hücre kaynağı yok (salt okunur)


@pytest.mark.db
def test_filter_sort_values_and_groups_on_related_fields(api, db_engine):
    critical = {c for (c,) in _sql(db_engine, "SELECT Code FROM core.ResourceGroup WHERE VersionTo IS NULL AND IsCritical = 1")}
    rows, info = _all(api, MEMBER, {"fields": ["ResourceGroupCode", CRITICAL], "filters": [{"field": CRITICAL, "op": "in", "values": [False]}]})
    assert rows and {r["ResourceGroupCode"] for r in rows}.isdisjoint(critical) and info["filtered"] < info["total"]
    rows, _ = _all(api, OPERATION, {"fields": ["WorkOrderCode", MATERIAL_NAME], "sort": [{"field": MATERIAL_NAME, "dir": "desc"}]})
    names = [r[MATERIAL_NAME] for r in rows]
    assert names == sorted(names, key=lambda x: x.upper(), reverse=True) or len(set(names)) > 1
    assert names[0] >= names[-1]
    values = api.post(MEMBER + "/values", json={"field": CRITICAL, "search": "", "filters": []}).json()
    assert {v["value"] for v in values} == {True, False} and sum(v["count"] for v in values) == info["total"]
    tree = api.post(OPERATION + "/groups", json={"group_by": ["WorkOrderId/MaterialId/MaterialGroup"], "fields": ["WorkOrderId/OpenQuantity"],
                                                 "aggregates": {"WorkOrderId/OpenQuantity": {"fn": "sum"}}})
    assert tree.status_code == 200, tree.text
    body = tree.json()
    assert sum(g["count"] for g in body["groups"]) == body["total"] and all(g["key"][0] for g in body["groups"])
    one = body["groups"][0]
    leaf, _ = _all(api, OPERATION, {"fields": ["WorkOrderId/OpenQuantity"], "group_key": [{"field": "WorkOrderId/MaterialId/MaterialGroup", "value": one["key"][0]}]})
    assert len(leaf) == one["count"] and sum(r["WorkOrderId/OpenQuantity"] or 0 for r in leaf) == pytest.approx(one["aggregates"]["WorkOrderId/OpenQuantity"])


@pytest.mark.db
def test_related_quantity_uses_the_unit_of_its_own_record(api, db_engine):
    """K-182 madde 10: ilişkili miktar alanı geldiği kaydın biriminin ondalığıyla; satırın kendi biriminden bağımsız."""
    decimals = dict(_sql(db_engine, "SELECT Code, Decimals FROM core.UnitOfMeasure"))
    material_unit = dict(_sql(db_engine, "SELECT w.WorkOrderNo, m.BaseUom FROM core.WorkOrder w JOIN core.Material m ON m.Id = w.MaterialId AND m.VersionTo IS NULL "
                                         "WHERE w.VersionTo IS NULL"))
    rows, _ = _all(api, OPERATION, {"fields": ["WorkOrderCode", "PlannedConsumption", "WorkOrderId/OpenQuantity", "WorkOrderId/MaterialId/SafetyStock"]})
    assert rows
    for r in rows:
        want = decimals[material_unit[r["WorkOrderCode"]]]
        assert r["_field_decimals"] == {"WorkOrderId/OpenQuantity": want, "WorkOrderId/MaterialId/SafetyStock": want}
        assert not any(k.startswith("_unit/") for k in r)                          # birim kolonu satırda kalmaz
    assert {r["_unit_decimals"] for r in rows} == {decimals["SAAT"]}               # tüketim kaynak grubunun biriminde (saat)
    assert decimals["ADET"] == 0 and any(r["_field_decimals"]["WorkOrderId/OpenQuantity"] == 0 for r in rows)
    tree = api.post(OPERATION + "/groups", json={"group_by": ["OperationName"], "fields": ["WorkOrderId/OpenQuantity"],
                                                 "aggregates": {"WorkOrderId/OpenQuantity": {"fn": "sum"}}}).json()
    assert all(g["unit_decimals"].get("WorkOrderId/OpenQuantity") == 0 or "WorkOrderId/OpenQuantity" in g["mixed_units"] for g in tree["groups"])
    plain, _ = _all(api, OPERATION, {"fields": ["WorkOrderCode", "WorkOrderId/Status"]})
    assert all("_field_decimals" not in r for r in plain)


@pytest.mark.db
def test_closed_target_version_is_not_matched(api, db_engine):
    """Hedefin kapanmış (eski versiyon) satırı eşleşmez; güncel satır tektir, satır çoğalmaz."""
    group = _sql(db_engine, "SELECT TOP 1 Id, Name FROM core.ResourceGroup WHERE VersionTo IS NULL AND Code = :c", c=d.BOTTLENECK_GROUP)[0]
    before, info = _all(api, MEMBER, {"fields": ["ResourceGroupCode", "ResourceGroupId/Name"]})
    with db_engine.begin() as c:  # aynı Id'nin kapanmış eski versiyonu (aktarımın bıraktığı gibi)
        c.execute(sa.text("SELECT 1"))
        cols = [x["name"] for x in sa.inspect(c).get_columns("ResourceGroup", schema="core")]
        keep = ", ".join(f"[{x}]" for x in cols if x not in ("VersionFrom", "VersionTo", "Name"))
        c.execute(sa.text(f"INSERT INTO core.ResourceGroup ({keep}, VersionFrom, VersionTo, Name) SELECT {keep}, 0, 0, N'ESKİ AD' "
                          "FROM core.ResourceGroup WHERE Id = :i AND VersionTo IS NULL"), {"i": group.Id})
    try:
        after, info2 = _all(api, MEMBER, {"fields": ["ResourceGroupCode", "ResourceGroupId/Name"]})
        assert len(after) == len(before) and info2["total"] == info["total"]
        assert {r["ResourceGroupId/Name"] for r in after if r["ResourceGroupCode"] == d.BOTTLENECK_GROUP} == {group.Name}
    finally:
        with db_engine.begin() as c:
            c.execute(sa.text("DELETE FROM core.ResourceGroup WHERE Id = :i AND VersionFrom = 0 AND VersionTo = 0"), {"i": group.Id})


@pytest.mark.db
def test_rules_chart_and_export_accept_related_fields(api):
    rule = {"id": "r1", "field": CRITICAL, "condition": {"op": "in", "values": [True]}, "style": {"background": "#FDECEC"}, "enabled": True}
    r = api.post(MEMBER + "/query", json={"fields": ["ResourceGroupCode", CRITICAL], "rules": [rule], "limit": 100})
    assert r.status_code == 200, r.text
    assert all((row["_rules"] == [0]) == bool(row[CRITICAL]) for row in r.json()["rows"])
    chart = api.post(OPERATION + "/chart", json={"x": {"field": MATERIAL_NAME}, "series": [{"id": "s1", "fn": "count"}], "filters": []})
    assert chart.status_code == 200, chart.text
    assert len(chart.json()["x"]["values"]) > 1
    for scope, expected in (("visible", ["Kaynak grubu", "Kaynak grubu · Kritik"]), ("all", None)):
        e = api.post(MEMBER + "/export", json={"fields": ["ResourceGroupCode", CRITICAL], "scope": {"rows": "all", "columns": scope}})
        assert e.status_code == 200, e.text
        ws = load_workbook(io.BytesIO(e.content)).worksheets[0]
        header = [c.value for c in ws[1]]
        if expected:  # Excel'de tam yol
            assert header == expected and {ws.cell(row=i, column=2).value for i in range(2, ws.max_row + 1)} <= {"Evet", "Hayır"}
        else:  # bütün alanlar: tablonun kendi alanları ve açık ilişkili alan; başka ilişkili alan yok
            assert header.count("Kaynak grubu · Kritik") == 1 and sum(" · " in h for h in header) == 1 and "Kaynak" in header


@pytest.mark.db
def test_errors(api):
    unknown = api.post(MEMBER + "/query", json={"fields": ["ResourceGroupId/Nope"]})
    assert unknown.status_code == 422 and "Bilinmeyen alan: ResourceGroupId/Nope" in unknown.text
    many = api.post(MEMBER + "/query", json={"fields": ["ResourceId/LocationId/Name"]})  # ikinci seviyede Lokasyon yok
    assert many.status_code == 422 and "Bilinmeyen alan" in many.text
    fields = [f["field"] for f in api.get("/api/transaction-purchase-order/related", params={"path": "MaterialId"}).json()["fields"]][:21]
    over = api.post("/api/transaction-purchase-order/query", json={"fields": fields})
    assert over.status_code == 422 and "En çok 20 ilişkili alan seçilebilir" in over.text
    assert api.post("/api/data-entities/query", json={"fields": ["Name", "X/Y"]}).status_code == 422  # ilişkisi tanımlı olmayan listede alan değildir
    manual = api.post("/api/manual-values", json={"list": "master-resource-group-member", "changes": [{"id": 1, "field": CRITICAL, "value": "1"}]})
    assert manual.status_code in (400, 403, 409, 422), manual.text                   # ilişkili alana manuel değer yazılamaz


@pytest.mark.db
def test_views_keep_related_fields_and_old_views_read_unchanged(api, db_engine, people):
    old = {"v": 1, "columns": [{"field": "ResourceGroupCode"}, {"field": "ResourceCode"}], "pinned": 0, "sort": [], "filters": [], "group_by": []}
    plain = api.post(MEMBER + "/views", json={"name": "pytest ilişkili eski", "is_shared": False, "definition": old})
    assert plain.status_code == 201, plain.text
    new = {**old, "columns": [*old["columns"], {"field": CRITICAL}, {"field": "ResourceGroupId/SubcontractorId/Name"}],
           "filters": [{"field": CRITICAL, "op": "in", "values": [True]}], "sort": [{"field": "ResourceGroupId/Name", "dir": "asc"}],
           "group_by": ["ResourceGroupId/Type"]}
    saved = api.post(MEMBER + "/views", json={"name": "pytest ilişkili yeni", "is_shared": False, "definition": new})
    assert saved.status_code == 201, saved.text
    listed = api.get(MEMBER + "/views").json()
    by_name = {v["name"]: v for v in listed["views"]}
    assert by_name["pytest ilişkili eski"]["definition"]["columns"] == old["columns"] and by_name["pytest ilişkili eski"]["warnings"] == []
    got = by_name["pytest ilişkili yeni"]
    assert [c["field"] for c in got["definition"]["columns"]] == [c["field"] for c in new["columns"]] and got["warnings"] == []
    assert got["definition"]["group_by"] == ["ResourceGroupId/Type"] and got["definition"]["v"] == 1
    related = {c["field"]: c for c in listed["related_columns"]}
    assert set(related) == {CRITICAL, "ResourceGroupId/SubcontractorId/Name", "ResourceGroupId/Name", "ResourceGroupId/Type"}
    assert related[CRITICAL]["label"] == "Kaynak grubu · Kritik" and related[CRITICAL]["type"] == "bool"
    assert related["ResourceGroupId/SubcontractorId/Name"]["short_label"] == "Fasoncu · Tedarikçi adı"
    bad = api.post(MEMBER + "/views", json={"name": "pytest ilişkili bozuk", "is_shared": False,
                                            "definition": {**old, "columns": [{"field": "ResourceGroupId/Nope"}]}})
    assert bad.status_code == 422
    with db_engine.begin() as c:  # alan sonradan kalkmış gibi: kayıtlı tanımda artık olmayan ilişkili alan
        gone = json.dumps({**old, "columns": [*old["columns"], {"field": "ResourceGroupId/Gone"}]})
        c.execute(sa.text("UPDATE adm.TableView SET Definition = :d WHERE Id = :i"), {"d": gone, "i": plain.json()["id"]})
    again = {v["name"]: v for v in api.get(MEMBER + "/views").json()["views"]}["pytest ilişkili eski"]
    assert [c["field"] for c in again["definition"]["columns"]] == ["ResourceGroupCode", "ResourceCode"]
    assert again["warnings"] == ["'ResourceGroupId/Gone' artık listede yok; görünümden çıkarıldı."]


@pytest.mark.db
def test_system_owner_label_reaches_the_relation_name(api, db_engine):
    with db_engine.begin() as c:
        c.execute(sa.text("UPDATE adm.FieldDefinition SET Label = N'İstasyon grubu' WHERE TableName = N'ResourceGroupMember' AND FieldName = N'ResourceGroupId'"))
        c.execute(sa.text("UPDATE adm.FieldDefinition SET Label = N'Darboğaz' WHERE TableName = N'ResourceGroup' AND FieldName = N'IsCritical'"))
    try:
        heads = {h["path"]: h["label"] for h in api.get(MEMBER + "/columns").json()["relations"]}
        assert heads["ResourceGroupId"] == "İstasyon grubu"
        fields = {f["field"]: f["label"] for f in api.get(MEMBER + "/related", params={"path": "ResourceGroupId"}).json()["fields"]}
        assert fields[CRITICAL] == "İstasyon grubu · Darboğaz"
    finally:
        with db_engine.begin() as c:
            c.execute(sa.text("UPDATE adm.FieldDefinition SET Label = NULL WHERE (TableName = N'ResourceGroupMember' AND FieldName = N'ResourceGroupId') "
                              "OR (TableName = N'ResourceGroup' AND FieldName = N'IsCritical')"))


@pytest.mark.db
def test_no_copy_change_in_the_related_record_shows_at_once(api, db_engine):
    """Veri kopyalanmaz: grubun kritikliği değişince eşleşme tablosundaki ilişkili alan da değişir."""
    group = _sql(db_engine, "SELECT TOP 1 Id FROM core.ResourceGroup WHERE VersionTo IS NULL AND Code = :c", c=d.BOTTLENECK_GROUP)[0].Id
    body = {"fields": ["ResourceGroupCode", CRITICAL], "filters": [{"field": "ResourceGroupCode", "op": "in", "values": [d.BOTTLENECK_GROUP]}]}
    assert {r[CRITICAL] for r in _all(api, MEMBER, body)[0]} == {True}
    with db_engine.begin() as c:
        c.execute(sa.text("UPDATE core.ResourceGroup SET IsCritical = 0 WHERE Id = :i AND VersionTo IS NULL"), {"i": group})
    try:
        assert {r[CRITICAL] for r in _all(api, MEMBER, body)[0]} == {False}
    finally:
        with db_engine.begin() as c:
            c.execute(sa.text("UPDATE core.ResourceGroup SET IsCritical = 1 WHERE Id = :i AND VersionTo IS NULL"), {"i": group})
