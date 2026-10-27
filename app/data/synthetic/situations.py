"""Bilerek konmuş durumların denetimi (docs/11): gerçek motor olmadan veriden çıkarılabilen kaba ölçüler.

Kaba kapasite yükü: açık kesin siparişler ağaç üzerinden patlatılır, kaynak saatleri siparişin termin haftasına
yazılır. En erken temin: tedarik süresi + mal kabul + üretim süreleri. Testler ve `check` komutu bunu kullanır.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

from . import dataset as d
from .dataset import Dataset, add_business_days


@dataclass
class Check:
    no: int
    name: str
    ok: bool
    detail: str


def _bom_children(ds: Dataset) -> dict[int, list[tuple[int, float]]]:
    pv_mat = {pv["Id"]: pv["MaterialId"] for pv in ds.rows("ProductionVersion") if pv["IsDefault"]}
    children = defaultdict(list)
    for r in ds.rows("BOM"):
        if r["ProductionVersionId"] in pv_mat:
            children[pv_mat[r["ProductionVersionId"]]].append((r["ComponentMaterialId"], r["Quantity"]))
    return children


def explode(ds: Dataset, material_id: int, qty: float) -> dict[int, float]:
    """Brüt ihtiyaç: malzeme ve bütün alt kırılımları (stok düşülmez)."""
    children = _bom_children(ds)
    need = defaultdict(float)

    def walk(mid, q):
        need[mid] += q
        for cid, per in children.get(mid, []):
            walk(cid, q * per)
    walk(material_id, qty)
    return dict(need)


def resource_hours(ds: Dataset, material_id: int, qty: float, resource_id: int) -> float:
    route_of = {pv["MaterialId"]: pv["RouteCode"] for pv in ds.rows("ProductionVersion") if pv["IsDefault"]}
    ops = defaultdict(float)
    for r in ds.rows("Routing"):
        if r["ResourceId"] == resource_id:
            ops[r["RouteCode"]] += r["Consumption"]
    return sum(q * ops.get(route_of.get(mid), 0.0) for mid, q in explode(ds, material_id, qty).items())


def open_firm_orders(ds: Dataset) -> list[dict]:
    return [s for s in ds.rows("SalesOrderLine") if s["Type"] == "Kesin" and s["Status"] == "Açık"]


def weekly_capacity(ds: Dataset, resource: dict, week: int) -> float:
    working = {r["Date"] for r in ds.rows("CalendarDay") if r["IsWorkingDay"] and r["CalendarId"] == resource["CalendarId"]}
    days = sum(1 for i in range(7) if ds.day(week, i) in working)
    return days * resource["DailyCapacity"] * resource["Quantity"]


def weekly_load(ds: Dataset, resource_code: str) -> dict[int, float]:
    res = ds.get("Resource", Code=resource_code)
    load = defaultdict(float)
    for so in open_firm_orders(ds):
        load[ds.week_of(so["RequestedDate"])] += resource_hours(ds, so["MaterialId"], so["OpenQty"], res["Id"])
    return dict(load)


def chain_lead_days(ds: Dataset, material_id: int) -> int:
    """En uzun üretim süresi zinciri (iş günü): malzeme + üretilen alt kırılımlar."""
    children = _bom_children(ds)
    mat = {m["Id"]: m for m in ds.rows("Material")}

    def lead(mid):
        m = mat[mid]
        if not m["IsProducible"]:
            return 0
        return (m["ProductionLeadTimeDays"] or 0) + max([lead(c) for c, _ in children.get(mid, [])] or [0])
    return lead(material_id)


def path_lead_days(ds: Dataset, top_id: int, target_id: int) -> int | None:
    """top'tan target'a giden yoldaki üretilen malzemelerin üretim süreleri toplamı (target hariç)."""
    children = _bom_children(ds)
    mat = {m["Id"]: m for m in ds.rows("Material")}

    def walk(mid):
        if mid == target_id:
            return 0
        best = None
        for c, _ in children.get(mid, []):
            sub = walk(c)
            if sub is not None:
                best = sub if best is None else max(best, sub)
        return None if best is None else best + (mat[mid]["ProductionLeadTimeDays"] or 0)
    return walk(top_id)


# --- Durumlar ---

def check_bottleneck(ds: Dataset) -> Check:
    res = ds.get("Resource", Code=d.BOTTLENECK_RESOURCE)
    load = weekly_load(ds, d.BOTTLENECK_RESOURCE)
    pct = {w: 100 * load.get(w, 0.0) / weekly_capacity(ds, res, w) for w in range(1, d.HORIZON_WEEKS + 1)}
    need_1_5 = sum(load.get(w, 0.0) for w in range(1, 6))
    cap_1_5 = sum(weekly_capacity(ds, res, w) for w in range(1, 6))
    peak_ok = all(pct[w] >= 130 for w in (3, 4, 5))
    rest_ok = all(pct[w] <= 70 for w in pct if w not in (3, 4, 5))
    ok = peak_ok and rest_ok and need_1_5 > cap_1_5
    detail = (f"{d.BOTTLENECK_RESOURCE} hafta 3: %{pct[3]:.0f}, 4: %{pct[4]:.0f}, 5: %{pct[5]:.0f}; "
              f"diğer haftalarda en çok %{max(v for w, v in pct.items() if w not in (3, 4, 5)):.0f}; "
              f"hafta 1–5 ihtiyaç {need_1_5:.0f} s > kapasite {cap_1_5:.0f} s")
    return Check(1, "5 eksen darboğazı (hafta 3–5)", ok, detail)


def check_late_material(ds: Dataset) -> Check:
    ham = ds.get("Material", Code=d.LATE_MATERIAL)
    so = ds.get("SalesOrderLine", OrderNo=d.LATE_ORDER)
    fg = ds.get("Material", Code=d.LATE_PRODUCT)
    sources = [ms for ms in ds.rows("MaterialSupplier") if ms["MaterialId"] == ham["Id"]]
    lead = min(ms["LeadTimeDays"] for ms in sources)
    arrival = ds.generated_on + timedelta(days=lead + (ham["GoodsReceiptDays"] or 0))
    production = path_lead_days(ds, fg["Id"], ham["Id"])
    ready = add_business_days(arrival, production)
    no_supply = (not any(s["MaterialId"] == ham["Id"] for s in ds.rows("Stock"))
                 and not any(p["MaterialId"] == ham["Id"] for p in ds.rows("PurchaseOrderLine")))
    used_by = {so_["MaterialId"] for so_ in open_firm_orders(ds) if ham["Id"] in explode(ds, so_["MaterialId"], 1)}
    ok = no_supply and ready > so["RequestedDate"] and used_by == {fg["Id"]}
    detail = (f"{d.LATE_MATERIAL} temin {lead} gün, en erken hazır {ready:%d.%m.%Y} > "
              f"{d.LATE_ORDER} termini {so['RequestedDate']:%d.%m.%Y}; stok ve açık sipariş yok")
    return Check(2, "Uzun temin süreli hammadde siparişi geciktirir", ok, detail)


def check_supplier_limit(ds: Dataset) -> Check:
    limit = ds.params["SupplierLimit"][0]
    sat = ds.get("Material", Code=d.LIMIT_MATERIAL)
    sup = ds.get("Supplier", Code=d.LIMIT_SUPPLIER)
    in_window = lambda x: x is not None and limit["ValidFrom"] <= x <= limit["ValidTo"]  # noqa: E731
    ordered = sum(p["OpenQty"] for p in ds.rows("PurchaseOrderLine")
                  if p["MaterialId"] == sat["Id"] and p["SupplierId"] == sup["Id"] and in_window(p["ConfirmedDate"]))
    gross = sum(explode(ds, so["MaterialId"], so["OpenQty"]).get(sat["Id"], 0.0)
                for so in open_firm_orders(ds) if in_window(so["RequestedDate"]))
    stock = sum(s["Quantity"] for s in ds.rows("Stock") if s["MaterialId"] == sat["Id"] and s["StockStatus"] == "Serbest")
    ok = ordered == limit["UpperLimit"] and gross - stock > 0
    detail = (f"{d.LIMIT_SUPPLIER} · {d.LIMIT_MATERIAL} {limit['ValidFrom']:%m.%Y} limiti {limit['UpperLimit']:.0f}, "
              f"teyitli sipariş {ordered:.0f}; aynı ayda ihtiyaç {gross:.0f} − stok {stock:.0f} > 0")
    return Check(3, "Tedarikçinin aylık limiti dolu", ok, detail)


def check_impossible_due(ds: Dataset) -> Check:
    so = ds.get("SalesOrderLine", OrderNo=d.IMPOSSIBLE_ORDER)
    fg = ds.get("Material", Code=d.IMPOSSIBLE_PRODUCT)
    lead = chain_lead_days(ds, fg["Id"])
    earliest = add_business_days(ds.generated_on, lead)
    no_supply = (not any(s["MaterialId"] == fg["Id"] for s in ds.rows("Stock"))
                 and not any(w["MaterialId"] == fg["Id"] for w in ds.rows("WorkOrder")))
    ok = no_supply and so["RequestedDate"] < earliest and lead >= 10
    detail = (f"{d.IMPOSSIBLE_ORDER} termini {so['RequestedDate']:%d.%m.%Y}, en kısa üretim {lead} iş günü "
              f"→ en erken {earliest:%d.%m.%Y}; stok ve iş emri yok")
    return Check(4, "İmkânsız termin", ok, detail)


def check_downtime_and_absence(ds: Dataset) -> Check:
    res = ds.get("Resource", Code=d.MAINTENANCE_RESOURCE)
    downs = [r for r in ds.rows("ResourceDowntime") if r["ResourceId"] == res["Id"] and r["DowntimeType"] == "Bakım"]
    working = {r["Date"] for r in ds.rows("CalendarDay") if r["IsWorkingDay"]}
    down_ok = any(ds.start <= r["StartAt"].date() <= ds.horizon_end and r["StartAt"].date() in working for r in downs)
    absences = {ds.code("Worker", a["WorkerId"]): a for a in ds.rows("WorkerAbsence")}
    abs_ok = (absences.get(d.LEAVE_WORKER, {}).get("AbsenceType") == "İzin"
              and absences.get(d.SICK_WORKER, {}).get("AbsenceType") == "Rapor")
    detail = (f"{d.MAINTENANCE_RESOURCE} bakım {downs[0]['StartAt']:%d.%m}–"
              f"{downs[0]['EndAt'] - timedelta(seconds=1):%d.%m}; "
              f"{d.LEAVE_WORKER} izin, {d.SICK_WORKER} rapor") if downs else "bakım kaydı yok"
    return Check(5, "Bakım duruşu ve izin", down_ok and abs_ok, detail)


def all_checks(ds: Dataset) -> list[Check]:
    return [check_bottleneck(ds), check_late_material(ds), check_supplier_limit(ds), check_impossible_due(ds),
            check_downtime_and_absence(ds)]


def summary(ds: Dataset) -> dict:
    firm = open_firm_orders(ds)
    return {
        "Malzeme": len(ds.rows("Material")), "Kaynak": len(ds.rows("Resource")),
        "Açık kesin sipariş": len(firm), "Teklif": len(ds.rows("SalesOrderLine")) - len(firm),
        "Müşteri": len(ds.rows("Customer")), "Tedarikçi": len(ds.rows("Supplier")),
        "Çalışan": len(ds.rows("Worker")), "Ufuk (hafta)": d.HORIZON_WEEKS,
        "Hafta 1": f"{ds.start:%d.%m.%Y}", "Ufuk sonu": f"{ds.horizon_end:%d.%m.%Y}",
    }


