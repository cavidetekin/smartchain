"""Üretim akışı (K-200): alternatifler (farklı ürün ağacı başına), miktar, alternatif grubu, hayalet, benzetilen ürün, kullananlar (sayfalı),
sentetik veri ve uçlar. Küme (`flow_data`) bir işlem içinde kurulur ve geri alınır; test veritabanının sentetik verisi değişmez."""
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import COOKIE
from app.api.errors import AppError
from app.api.main import create_app
from app.api.services import production_flow as flow

import flow_data
from auth_helpers import delete_users, ensure_user, token

pytestmark = pytest.mark.db


@pytest.fixture
def built(db_engine):
    """Küme test başına kurulur ve geri alınır: açık işlem öteki bağlantıların okumasını bekletir, modül boyunca açık tutulmaz."""
    with Session(db_engine) as s:
        try:
            yield s, flow_data.build(s)
        finally:
            s.rollback()


def shape(alternative: dict) -> list[tuple]:
    return [(i["material"]["code"], i["quantity"], i["uom"], i["group"], i["group_priority"]) for i in alternative["items"]]


def test_alternatives_are_distinct_trees(built):
    s, ids = built
    r = flow.components(s, ids["U-TOP"])
    assert r["reference"] is None
    # aynı ağacı kullanan V1 ve V3 tek alternatif; pasif V9 yok; sıra önceliğe göre
    assert [(a["no"], a["versions"], a["bom_code"]) for a in r["alternatives"]] == [(1, ["V1", "V3"], "B1"), (2, ["V2"], "B2")]
    # iki operasyondaki U-A toplanır (2 + 1); kendine bağlanan satır ve eski versiyon satırı yok; alternatif grubu alanları
    assert shape(r["alternatives"][0]) == [("U-A", 3.0, "ADET", None, None), ("U-PH", 1.0, "ADET", None, None), ("U-G1", 1.0, "ADET", "G1", 1), ("U-G2", 1.0, "ADET", "G1", 2)]
    # miktar taban miktara bölünür (taban 2); birim satırın birimi
    assert shape(r["alternatives"][1]) == [("U-A", 2.0, "ADET", None, None), ("U-RAW", 0.5, "KG", None, None)]


def test_boxes_carry_level_phantom_and_both_flags(built):
    s, ids = built
    items = {i["material"]["code"]: i["material"] for i in flow.components(s, ids["U-TOP"])["alternatives"][0]["items"]}
    assert items["U-PH"] == {"id": ids["U-PH"], "code": "U-PH", "name": "Hayalet takım", "level": "Yarı mamul", "phantom": True, "has_parents": True, "has_components": True}
    assert items["U-G1"]["has_components"] is False and items["U-A"]["has_components"] is True
    top = flow.read(s, ids["U-TOP"])
    assert top["location"] == flow_data.LOC and top["material"]["has_components"] is True and top["reference"] is None
    assert top["material"]["has_parents"] is False         # kendine bağlanan satır kenar değil (benzetilen ürün üzerinden de)
    assert flow.parents(s, ids["U-TOP"], 0, 20)["total"] == 0
    assert flow.read(s, ids["U-WIDE"])["material"]["has_parents"] is False
    # yalnız pasif versiyonun ya da eski satırın bileşeni: kullananı yok
    assert not flow.read(s, ids["U-X"])["material"]["has_parents"] and not flow.read(s, ids["U-OLD"])["material"]["has_parents"]
    assert flow.parents(s, ids["U-X"], 0, 20) == {"total": 0, "items": []}
    assert flow.components(s, ids["U-RAW"]) == {"reference": None, "alternatives": []}


def test_reference_product_opens_the_referenced_tree(built):
    s, ids = built
    whole = flow.components(s, ids["U-REF"])            # versiyon verilmemiş: benzetildiği ürünün bütün ağaçları
    assert whole["reference"] == {"code": "U-TOP"} and [a["versions"] for a in whole["alternatives"]] == [["V1", "V3"], ["V2"]]
    assert shape(whole["alternatives"][1]) == [("U-A", 2.0, "ADET", None, None), ("U-RAW", 0.5, "KG", None, None)]
    one = flow.components(s, ids["U-REF2"])             # versiyon verilmiş: yalnız o versiyonun ağacı
    assert one["reference"] == {"code": "U-TOP"} and [(a["no"], a["versions"]) for a in one["alternatives"]] == [(1, ["V2"])]
    assert flow.read(s, ids["U-REF"])["material"]["has_components"] is True
    # başlığın altındaki not için: seçili malzeme benzetilen ürünse ağacını kullandığı ürün
    assert flow.read(s, ids["U-REF"])["reference"] == {"code": "U-TOP"} == flow.read(s, ids["U-REF2"])["reference"] and flow.read(s, ids["U-A"])["reference"] is None


