"""Sentetik veri v0'ın içeriği (docs/11, K-78, K-79). Veritabanı gerekmez."""
import importlib.util
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app.data.synthetic import dataset as d
from app.data.synthetic import situations as s
from app.data.synthetic.dataset import generate
from db import models

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("generate", ROOT / "db" / "generate.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

DAY = date(2026, 10, 27)
EMPTY = {"TransferOrder"}  # docs/11: tek lokasyon (tahmin ve benzetilen ürün 6.5'ten beri dolu, K-174)
LOADER_FILLS = {"VersionFrom", "VersionTo", "ImportBatchId", "UpdatedAt", "IsSynthetic"}


@pytest.fixture(scope="module")
def ds():
    return generate(DAY)


def test_sizes_match_docs(ds):
    sm = s.summary(ds)
    assert 190 <= sm["Malzeme"] <= 210
    assert sm["Kaynak"] == 41 and sm["Çalışan"] == 25 and sm["Açık kesin sipariş"] == 42  # 6.5: T-05, SO-1043 ve SO-1044 (K-174)
    assert sm["Müşteri"] == 3 and sm["Tedarikçi"] == 8 and 23 <= sm["Çalışan"] <= 27
    assert ds.horizon_end == ds.start + timedelta(weeks=13, days=-1)
    assert ds.start.weekday() == 0 and ds.start <= DAY < ds.start + timedelta(days=7)  # hafta 1 (K-79)


def test_every_core_table_filled_except_documented(ds):
    core = {t.name for t in models.metadata.sorted_tables if t.schema == "core"}
    assert {t for t in core if not ds.rows(t)} == EMPTY
    assert set(ds.params) == {"PriorityRule", "SupplierLimit", "MaterialHold", "WorkPattern", "ResourceEfficiency", "OvertimeLimit", "ResourceDowntime", "FactoryCalendar",
                              "ResourceGroupConstraint"}  # Baz senaryoya bağlanır (K-175, K-185, K-189)


def test_values_fit_schema(ds):
    """Alan adları docs/02'de var, zorunlu alanlar dolu, metinler alan uzunluğuna sığar."""
    problems = []
    for name, rows in list(ds.tables.items()) + [(f"param.{k}", v) for k, v in ds.params.items()]:
        table = models.metadata.tables[name if "." in name else f"core.{name}"]
        required = {c.name for c in table.columns if not c.nullable and not c.autoincrement is True} - LOADER_FILLS
        for r in rows:
            problems += [f"{name}.{k}: bilinmeyen alan" for k in r if k not in table.c]
            problems += [f"{name}.{k}: zorunlu alan boş" for k in required if r.get(k) is None
                         and not (k == "Id" and name.startswith("param.")) and k != "ScenarioDefinitionId"]
            for k, v in r.items():
                size = getattr(table.c[k].type, "length", None) if k in table.c else None
                if isinstance(v, str) and size and len(v) > size:
                    problems.append(f"{name}.{k}: '{v}' > {size}")
    assert not sorted(set(problems))


def test_references_resolve(ds):
    """Her ...Id alanı var olan bir kayda gider (K-58: ana tablolar Id ile)."""
    targets = {**{k: (v if isinstance(v, str) else v[0]) for k, v in gen.REF_TARGET.items()},
               "LocationId": "Location",
               "ResourceGroupId": "ResourceGroup",
               "ProjectGroupId": "ProjectGroup", "CustomerId": "Customer",
               "SalesOrderLineId": "SalesOrderLine"}
    missing = []
    for name, rows in ds.tables.items():
        for r in rows:
            for k, v in r.items():
                if k.endswith("Id") and k != "Id" and v is not None and k in targets:
                    if targets[k] in ds.tables and v not in {x["Id"] for x in ds.rows(targets[k])}:
                        missing.append(f"{name}.{k}={v}")
    assert not missing
    labor = [r for r in ds.rows("Routing") if r["ResourceRole"] == "Secondary"]  # K-116: işçilik ayrı satır
    assert labor and all(ds.code("ResourceGroup", r["ResourceGroupId"]) == d.LABOR_GROUP and r["ResourceNumber"] == 2 for r in labor)
    primary = {(r["RouteCode"], r["OperationNo"]): r for r in ds.rows("Routing") if r["ResourceRole"] == "Primary"}
    assert all(r["Consumption"] == primary[(r["RouteCode"], r["OperationNo"])]["Consumption"] and r["SequenceNo"] == 2 for r in labor)
    assert all(r["ResourceGroupId"] and "ResourceId" not in r for r in ds.rows("Routing"))  # K-180: rotada kaynak yok, grup zorunlu
    keys = [(r["RouteCode"], r["OperationNo"], r["SequenceNo"]) for r in ds.rows("Routing")]
    assert len(keys) == len(set(keys))
    groups = {g["Id"]: g for g in ds.rows("ResourceGroup")}
    assert all(o["ResourceGroupId"] and "ResourceId" not in o for o in ds.rows("WorkOrderOperation"))
    assert not [o for o in ds.rows("WorkOrderOperation") if groups[o["ResourceGroupId"]]["IsEmployee"]]  # iş emri operasyonu yalnız Primary satırdan


def test_resource_side(ds):
    """K-180: planlama birimi kaynak grubu. Tip bayrağı, kritiklik, birim ve fasoncu grupta; kaynakta yalnız kimlik ve ham tip; eşleşme tarihsiz."""
    flags = ("IsEmployee", "IsMachine", "IsFurnace", "IsMold", "IsOther", "IsSubcontractor")
    groups = {g["Id"]: g for g in ds.rows("ResourceGroup")}
    assert all(sum(bool(g[f]) for f in flags) == 1 for g in groups.values())                       # her grubun tek tipi
    assert not [g for g in groups.values() if g["IsFurnace"] or g["IsMold"]]                       # Faz 1 dışı
    assert all(g["CapacityUnit"] == "SAAT" and g["IsCritical"] is not None for g in groups.values())
    assert not any(k in g for g in groups.values() for k in ("IsResourceGroup", "IsCompetenceGroup"))
    assert {g["Code"] for g in groups.values() if g["IsEmployee"]} == {"CG-CNC", "CG-MON", "CG-KAL"}   # yetkinlik grubu = işçi grubu
    fason = {g["Code"]: g for g in groups.values() if g["IsSubcontractor"]}
    assert set(fason) == {"F-ISIL", "F-KAPLA"} and all(g["SubcontractorId"] and not g["IsCritical"] for g in fason.values())
    moved = (*flags, "IsCritical", "CapacityUnit", "SubcontractorId", "CapacitySource", "Quantity")
    assert not [k for r in ds.rows("Resource") for k in moved if k in r]                           # kaynakta kalmadı
    assert {r["ResourceType"] for r in ds.rows("Resource")} == {"Makine", "İşçi", "Fason"}         # ham tip bilgi olarak durur
    members = ds.rows("ResourceGroupMember")
    assert not any(k in m for m in members for k in ("ValidFrom", "ValidTo"))                      # eşleşme tarihsiz
    keys = [(m["ResourceGroupId"], m["ResourceId"]) for m in members]
    assert len(keys) == len(set(keys))
    employees = s.employees(ds)
    by_resource = {}
    for m in members:
        by_resource.setdefault(m["ResourceId"], set()).add(m["ResourceGroupId"])
    assert set(by_resource) == {r["Id"] for r in ds.rows("Resource")}                              # her kaynak en az bir grupta
    assert len(employees) == 25 and all(all(groups[g]["IsEmployee"] for g in by_resource[r]) for r in employees)   # işçi yalnız işçi gruplarında
    assert any(len(by_resource[r]) > 1 for r in employees)                                         # birden fazla yetkinliği olan işçi
    units = {r: {groups[g]["CapacityUnit"] for g in gs} for r, gs in by_resource.items()}
    assert all(len(u) == 1 for u in units.values())                                                # üye olunan grupların birimi aynı
    assert all(a["ResourceId"] in employees and a["EndDate"] >= a["StartDate"] for a in ds.rows("EmployeeAbsence"))
    assert "Shift" not in ds.tables and "ShiftPlan" not in ds.tables                               # vardiya kalktı
    assert not [r for r in ds.rows("Routing") if r["ResourceRole"] == "Secondary" and not groups[r["ResourceGroupId"]]["IsEmployee"]]
    count = {g: sum(1 for m in members if m["ResourceGroupId"] == g) for g in groups}
    assert all(r["ResourceNumber"] <= count[r["ResourceGroupId"]] for r in ds.rows("Routing"))     # kaynak adedi gruptaki kaynak sayısını aşmaz
    assert count[ds.get("ResourceGroup", Code=d.BOTTLENECK_GROUP)["Id"]] == 1                      # darboğaz grubu tek üyeli


def test_bom_is_acyclic_with_three_or_four_levels(ds):
    children = s._bom_children(ds)

    def depth(mid, seen=()):
        assert mid not in seen, "ağaçta döngü"
        return 1 + max([depth(c, seen + (mid,)) for c, _ in children.get(mid, [])] or [0])
    finished = [m for m in ds.rows("Material") if m["MaterialLevel"] == "Nihai ürün" and m["Code"] != d.REFERENCE_PRODUCT]  # benzetilen ürünün ağacı yok
    assert len(finished) == 10 and {depth(m["Id"]) for m in finished} <= {3, 4} and max(
        depth(m["Id"]) for m in finished) == 4


def test_every_produced_material_has_version_and_route(ds):
    pv = {p["MaterialId"]: p for p in ds.rows("ProductionVersion")}
    routes = {r["RouteCode"] for r in ds.rows("Routing")}
    referenced = {r["MaterialId"] for r in ds.rows("MaterialReference")}  # benzetilen ürün başkasının versiyonuyla üretilir (K-174)
    for m in ds.rows("Material"):
        if m["IsProducible"] and m["Id"] not in referenced:
            assert m["Id"] in pv and pv[m["Id"]]["RouteCode"] in routes, m["Code"]
        if m["IsPurchasable"]:
            assert any(x["MaterialId"] == m["Id"] for x in ds.rows("MaterialSupplier")), m["Code"]


def test_deterministic_and_seed_sensitive(ds):
    again = generate(DAY)
    assert again.tables == ds.tables and again.params == ds.params
    other = generate(DAY, seed=7)
    assert [r["Name"] for r in other.rows("Resource") if r["ResourceType"] == "İşçi"] != [r["Name"] for r in ds.rows("Resource") if r["ResourceType"] == "İşçi"]


# Takvim ayına bağlı alanlar (aylık tedarikçi limiti, durum 3) hafta kaymasıyla değil, aya göre belirlenir.
MONTH_BOUND = {("PurchaseOrderLine", "PO-2041"), ("PurchaseOrderLine", "PO-2042")}


def test_dates_shift_with_generation_day(ds):
    later = generate(DAY + timedelta(days=7))
    for name, rows in ds.tables.items():
        for a, b in zip(rows, later.rows(name)):
            if (name, a.get("PurchaseOrderNo")) in MONTH_BOUND or name == "Forecast":  # tahmin dönemi ay başı (K-174)
                continue
            for k, v in a.items():
                if isinstance(v, (date, datetime)):
                    assert b[k] == v + timedelta(days=7), f"{name}.{k}"
                elif k != "BusinessKey":
                    assert b[k] == v, f"{name}.{k}"
    first, last = d.limit_month(later)
    limit = later.params["SupplierLimit"][0]
    assert (limit["ValidFrom"], limit["ValidTo"]) == (first, last)


@pytest.mark.parametrize("day", [DAY, date(2026, 12, 28), date(2027, 2, 26), date(2027, 6, 30), date.today()])
def test_intentional_situations(day):
    failed = [(c.no, c.name, c.detail) for c in s.all_checks(generate(day)) if not c.ok]
    assert not failed


def test_bottleneck_orders(ds):
    """Durum 1: hafta 3–5'teki aşırı yük SO-1011…1016'dan gelir."""
    load_by_order = {}
    m5 = ds.get("ResourceGroup", Code=d.BOTTLENECK_GROUP)["Id"]  # yük grup düzeyinde (K-180)
    for so in s.open_firm_orders(ds):
        if 3 <= ds.week_of(so["RequestedDate"]) <= 5:
            load_by_order[so["OrderNo"]] = s.resource_hours(ds, so["MaterialId"], so["OpenQuantity"], m5)
    heavy = {k for k, v in load_by_order.items() if v >= 40}
    assert heavy == {f"SO-{n}" for n in range(1011, 1017)}


@pytest.mark.parametrize("offset", range(7))
def test_no_accidental_past_due_on_any_weekday(offset):
    """Tarihten bağımsızlık (7.11): set haftanın hangi günü üretilirse üretilsin, bilerek konan sipariş (durum 9) dışında hiçbir açık sipariş, iş emri
    ya da satın alma siparişi "tarihi geçmiş" durumda değildir (kirli veri testi ve veri kalitesi beklenmeyen uyarı görmez). Pazartesi'den Pazar'a."""
    on = date(2026, 11, 16) + timedelta(days=offset)
    assert on.weekday() == offset
    ds = generate(on)
    late_orders = sorted(r["OrderNo"] for r in ds.rows("SalesOrderLine") if r["OpenQuantity"] > 0 and r["RequestedDate"] < on)
    assert late_orders == [d.PAST_DUE_ORDER]
    assert [r["WorkOrderNo"] for r in ds.rows("WorkOrder") if r["OpenQuantity"] > 0 and r["DueDate"] < on] == []
    assert [r["OrderNo"] for r in ds.rows("PurchaseOrderLine") if r["OpenQuantity"] > 0 and (r["ConfirmedDate"] or r["RequestedDate"]) < on] == []
    assert all(r["StartDate"] <= r["DueDate"] for r in ds.rows("WorkOrder"))
