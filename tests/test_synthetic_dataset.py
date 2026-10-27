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
EMPTY = {"Forecast", "TransferOrder"}  # docs/11: tahmin üretilmez; tek lokasyon
LOADER_FILLS = {"VersionFrom", "VersionTo", "ImportBatchId", "UpdatedAt", "IsSynthetic"}


@pytest.fixture(scope="module")
def ds():
    return generate(DAY)


def test_sizes_match_docs(ds):
    sm = s.summary(ds)
    assert 190 <= sm["Malzeme"] <= 210
    assert sm["Kaynak"] == 15 and sm["Açık kesin sipariş"] == 40
    assert sm["Müşteri"] == 3 and sm["Tedarikçi"] == 8 and 23 <= sm["Çalışan"] <= 27
    assert ds.horizon_end == ds.start + timedelta(weeks=13, days=-1)
    assert ds.start.weekday() == 0 and ds.start <= DAY < ds.start + timedelta(days=7)  # hafta 1 (K-79)


def test_every_core_table_filled_except_documented(ds):
    core = {t.name for t in models.metadata.sorted_tables if t.schema == "core"}
    assert {t for t in core if not ds.rows(t)} == EMPTY
    assert set(ds.params) == {"ParameterSet", "PlanningSetting", "TimeBucketDefinition", "PriorityRule", "SupplierLimit"}


def test_values_fit_schema(ds):
    """Alan adları docs/02'de var, zorunlu alanlar dolu, metinler alan uzunluğuna sığar."""
    problems = []
    for name, rows in list(ds.tables.items()) + [(f"param.{k}", v) for k, v in ds.params.items()]:
        table = models.metadata.tables[name if "." in name else f"core.{name}"]
        required = {c.name for c in table.columns if not c.nullable and not c.autoincrement is True} - LOADER_FILLS
        for r in rows:
            problems += [f"{name}.{k}: bilinmeyen alan" for k in r if k not in table.c]
            problems += [f"{name}.{k}: zorunlu alan boş" for k in required if r.get(k) is None
                         and not (k == "Id" and name.startswith("param.")) and k != "ParameterSetId"]
            for k, v in r.items():
                size = getattr(table.c[k].type, "length", None) if k in table.c else None
                if isinstance(v, str) and size and len(v) > size:
                    problems.append(f"{name}.{k}: '{v}' > {size}")
    assert not sorted(set(problems))


def test_references_resolve(ds):
    """Her ...Id alanı var olan bir kayda gider (K-58: ana tablolar Id ile)."""
    targets = {**{k: (v if isinstance(v, str) else v[0]) for k, v in gen.REF_TARGET.items()},
               "LocationId": "Location", "CalendarId": "Calendar", "ShiftId": "Shift", "WorkerId": "Worker",
               "CompetenceGroupId": "CompetenceGroup", "ResourceGroupId": "ResourceGroup",
               "ProjectGroupId": "ProjectGroup", "CustomerId": "Customer", "ProductionVersionId": "ProductionVersion",
               "SalesOrderLineId": "SalesOrderLine"}
    missing = []
    for name, rows in ds.tables.items():
        for r in rows:
            for k, v in r.items():
                if k.endswith("Id") and k != "Id" and v is not None and k in targets:
                    if targets[k] in ds.tables and v not in {x["Id"] for x in ds.rows(targets[k])}:
                        missing.append(f"{name}.{k}={v}")
    assert not missing
    labor = [r for r in ds.rows("Routing") if r.get("LaborRefId")]
    assert labor and all(r["LaborType"] == "Yetkinlik grubu" and ds.code("CompetenceGroup", r["LaborRefId"])
                         for r in labor)


def test_bom_is_acyclic_with_three_or_four_levels(ds):
    children = s._bom_children(ds)

    def depth(mid, seen=()):
        assert mid not in seen, "ağaçta döngü"
        return 1 + max([depth(c, seen + (mid,)) for c, _ in children.get(mid, [])] or [0])
    finished = [m for m in ds.rows("Material") if m["MaterialLevel"] == "Nihai ürün"]
    assert len(finished) == 10 and {depth(m["Id"]) for m in finished} <= {3, 4} and max(
        depth(m["Id"]) for m in finished) == 4


def test_every_produced_material_has_version_and_route(ds):
    pv = {p["MaterialId"]: p for p in ds.rows("ProductionVersion")}
    routes = {r["RouteCode"] for r in ds.rows("Routing")}
    for m in ds.rows("Material"):
        if m["IsProducible"]:
            assert m["Id"] in pv and pv[m["Id"]]["RouteCode"] in routes, m["Code"]
        if m["IsPurchasable"]:
            assert any(x["MaterialId"] == m["Id"] for x in ds.rows("MaterialSupplier")), m["Code"]


def test_deterministic_and_seed_sensitive(ds):
    again = generate(DAY)
    assert again.tables == ds.tables and again.params == ds.params
    other = generate(DAY, seed=7)
    assert [w["Name"] for w in other.rows("Worker")] != [w["Name"] for w in ds.rows("Worker")]


# Takvim ayına bağlı alanlar (aylık tedarikçi limiti, durum 3) hafta kaymasıyla değil, aya göre belirlenir.
MONTH_BOUND = {("PurchaseOrderLine", "PO-2041"), ("PurchaseOrderLine", "PO-2042")}


def test_dates_shift_with_generation_day(ds):
    later = generate(DAY + timedelta(days=7))
    for name, rows in ds.tables.items():
        for a, b in zip(rows, later.rows(name)):
            if (name, a.get("OrderNo")) in MONTH_BOUND:
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
    m5 = ds.get("Resource", Code=d.BOTTLENECK_RESOURCE)["Id"]
    for so in s.open_firm_orders(ds):
        if 3 <= ds.week_of(so["RequestedDate"]) <= 5:
            load_by_order[so["OrderNo"]] = s.resource_hours(ds, so["MaterialId"], so["OpenQty"], m5)
    heavy = {k for k, v in load_by_order.items() if v >= 40}
    assert heavy == {f"SO-{n}" for n in range(1011, 1017)}