def test_parents_show_where_and_how_much(built):
    s, ids = built
    r = flow.parents(s, ids["U-A"], 0, 20)
    found = {i["material"]["code"]: (i["alternatives"], [(u["alternative"], u["quantity"], u["uom"]) for u in i["uses"]]) for i in r["items"]}
    assert r["total"] == 3 and [i["material"]["code"] for i in r["items"]] == ["U-REF", "U-REF2", "U-TOP"]     # koda göre
    assert found["U-TOP"] == (2, [(1, 3.0, "ADET"), (2, 2.0, "ADET")]) and found["U-REF"] == found["U-TOP"]
    assert found["U-REF2"] == (1, [(1, 2.0, "ADET")])
    raw = {i["material"]["code"]: i["uses"] for i in flow.parents(s, ids["U-RAW"], 0, 20)["items"]}
    assert set(raw) == {"U-A", "U-PH", "U-REF", "U-REF2", "U-TOP"} and raw["U-TOP"] == [{"alternative": 2, "quantity": 0.5, "uom": "KG", "group": None}]
    group = {i["material"]["code"]: i["uses"] for i in flow.parents(s, ids["U-G2"], 0, 20)["items"]}
    assert group["U-TOP"] == [{"alternative": 1, "quantity": 1.0, "uom": "ADET", "group": "G1"}]


def test_wide_structures_and_paging(built):
    s, ids = built
    wide = flow.components(s, ids["U-WIDE"])["alternatives"]
    assert len(wide) == 1 and [i["material"]["code"] for i in wide[0]["items"]] == [f"U-C{n:02d}" for n in range(1, 26)]
    first = flow.parents(s, ids["U-BOLT"], 0, 20)
    rest = flow.parents(s, ids["U-BOLT"], 20, 200)
    assert first["total"] == rest["total"] == 25 and len(first["items"]) == 20 and len(rest["items"]) == 5
    assert [i["material"]["code"] for i in first["items"] + rest["items"]] == [f"U-P{n:02d}" for n in range(1, 26)]
    assert first["items"][6]["uses"] == [{"alternative": 1, "quantity": 7.0, "uom": "ADET", "group": None}] and first["items"][6]["alternatives"] == 1


def test_unknown_material(built):
    s, _ = built
    for call in (lambda: flow.read(s, -5), lambda: flow.components(s, -5), lambda: flow.parents(s, -5, 0, 20)):
        with pytest.raises(AppError) as e:
            call()
        assert e.value.status_code == 404 and e.value.code == "not_found"


# ---------------------------------------------------------------------------------------------- sentetik veri ve uçlar
@pytest.fixture(scope="module")
def api(db_engine, test_users):
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.cookies.set(COOKIE, token(test_users[0]))
    return client


@pytest.fixture(scope="module")
def codes(db_engine) -> dict:
    with db_engine.connect() as c:
        return dict(c.execute(sa.text("SELECT m.Code, m.Id FROM core.Material m JOIN core.Location l ON l.Id = m.LocationId WHERE m.VersionTo IS NULL AND l.IsSynthetic = 1")).all())


def bom(engine, code: str, tree: str) -> dict:
    """Bağımsız kaynak: ağaç tablosundan bileşen → miktar (iş emri bileşenleri bu görünüme girmez)."""
    with engine.connect() as c:
        return {r[0]: float(r[1]) for r in c.execute(sa.text(
            "SELECT x.Code, SUM(b.Quantity) FROM core.BOM b JOIN core.Material m ON m.Id = b.MaterialId AND m.VersionTo IS NULL "
            "JOIN core.Material x ON x.Id = b.ComponentMaterialId AND x.VersionTo IS NULL WHERE b.VersionTo IS NULL AND m.Code = :m AND b.Code = :t GROUP BY x.Code"),
            {"m": code, "t": tree})}


def test_synthetic_single_and_double_alternative(api, db_engine, codes):
    top = api.get(f"/api/production-flow/{codes['MAM-006']}").json()
    assert top["material"] | {"id": 0} == {"id": 0, "code": "MAM-006", "name": top["material"]["name"], "level": "Nihai ürün", "phantom": False,
                                           "has_parents": False, "has_components": True} and top["location"]
    r = api.get(f"/api/production-flow/{codes['MAM-006']}/components").json()
    assert len(r["alternatives"]) == 1 and r["alternatives"][0]["versions"] == ["V1"]
    assert {i["material"]["code"]: i["quantity"] for i in r["alternatives"][0]["items"]} == bom(db_engine, "MAM-006", "B-MAM-006")
    assert all(i["uom"] and i["group"] is None for i in r["alternatives"][0]["items"])
    two = api.get(f"/api/production-flow/{codes['ALT-017']}/components").json()["alternatives"]
    assert [(a["no"], a["versions"], a["bom_code"]) for a in two] == [(1, ["V1"], "B-ALT-017"), (2, ["V2"], "B-ALT-017-2")]
    first, second = ({i["material"]["code"] for i in a["items"]} for a in two)
    assert second - first == {"SAT-001"} and not first - second
    leaf = api.get(f"/api/production-flow/{codes['HAM-008']}").json()["material"]
    assert leaf["has_components"] is False and leaf["has_parents"] is True and leaf["level"] == "Hammadde"


def test_synthetic_parents_and_reference(api, codes):
    r = api.get(f"/api/production-flow/{codes['SAT-003']}/parents").json()
    assert r["total"] == 10 and len(r["items"]) == 10 and all(i["material"]["code"].startswith("ALT-") and i["material"]["has_parents"] for i in r["items"])
    assert [i["material"]["code"] for i in r["items"]] == sorted(i["material"]["code"] for i in r["items"])
    page = api.get(f"/api/production-flow/{codes['SAT-003']}/parents?offset=8&limit=5").json()
    assert page["total"] == 10 and [i["material"]["code"] for i in page["items"]] == [i["material"]["code"] for i in r["items"][8:]]
    sat = {i["material"]["code"]: i for i in api.get(f"/api/production-flow/{codes['SAT-001']}/parents").json()["items"]}
    assert sat["ALT-017"]["alternatives"] == 2 and [u["alternative"] for u in sat["ALT-017"]["uses"]] == [2]      # yalnız ikinci ağaçta
    ref = api.get(f"/api/production-flow/{codes['MAM-011']}/components").json()                                    # benzetilen ürün (K-126)
    own = api.get(f"/api/production-flow/{codes['MAM-001']}/components").json()
    assert ref["reference"] == {"code": "MAM-001"} and own["reference"] is None and ref["alternatives"] == own["alternatives"]
    below = api.get(f"/api/production-flow/{own['alternatives'][0]['items'][0]['material']['id']}/parents").json()
    assert {"MAM-001", "MAM-011"} <= {i["material"]["code"] for i in below["items"]}                              # sol tarafta kullanan olarak da görünür


def test_png_download_is_audited(api, db_engine, codes, test_users):
    """PNG tarayıcıda üretilir; uç yalnız izi yazar ve dosya adını verir (grafik görseli gibi, K-179; K-108)."""
    count = "SELECT COUNT(*) FROM adm.AuditLog WHERE Action = N'Dışa aktarım' AND ObjectType = N'production-flow'"
    with db_engine.connect() as c:
        before = c.execute(sa.text(count)).scalar()
    try:
        r = api.post(f"/api/production-flow/{codes['MAM-006']}/export-log")
        assert r.status_code == 200 and r.json() == {"file_name": "uretim-akisi-MAM-006.png"}, r.text
        with db_engine.connect() as c:
            row = c.execute(sa.text("SELECT TOP 1 UserId, ObjectKey, NewValue FROM adm.AuditLog WHERE Action = N'Dışa aktarım' AND ObjectType = N'production-flow' ORDER BY Id DESC")).one()
            assert c.execute(sa.text(count)).scalar() == before + 1
        assert row.UserId == test_users[0] and row.ObjectKey == "uretim-akisi-MAM-006.png"
        assert '"material": "MAM-006"' in row.NewValue and '"format": "png"' in row.NewValue and '"title": "Üretim akışı"' in row.NewValue
        assert api.post("/api/production-flow/0/export-log").status_code == 404
        assert api.get(f"/api/production-flow/{codes['MAM-011']}").json()["reference"] == {"code": "MAM-001"}
        assert api.get(f"/api/production-flow/{codes['MAM-006']}").json()["reference"] is None
    finally:
        with db_engine.begin() as c:
            c.execute(sa.text("DELETE FROM adm.AuditLog WHERE Action = N'Dışa aktarım' AND ObjectType = N'production-flow' AND UserId = :u"), {"u": test_users[0]})


def test_endpoint_errors_and_roles(api, db_engine, codes):
    for path in ("/api/production-flow/0", "/api/production-flow/0/components", "/api/production-flow/0/parents"):
        r = api.get(path)
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found", r.text
    assert api.get(f"/api/production-flow/{codes['SAT-003']}/parents?limit=201").status_code == 422
    assert api.get("/api/production-flow/abc").status_code == 422
    names = {role: f"test.flow.{role.split()[0].lower()}" for role in ("System owner", "Admin", "Key user", "End user")}
    with db_engine.begin() as c:
        users = {role: ensure_user(c, name, role) for role, name in names.items()}
    try:
        for role, user in users.items():      # görüntüleme: bütün roller (End user dahil)
            client = TestClient(create_app(), raise_server_exceptions=False)
            client.cookies.set(COOKIE, token(user))
            for path in ("", "/components", "/parents"):
                assert client.get(f"/api/production-flow/{codes['MAM-006']}{path}").status_code == 200, (role, path)
            assert client.post(f"/api/production-flow/{codes['MAM-006']}/export-log").status_code == 200, role      # indirme: görüntüleyen her rol
        with db_engine.begin() as c:
            c.execute(sa.text("DELETE FROM adm.AuditLog WHERE Action = N'Dışa aktarım' AND ObjectType = N'production-flow' AND UserId IN :u").bindparams(
                sa.bindparam("u", expanding=True)), {"u": list(users.values())})
        assert TestClient(create_app(), raise_server_exceptions=False).get(f"/api/production-flow/{codes['MAM-006']}").status_code == 401
    finally:
        with db_engine.begin() as c:
            delete_users(c, list(users.values()))
