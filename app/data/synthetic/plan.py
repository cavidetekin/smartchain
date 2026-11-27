"""Plan fikstürü (K-205, geliştirme 8.0): sentetik veri için basit kuralla üretilmiş, dondurulmuş üç plan.

Ürünün planlama mantığına girmez; amaç doğru plan değil, tutarlı ve dolu bir plan. Kural bilerek basittir: talepten geriye, ağacı patlatarak,
kapasite sınırı olmadan; optimizasyon yok. 12 durum plan parametresinde açıkça listelenir (`PLANS`).

Üretim (`generate`): bellekte `dataset.generate(on)`; veritabanı okunmaz. Zaman sentetik verinin haftalarıyla (hafta 1 = üretim gününün Pazartesi'si)
tutulur; kayıtlar kodla (iş anahtarı) tutulur, Id ve tarih tutulmaz. Böylece dosya üretim gününden bağımsızdır (`plan_fixture.json`, repoda).

Yükleme (`load_plans`): kodlar güncel veri versiyonunda Id'ye, haftalar senaryonun plan dönemlerine çevrilir; karar satırları yazıcıyla yazılır,
hareketler ve yükler ürünün türetmesiyle (`app.planning.derive`) kurulur, pegging hareketlere eşlenir; uyarı ve metrik yazılır; tutarlılık denetimleri
(`app.planning.checks`) koşar, hata varsa hiçbir şey kalmaz.

Komutlar: `python -m app.data.synthetic plan` (yükler) · `plan --regenerate` (yalnız dosyayı yazar) · `plan --summary` (özet ve 12 durumun kanıtı).
"""
import copy
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import capacity as cap_ref
from . import dataset as d

FIXTURE = Path(__file__).with_name("plan_fixture.json")
SOLVER = "Fikstür"          # fikstür plan hesapları bununla tanınır (PlanRun.Solver)
ENGINE = "Kısıtsız MRP"
FIRST_OVERTIME_WEEK = 2     # ilk hafta kısa dönem olabilir: ek mesai yazılmaz
PRODUCTION, PURCHASE = "Üretim", "Satın alma"
PLAN_SRC, ORDER_SRC = "Plan", "Sipariş"
EPS = 1e-6


@dataclass(frozen=True)
class PlanSpec:
    """Bir planın parametreleri (K-205 S-6: durumlar açıkça listelenir; kural basit kalır)."""
    name: str
    scenario: str                               # "Baz" ya da sentetik senaryonun adı
    night: int = 0                              # gece kayması (gün): 0 bugün, -1 dün
    use_overtime: bool = True
    overtime: dict = field(default_factory=dict)  # kaynak grubu → günlük ek mesai limiti (senaryonun farkı); boşsa Baz girişleri
    late: dict = field(default_factory=dict)    # sipariş no → ((pay, kaç hafta geç), …)
    unmet: tuple = ()                           # karşılanmayan siparişler
    fixed: tuple = ()                           # malzeme kodu: ilk üretim planı kaydı sabitlenir
    manual: dict = field(default_factory=dict)  # malzeme kodu → (miktar çarpanı, kaç hafta öne): ilk üretim planı kaydı elle değiştirilir
    alternative: dict = field(default_factory=dict)  # malzeme kodu → üretim versiyonu kodu
    split: dict = field(default_factory=dict)   # üretim siparişi no → payları (ardışık haftalar)
    early: dict = field(default_factory=dict)   # malzeme kodu → satın alma planı kayıtları kaç hafta öne
    bump: dict = field(default_factory=dict)    # malzeme kodu → üretim planı miktar çarpanı


ISL5_LATE = {"SO-1012": ((0.5, 0), (0.5, 1)), "SO-1014": ((0.5, 0), (0.5, 1))}
PLANS = (
    PlanSpec("Baz · güncel", "Baz",
             late={d.LATE_ORDER: ((0.6, 0), (0.4, 1)), **ISL5_LATE}, unmet=(d.IMPOSSIBLE_ORDER,),
             fixed=("ALT-001",), manual={"ALT-002": (1.2, 1)}, alternative={d.ALTERNATIVE_PARENT: "V2"}, split={"WO-5012": (0.5, 0.5)}),
    PlanSpec("Baz · önceki gece", "Baz", night=-1,
             late={d.LATE_ORDER: ((0.6, 0), (0.4, 1)), **ISL5_LATE}, unmet=(d.IMPOSSIBLE_ORDER,),
             alternative={d.ALTERNATIVE_PARENT: "V2"}, split={"WO-5012": (0.5, 0.5)}, early={"HAM-001": 1, "HAM-002": 1}, bump={"ALT-003": 1.1, "ALT-004": 1.1}),
    PlanSpec("Fazla mesaili", "Fazla mesaili", overtime=dict(getattr(d, "OVERTIME_DIFFS", {})),
             late={d.LATE_ORDER: ((0.6, 0), (0.4, 1)), "SO-1014": ((0.75, 0), (0.25, 1))}, unmet=(d.IMPOSSIBLE_ORDER,),
             alternative={d.ALTERNATIVE_PARENT: "V2"}, split={"WO-5012": (0.5, 0.5)}),
)
BY_NAME = {p.name: p for p in PLANS}


# ====================================================================================================================== üretim (bellekte)

class _World:
    """Sentetik verinin plana gereken görünümü (bellekte)."""

    def __init__(self, ds: d.Dataset):
        self.ds = ds
        self.mat = {m["Id"]: m for m in ds.rows("Material")}
        self.code = {m["Id"]: m["Code"] for m in ds.rows("Material")}
        self.by_code = {m["Code"]: m["Id"] for m in ds.rows("Material")}
        self.pv = defaultdict(list)
        for v in ds.rows("ProductionVersion"):
            if v.get("IsActive", True):
                self.pv[v["MaterialId"]].append(v)
        for vs in self.pv.values():
            vs.sort(key=lambda v: (v.get("Priority") or 99, v["Id"]))
        self.bom = defaultdict(list)
        for b in ds.rows("BOM"):
            self.bom[b["Code"]].append(b)
        self.route = defaultdict(list)
        for r in ds.rows("Routing"):
            if r.get("IsActive", True):
                self.route[r["RouteCode"]].append(r)
        self.group = {g["Id"]: g for g in ds.rows("ResourceGroup")}
        self.supplier = {s["Id"]: s for s in ds.rows("Supplier")}
        self.ms = defaultdict(list)
        for s in ds.rows("MaterialSupplier"):
            if s.get("IsActive", True):
                self.ms[s["MaterialId"]].append(s)
        for xs in self.ms.values():
            xs.sort(key=lambda s: (s.get("Priority") or 99, s["Id"]))
        self.reference = {r["MaterialId"]: r for r in ds.rows("MaterialReference")}
        self.project = {p["Id"]: p["Code"] for p in ds.rows("Project")}
        self.customer = {c["Id"]: c["Code"] for c in ds.rows("Customer")}
        self.wo = {w["Id"]: w for w in ds.rows("WorkOrder")}

    def week(self, day: date | None) -> int:
        return max(1, self.ds.week_of(day)) if day else 1

    def version(self, mid: int, code: str | None = None) -> dict | None:
        """Varsayılan (ya da istenen) üretim versiyonu; kendi versiyonu yoksa benzetilen ürünün versiyonu."""
        vs = self.pv.get(mid)
        if not vs and mid in self.reference:
            ref = self.reference[mid]
            vs = [v for v in self.pv.get(ref["ReferenceMaterialId"], []) if ref.get("ReferenceProductionVersionId") in (None, v["Id"])]
        if not vs:
            return None
        return next((v for v in vs if v["Code"] == code), vs[0]) if code else vs[0]

    def phantom(self, mid: int) -> bool:
        return bool(self.mat[mid].get("IsPhantom"))

    def lines(self, bom_code: str) -> list[dict]:
        """Ağaç satırları: miktarı 0 olan atılır; alternatif grupta en öncelikli."""
        rows = [b for b in self.bom.get(bom_code, []) if (b.get("Quantity") or 0) > 0]
        best = {}
        for b in rows:
            g = b.get("AlternativeGroup")
            if g is not None:
                best[g] = min(best.get(g, 99), b.get("AlternativePriority") or 99)
        return [b for b in rows if b.get("AlternativeGroup") is None or (b.get("AlternativePriority") or 99) == best[b["AlternativeGroup"]]]

    def explode(self, version: dict, qty: float, depth: int = 0) -> dict[int, float]:
        """Bir üretim kaydının bileşen ihtiyacı (türetmeyle aynı kural): miktar × satır ÷ temel miktar × (1 + fire); parti bazlı satır bir kez;
        hayalet bileşen varsayılan versiyonuyla patlatılır."""
        out: dict[int, float] = defaultdict(float)
        base = float(version.get("BaseQuantity") or 1)
        for b in self.lines(version["BOMCode"]):
            q = float(b["Quantity"]) if b.get("IsLotBasedUsage") else qty * float(b["Quantity"]) / base
            q *= 1 + float(b.get("ScrapRatio") or 0)
            c = b["ComponentMaterialId"]
            if (b.get("IsPhantom") or self.phantom(c)) and depth < 5:
                v = self.version(c)
                if v:
                    for k, x in self.explode(v, q, depth + 1).items():
                        out[k] += x
                continue
            out[c] += q
        return dict(out)

    def edges(self) -> dict[int, set[int]]:
        """Ağaç kenarları (alokasyon kuralı ve seviye için): bütün aktif versiyonlar ve alternatifler, benzetilen ürün, üretim siparişi bileşenleri."""
        out: dict[int, set[int]] = defaultdict(set)
        for mid, vs in self.pv.items():
            for v in vs:
                for b in self.bom.get(v["BOMCode"], []):
                    out[mid].add(b["ComponentMaterialId"])
        for mid in self.reference:
            if not self.pv.get(mid):
                v = self.version(mid)
                if v:
                    out[mid] |= {b["ComponentMaterialId"] for b in self.bom.get(v["BOMCode"], [])}
        for c in self.ds.rows("WorkOrderComponent"):
            if self.wo[c["WorkOrderId"]]["OpenQuantity"] > 0:
                out[self.wo[c["WorkOrderId"]]["MaterialId"]].add(c["MaterialId"])
        return {k: {c for c in v if c != k} for k, v in out.items()}


def supply_key(world: _World, row: dict) -> tuple[str, str] | None:
    """Arz satırının alokasyon anahtarı (`app/allocation.expressions` ile aynı kural)."""
    if not world.mat[row["MaterialId"]].get("IsCustomAllocated"):
        return None
    order, line, item = row.get("SalesOrderNo"), row.get("SalesOrderLineNo"), row.get("SalesOrderLineItemNo")
    if order and line is not None:
        return ("Sipariş", f"{order}|{line}|{item or 0}")
    if order:
        return ("Sipariş", order)
    if row.get("ProjectCode"):
        return ("Proje", row["ProjectCode"])
    if row.get("CustomerCode"):
        return ("Müşteri", row["CustomerCode"])
    return None


def allocation_rules(world: _World) -> set[tuple[int, str, str]]:
    """`core.MaterialAllocationRule`'un bellekteki karşılığı (K-199): (malzeme, seviye, anahtar) ⇔ o anahtara uyan bir talebin malzemesinden o anahtarlı
    açık arzın malzemesine inen yolun üzerinde (uçlar dahil). Hayalet malzemeye satır açılmaz. Testte veritabanındaki kuralla karşılaştırılır."""
    ds = world.ds
    edges = world.edges()
    parents: dict[int, set[int]] = defaultdict(set)
    for p, cs in edges.items():
        for c in cs:
            parents[c].add(p)
    supply: dict[tuple[str, str], set[int]] = defaultdict(set)
    for table, qty in (("Stock", "Quantity"), ("WorkOrder", "OpenQuantity"), ("PurchaseOrderLine", "OpenQuantity")):
        for r in ds.rows(table):
            if (r.get(qty) or 0) > 0 and r.get("IsActive", True):
                k = supply_key(world, r)
                if k:
                    supply[k].add(r["MaterialId"])
    demand: dict[tuple[str, str], set[int]] = defaultdict(set)
    for s in ds.rows("SalesOrderLine"):
        if (s.get("OpenQuantity") or 0) > 0 and s.get("IsActive", True):
            demand[("Sipariş", f"{s['OrderNo']}|{s['LineNo']}|{s.get('LineItemNo') or 0}")].add(s["MaterialId"])
            demand[("Sipariş", s["OrderNo"])].add(s["MaterialId"])
            if s.get("ProjectId"):
                demand[("Proje", world.project[s["ProjectId"]])].add(s["MaterialId"])
            demand[("Müşteri", world.customer[s["CustomerId"]])].add(s["MaterialId"])
    for f in ds.rows("Forecast"):
        if (f.get("Quantity") or 0) > 0 and f.get("IsActive", True):
            if f.get("ProjectId"):
                demand[("Proje", world.project[f["ProjectId"]])].add(f["MaterialId"])
            if f.get("CustomerId"):
                demand[("Müşteri", world.customer[f["CustomerId"]])].add(f["MaterialId"])
    out = set()
    for key, mats in supply.items():
        if key not in demand:
            continue
        up, todo = set(mats), list(mats)
        while todo:
            m = todo.pop()
            for p in parents.get(m, ()):
                if p not in up:
                    up.add(p)
                    todo.append(p)
        down, todo = {m for m in demand[key] if m in up}, [m for m in demand[key] if m in up]
        while todo:
            m = todo.pop()
            for c in edges.get(m, ()):
                if c in up and c not in down:
                    down.add(c)
                    todo.append(c)
        out |= {(m, key[0], key[1]) for m in down if not world.phantom(m)}
    return out


@dataclass
class _Supply:
    """Netlemedeki arz olayı."""
    week: int
    qty: float
    spec: dict                       # hareketin eşleme anahtarı (pegging)
    record: dict | None = None       # tedarik planı kaydı (Plan ya da Sipariş)
    transfer: list | None = None     # alokasyon transferinden gelen arz: genel arzdan eşleşmeler [(_Supply, miktar)]
    portions: list = field(default_factory=list)   # pegging: bu arzı tüketen bağlar [(bağ, miktar)]
    used: float = 0.0


@dataclass
class _Need:
    week: int
    qty: float
    spec: dict
    root: str | None = None          # kök talebin anahtarı (talepte kendisi)
    parent: _Supply | None = None    # üretim ihtiyacında ihtiyacı doğuran üretim
    matches: list = field(default_factory=list)    # [(_Supply, miktar)]


class _Generator:
    def __init__(self, ds: d.Dataset, spec: PlanSpec):
        self.ds, self.spec, self.w = ds, spec, _World(ds)
        self.rules = allocation_rules(self.w)
        self.keys_of = defaultdict(set)
        for m, lvl, k in self.rules:
            self.keys_of[m].add((lvl, k))
        self.supplies: dict[tuple, list[_Supply]] = defaultdict(list)    # (malzeme, anahtar) → arzlar
        self.needs: dict[tuple, list[_Need]] = defaultdict(list)
        self.records: list[dict] = []
        self.transfers: list[dict] = []
        self.fulfillment: list[dict] = []
        self.seq = 0
        self.fixed_done, self.manual_done = set(), set()

    # --- girdi ----------------------------------------------------------------------------------------------------------------------------
    def rule_key(self, mid: int, candidates) -> tuple[str, str] | None:
        return next((k for k in candidates if k and k in self.keys_of.get(mid, ())), None)

    def demands(self) -> None:
        w = self.w
        for s in self.ds.rows("SalesOrderLine"):
            if s.get("IsQuote") or s.get("IsOnHold") or not s.get("IsActive", True) or (s.get("OpenQuantity") or 0) <= 0:
                continue   # Teklif ve Beklemedeki sipariş Baz'da plana dahil değil (parametre); karşılanmaz
            if s["OrderNo"] in self.spec.unmet:
                continue
            key = self.rule_key(s["MaterialId"], [("Sipariş", f"{s['OrderNo']}|{s['LineNo']}|{s.get('LineItemNo') or 0}"),
                                                  ("Proje", w.project.get(s.get("ProjectId"))) if s.get("ProjectId") else None,
                                                  ("Müşteri", w.customer.get(s["CustomerId"]))])
            due = w.week(s.get("ConfirmedDate") or s["RequestedDate"])
            self._demand(s["MaterialId"], key, due, float(s["OpenQuantity"]), s["BusinessKey"], "SalesOrderLine", s.get("OrderNo"))
        for f in self.ds.rows("Forecast"):
            if not f.get("IsActive", True) or (f.get("Quantity") or 0) <= 0:
                continue
            key = self.rule_key(f["MaterialId"], [("Proje", w.project.get(f.get("ProjectId"))) if f.get("ProjectId") else None,
                                                  ("Müşteri", w.customer.get(f.get("CustomerId"))) if f.get("CustomerId") else None])
            self._demand(f["MaterialId"], key, w.week(f["Period"]), float(f["Quantity"]), f["BusinessKey"], "Forecast", None)

    def _demand(self, mid, key, due, qty, bk, table, order_no) -> None:
        parts = self.spec.late.get(order_no, ((1.0, 0),))
        for share, late in parts:
            self.seq += 1
            ref = f"F{self.seq}"
            self.fulfillment.append({"ref": ref, "demand": [table, bk], "week": due + late, "Quantity": round(qty * share, 4)})
            self.needs[(mid, key)].append(_Need(due + late, qty * share, {"fulfillment": ref}, root=bk))

    def existing(self) -> None:
        """Stok, açık satın alma siparişi ve açık üretim siparişi (plan kaydı Kaynak = Sipariş)."""
        w = self.w
        for s in self.ds.rows("Stock"):
            if not s.get("IsActive", True) or s.get("IsBlocked") or (s.get("Quantity") or 0) <= 0:
                continue
            kind = "Kalitedeki stok" if s.get("IsInQuality") else "Stok"
            self.supplies[(s["MaterialId"], supply_key(w, s))].append(_Supply(1, float(s["Quantity"]), {"type": kind, "stock": s["BusinessKey"]}))
        for o in self.ds.rows("PurchaseOrderLine"):
            if not o.get("IsActive", True) or (o.get("OpenQuantity") or 0) <= 0 or (o.get("IsSubcontract") and o.get("WorkOrderId")):
                continue
            day = o.get("ConfirmedDate") or o.get("RequestedDate")
            self.supplies[(o["MaterialId"], supply_key(w, o))].append(
                _Supply(w.week(day), float(o["OpenQuantity"]), {"type": "Satın alma siparişi", "po": o["BusinessKey"]}))
        for wo in self.ds.rows("WorkOrder"):
            if (wo.get("OpenQuantity") or 0) <= 0:
                continue
            shares = self.spec.split.get(wo["WorkOrderNo"], (1.0,))
            due = w.week(wo.get("DueDate"))
            v = next((x for vs in w.pv.values() for x in vs if x["Id"] == wo.get("ProductionVersionId")), None)
            for i, share in enumerate(shares):
                rec = self._record(PRODUCTION, ORDER_SRC, wo["MaterialId"], due + i, float(wo["OpenQuantity"]) * share, supply_key(w, wo), v,
                                   work_order=wo["WorkOrderNo"], subcontract=bool(wo.get("IsSubcontract")), share=share, wo_id=wo["Id"])
                rec["SupplyNo"] = wo["WorkOrderNo"]
                self.supplies[(wo["MaterialId"], supply_key(w, wo))].append(_Supply(due + i, rec["Quantity"], {"type": "Üretim siparişi", "supply": rec["ref"]}, rec))

    # --- kayıtlar --------------------------------------------------------------------------------------------------------------------------
    def _record(self, kind, source, mid, week, qty, key, version=None, **extra) -> dict:
        self.seq += 1
        rec = {"ref": f"S{self.seq}", "SupplyType": kind, "Source": source, "material": self.w.code[mid], "week": week, "Quantity": round(qty, 4),
               "RoundedQuantity": round(qty, 4), "ProposedQuantity": round(qty, 4), "proposed_week": week, "IsManual": False, "IsFixed": False,
               "IsSubcontract": bool(extra.pop("subcontract", False)), "alloc": list(key) if key else None, "work_order": extra.pop("work_order", None),
               "version": version["Code"] if version else None, "version_material": self.w.code[version["MaterialId"]] if version else None,
               "BOMCode": version["BOMCode"] if version else None, "RouteCode": version["RouteCode"] if version else None, "supplier": None, "lead_days": None}
        rec["_share"], rec["_wo"], rec["_mid"], rec["_v"] = extra.pop("share", 1.0), extra.pop("wo_id", None), mid, version
        self.records.append(rec)
        return rec

    def _new_supply(self, mid, key, week, qty) -> _Supply:
        """Net ihtiyaç için tedarik planı kaydı: üretim (versiyon, fason) ya da satın alma (yuvarlama, tedarikçi, sipariş tarihi)."""
        w, spec = self.w, self.spec
        m = w.mat[mid]
        code = m["Code"]
        produce = bool(w.version(mid)) and (m.get("DefaultSupplyType") in ("Üretim", "Fason") or not m.get("IsPurchasable"))
        if produce:
            v = w.version(mid, spec.alternative.get(code))
            qty *= spec.bump.get(code, 1.0)
            rec = self._record(PRODUCTION, PLAN_SRC, mid, week, qty, key, v)
            sub = [r for r in w.route.get(v["RouteCode"], []) if r.get("IsSubcontracted") or w.group.get(r["ResourceGroupId"], {}).get("IsSubcontractor")]
            if sub:
                g = w.group[sub[0]["ResourceGroupId"]]
                rec["IsSubcontract"] = True
                rec["supplier"] = w.supplier[g["SubcontractorId"]]["Code"] if g.get("SubcontractorId") else None
                ms = next((s for s in w.ms.get(mid, []) if g.get("SubcontractorId") == s["SupplierId"]), None)
                rec["lead_days"] = int(ms["FixedLeadTimeDays"]) if ms and ms.get("FixedLeadTimeDays") is not None else 7
            if code in spec.fixed and code not in self.fixed_done:
                rec["IsFixed"] = True
                self.fixed_done.add(code)
            if code in spec.manual and code not in self.manual_done:
                factor, earlier = spec.manual[code]
                rec["IsManual"] = True
                rec["Quantity"] = rec["RoundedQuantity"] = round(rec["Quantity"] * factor, 4)
                rec["week"] = max(1, rec["week"] - earlier)
                self.manual_done.add(code)
            kind = "Üretim planı"
        else:
            week = max(1, week - spec.early.get(code, 0))
            ms = (w.ms.get(mid) or [None])[0]
            rounded = qty
            if ms:
                if ms.get("MinimumOrderQuantity"):
                    rounded = max(rounded, float(ms["MinimumOrderQuantity"]))
                if ms.get("OrderLotSize"):
                    lot = float(ms["OrderLotSize"])
                    rounded = math.ceil(rounded / lot - EPS) * lot
            rec = self._record(PURCHASE, PLAN_SRC, mid, week, qty, key)
            rec["RoundedQuantity"] = round(rounded, 4)
            if ms:
                rec["supplier"] = w.supplier[ms["SupplierId"]]["Code"]
                if ms.get("FixedLeadTimeDays") is not None or ms.get("VariableLeadTimeDays") is not None:
                    rec["lead_days"] = int(round(float(ms.get("FixedLeadTimeDays") or 0) + qty * float(ms.get("VariableLeadTimeDays") or 0)))
            kind = "Satın alma planı"
        amount = rec["RoundedQuantity"] if kind == "Satın alma planı" else rec["Quantity"]
        s = _Supply(rec["week"], amount, {"type": kind, "supply": rec["ref"]}, rec)
        self.supplies[(mid, key)].append(s)
        return s

    # --- netleme ---------------------------------------------------------------------------------------------------------------------------
    def levels(self) -> list[int]:
        """Malzemeler düşük seviye koduyla (talepten hammaddeye): ebeveyn çocuktan önce."""
        edges = self.w.edges()
        llc = {m: 0 for m in self.w.mat}
        changed = True
        while changed:
            changed = False
            for p, cs in edges.items():
                for c in cs:
                    if llc[c] < llc[p] + 1 and llc[p] < 60:
                        llc[c] = llc[p] + 1
                        changed = True
        return sorted(self.w.mat, key=lambda m: (llc[m], self.w.code[m]))

    @staticmethod
    def _order(s: _Supply) -> tuple:
        rank = {"Stok": 0, "Kalitedeki stok": 1, "Satın alma siparişi": 2, "Üretim siparişi": 3}.get(s.spec.get("type"), 4)
        return (s.week, rank)

    def _consume(self, need: _Need, supplies: list[_Supply], upto: float) -> float:
        """İhtiyacı arzlardan (hafta ve tür sırasıyla) karşılar; karşılanan miktar."""
        got = 0.0
        for s in sorted(supplies, key=self._order):
            if s.week > need.week or got >= upto - EPS:
                continue
            free = s.qty - s.used
            if free <= EPS:
                continue
            take = min(free, upto - got)
            s.used += take
            need.matches.append((s, take))
            got += take
        return got

    def _free_existing(self, supplies: list[_Supply], needs: list[_Need]) -> dict[int, float]:
        """Genel arzın serbest kısmı (yalnız mevcut arz: stok, satın alma ve üretim siparişi): hafta → o haftadan ileriye hiçbir ihtiyacı eksiğe
        düşürmeden alınabilecek miktar."""
        weeks = sorted({s.week for s in supplies} | {n.week for n in needs} | {1})
        existing = [s for s in supplies if s.record is None or s.record["Source"] == ORDER_SRC]
        cum, out, level = 0.0, {}, []
        for wk in weeks:
            cum += sum(s.qty for s in existing if s.week == wk) - sum(n.qty for n in needs if n.week == wk)
            level.append((wk, cum))
        for i, (wk, _) in enumerate(level):
            out[wk] = max(0.0, min(c for _, c in level[i:]))
        return out

    def net(self, mid: int) -> None:
        """Malzemenin netlemesi, hafta hafta: önce özel anahtarlar (eksik genel serbest arzdan transferle, kalan anahtarlı kayıtla), sonra genel
        (transfer ihtiyaçları dahil). Bir haftanın eksiği tek kayıtta toplanır."""
        keyed = sorted({k for (m, k) in list(self.needs) + list(self.supplies) if m == mid and k is not None})
        general_needs = self.needs[(mid, None)]
        free = self._free_existing(self.supplies[(mid, None)], general_needs)
        taken = 0.0
        for key in keyed:
            supplies = self.supplies[(mid, key)]
            for week in sorted({n.week for n in self.needs[(mid, key)]}):
                needs = [n for n in self.needs[(mid, key)] if n.week == week]
                short = {id(n): n.qty - self._consume(n, supplies, n.qty) for n in needs}
                total = sum(v for v in short.values() if v > EPS)
                if total <= EPS:
                    continue
                later = [v for wk, v in free.items() if wk >= week]
                avail = max(0.0, (min(later) if later else (free[max(free)] if free else 0.0)) - taken)
                move = min(total, avail)
                if move > EPS:   # genel arzdan transfer: genelden − (genel netlemede ihtiyaç), özele +
                    taken += move
                    self.transfers.append({"material": self.w.code[mid], "week": week, "level": key[0], "key": key[1], "Quantity": round(move, 4),
                                           "Uom": self.w.mat[mid]["BaseUom"]})
                    out_need = _Need(week, move, {"transfer": len(self.transfers) - 1})
                    general_needs.append(out_need)
                    supplies.append(_Supply(week, move, {"transfer": len(self.transfers) - 1}, transfer=out_need.matches))
                if total - move > EPS:
                    self._new_supply(mid, key, week, total - move)
                for n in needs:
                    if short[id(n)] > EPS:
                        self._consume(n, supplies, short[id(n)])
        supplies = self.supplies[(mid, None)]
        for week in sorted({n.week for n in general_needs}):
            needs = sorted([n for n in general_needs if n.week == week], key=lambda n: 0 if "transfer" in n.spec else 1)
            short = {id(n): n.qty - self._consume(n, supplies, n.qty) for n in needs}
            total = sum(v for v in short.values() if v > EPS)
            if total > EPS:
                self._new_supply(mid, None, week, total)
                for n in needs:
                    if short[id(n)] > EPS:
                        self._consume(n, supplies, short[id(n)])
        self._explode(mid)

    def _explode(self, mid: int) -> None:
        """Üretim kayıtlarının bileşen ihtiyacı (plan kaydında ağaç, sipariş kaydında siparişin kendi bileşenleri)."""
        w = self.w
        for (m, key), supplies in list(self.supplies.items()):
            if m != mid:
                continue
            for s in supplies:
                rec = s.record
                if rec is None or rec["SupplyType"] != PRODUCTION:
                    continue
                if rec["Source"] == PLAN_SRC:
                    needs = rec["_v"] and w.explode(rec["_v"], rec["Quantity"]) or {}
                    kind = "Üretim planı ihtiyacı"
                else:
                    needs = defaultdict(float)
                    for c in self.ds.rows("WorkOrderComponent"):
                        if c["WorkOrderId"] == rec["_wo"]:
                            remaining = c.get("RemainingQuantity")
                            if remaining is None:
                                remaining = float(c.get("RequiredQuantity") or 0) - float(c.get("IssuedQuantity") or 0)
                            if remaining > 0:
                                needs[c["MaterialId"]] += float(remaining) * rec["_share"]
                    kind = "Üretim siparişi ihtiyacı"
                for c, q in needs.items():
                    if q <= EPS:
                        continue
                    ckey = key if key and (c, key[0], key[1]) in self.rules else None
                    self.needs[(c, ckey)].append(_Need(rec["week"], q, {"type": kind, "supply": rec["ref"], "material": w.code[c]}, parent=s))

    # --- pegging ---------------------------------------------------------------------------------------------------------------------------
    def pegging(self, order: list[int]) -> list[dict]:
        """Basit kural (K-205): ihtiyaç hareketi dönem sırasıyla arz hareketlerine bağlanır (netlemenin eşleşmeleri); özel alokasyona uyulur;
        transferden gelen arz yerine transferi besleyen gerçek genel arz yazılır, Genelden = Evet (K-202). Seviye ve üst bağ ağaçtan."""
        rows: list[dict] = []

        def emit(need: _Need, supply: _Supply, qty: float, parent: dict | None, general: bool) -> None:
            if qty <= EPS:
                return
            if supply.transfer is not None:   # gerçek arz: transferi besleyen genel arzlar, oranla
                total = sum(q for _, q in supply.transfer) or 1.0
                for real, q in supply.transfer:
                    emit(need, real, qty * q / total, parent, True)
                return
            row = {"ref": f"G{len(rows) + 1}", "supply": supply.spec, "demand": need.spec, "parent": parent["ref"] if parent else None,
                   "root": parent["root"] if parent else need.root, "Quantity": round(qty, 4), "Level": parent["Level"] + 1 if parent else 0,
                   "consuming": self.w.code[need.parent.record["_mid"]] if need.parent else None, "IsFromGeneral": general}
            rows.append(row)
            supply.portions.append((row, qty))

        for mid in order:
            for (m, key), needs in self.needs.items():
                if m != mid:
                    continue
                for need in needs:
                    if "transfer" in need.spec:
                        continue
                    if need.parent is None:
                        for s, q in need.matches:
                            emit(need, s, q, None, False)
                        continue
                    out_qty = need.parent.qty or 1.0
                    for prow, pq in list(need.parent.portions):
                        f = pq / out_qty
                        for s, q in need.matches:
                            emit(need, s, q * f, prow, False)
        return rows

    # --- ek mesai --------------------------------------------------------------------------------------------------------------------------
    def overtime(self) -> list[dict]:
        """Grup × hafta yükü (türetmeyle aynı kural) kullanılabilir kapasiteyi aşarsa aşan kısım ek mesai limitine kadar ek mesai olur."""
        if not self.spec.use_overtime:
            return []
        w, ds = self.w, self.ds
        load: dict[tuple[int, int], float] = defaultdict(float)
        for rec in self.records:
            if rec["SupplyType"] != PRODUCTION:
                continue
            if rec["Source"] == PLAN_SRC and rec["_v"]:
                base = float(rec["_v"].get("BaseQuantity") or 1)
                for r in w.route.get(rec["RouteCode"], []):
                    if not r.get("IsLotBasedUsage") and r.get("ResourceGroupId") and (r.get("Consumption") or 0) > 0:
                        load[(r["ResourceGroupId"], rec["week"])] += rec["Quantity"] * float(r["Consumption"]) / base
            elif rec["Source"] == ORDER_SRC:
                for o in ds.rows("WorkOrderOperation"):
                    if o["WorkOrderId"] == rec["_wo"] and not o.get("IsCompleted") and o.get("IsActive", True) and not o.get("IsLotBasedUsage"):
                        rem = o.get("RemainingConsumption")
                        rem = float(rem) if rem is not None else float(o.get("PlannedConsumption") or 0) - float(o.get("ConfirmedConsumption") or 0)
                        if rem > 0 and o.get("ResourceGroupId"):
                            load[(o["ResourceGroupId"], rec["week"])] += rem * rec["_share"]
        params = copy.copy(ds.params)
        if self.spec.overtime:
            rows = []
            for row in ds.params.get("OvertimeLimit", []):
                g = w.group.get(row.get("ResourceGroupId"), {}).get("Code")
                rows.append({**row, "DailyLimit": self.spec.overtime.get(g, row["DailyLimit"])})
            have = {w.group[r["ResourceGroupId"]]["Code"] for r in rows if r.get("ResourceGroupId")}
            for g, limit in self.spec.overtime.items():
                if g not in have:
                    rows.append({"ScenarioDefinitionId": 1, "ResourceGroupId": next(x["Id"] for x in w.group.values() if x["Code"] == g), "ResourceId": None,
                                 "ValidFrom": ds.start, "ValidTo": None, "DailyLimit": limit, "IsValid": True})
            params["OvertimeLimit"] = rows
        view = copy.copy(ds)
        view.params = params
        days = cap_ref.daily(view, ds.start, ds.start + timedelta(days=7 * d.HORIZON_WEEKS - 1))
        cap: dict[tuple[int, int], list[float]] = defaultdict(lambda: [0.0, 0.0])
        for (g, _r, day), v in days.items():
            c = cap[(g, ds.week_of(day))]
            c[0] += v["AvailableCapacity"]
            c[1] += v["OvertimeLimit"]
        out = []
        for (g, wk), q in sorted(load.items(), key=lambda x: (x[0][1], w.group[x[0][0]]["Code"])):
            available, limit = cap.get((g, wk), (0.0, 0.0))
            over = q - available
            if wk >= FIRST_OVERTIME_WEEK and over > EPS and limit > EPS:
                out.append({"group": w.group[g]["Code"], "week": wk, "Overtime": math.floor(min(over, limit) * 100) / 100, "CapacityUnit": w.group[g]["CapacityUnit"]})
        return out

    # --- bütün plan ------------------------------------------------------------------------------------------------------------------------
    def run(self) -> dict:
        self.demands()
        self.existing()
        order = [m for m in self.levels() if not self.w.phantom(m)]
        for mid in order:
            self.net(mid)
        pegging = self.pegging(order)
        overtime = self.overtime()
        records = [{k: v for k, v in r.items() if not k.startswith("_")} for r in self.records]
        return {"name": self.spec.name, "scenario": self.spec.scenario, "night": self.spec.night, "supply": records, "fulfillment": self.fulfillment,
                "overtime": overtime, "transfers": self.transfers, "pegging": pegging}


def generate(on: date | None = None) -> dict:
    """Üç planın fikstürü (bellekte)."""
    ds = d.generate(on)
    return {"_note": "Plan fikstürü (K-205, geliştirme 8.0). Üretilmiş dosya: python -m app.data.synthetic plan --regenerate. Kayıtlar iş anahtarıyla, zaman "
                     "sentetik verinin haftasıyla (1 = üretim gününün haftası) tutulur; yükleyici güncel veri versiyonuna ve senaryonun dönemlerine çevirir.",
            "seed": ds.seed, "generated_on": ds.generated_on.isoformat(), "plans": [_Generator(ds, spec).run() for spec in PLANS]}


_GENERATED: dict[date, dict] = {}


def fixture_for(on: date) -> dict:
    """Verinin üretim gününe ait fikstür: dosya o güne aitse dosya, değilse aynı betik o gün için bellekte üretir. Sentetik verinin bazı tarihleri
    (tahmin dönemleri, iş günüyle hesaplanan teslimler) üretim gününe göre hafta değiştirir; başka günün planı bakiyeyi bozabilir."""
    if FIXTURE.exists():
        fx = read()
        if fx.get("generated_on") == on.isoformat():
            return fx
    if on not in _GENERATED:
        _GENERATED[on] = generate(on)
    return _GENERATED[on]


def write(path: Path = FIXTURE) -> dict:
    fx = generate()
    path.write_text(json.dumps(fx, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return fx


def read(path: Path = FIXTURE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ====================================================================================================================== yükleme (veritabanı)

class PlanFixtureError(Exception):
    """Fikstür yüklenemedi (sentetik olmayan veri, eşleşmeyen kayıt, tutarlılık denetimi); hiçbir şey yazılmadı."""


def _local_date(at: datetime) -> date:
    from app.flows.schedule import utc_to_local
    return utc_to_local(at).date()


CURRENT = "{a}VersionFrom <= :v AND ({a}VersionTo IS NULL OR {a}VersionTo >= :v)"


class _Resolver:
    """Fikstürün kodlarını ve haftalarını plan hesabının veri versiyonuna ve senaryonun dönemlerine çevirir."""

    def __init__(self, session, data_version_id: int, scenario_id: int, today: date, on: date):
        import sqlalchemy as sa
        from app.periods import periods as period_list
        v = {"v": data_version_id}
        cur = CURRENT.format(a="")

        def pairs(sql):
            return {a: b for a, b in session.execute(sa.text(sql), v)}
        self.material = pairs(f"SELECT Code, Id FROM core.Material WHERE {cur}")
        self.base_uom = pairs(f"SELECT Id, BaseUom FROM core.Material WHERE {cur}")
        self.location = session.execute(sa.text("SELECT Id FROM core.Location WHERE Code = :c"), {"c": d.LOCATION_CODE}).scalar_one()
        self.version = {(m, c): i for i, m, c in session.execute(sa.text(
            "SELECT pv.Id, m.Code, pv.Code FROM core.ProductionVersion pv JOIN core.Material m ON m.Id = pv.MaterialId AND "
            f"{CURRENT.format(a='m.')} WHERE {CURRENT.format(a='pv.')}"), v)}
        self.supplier = pairs(f"SELECT Code, Id FROM core.Supplier WHERE {cur}")
        self.group = pairs(f"SELECT Code, Id FROM core.ResourceGroup WHERE {cur}")
        self.work_order = pairs(f"SELECT WorkOrderNo, Id FROM core.WorkOrder WHERE {cur}")
        self.bk = {t: pairs(f"SELECT BusinessKey, Id FROM core.{t} WHERE {cur}") for t in ("Stock", "PurchaseOrderLine", "SalesOrderLine", "Forecast")}
        self.week1 = d.monday(on)
        self.periods = period_list.read(session, scenario_id, today)
        if not self.periods:
            raise PlanFixtureError("Senaryonun plan dönemleri yok.")

    def period(self, week: int):
        day = self.week1 + timedelta(days=7 * (week - 1))
        found = next((p for p in self.periods if day <= p.end), None)
        if found is None:
            raise PlanFixtureError(f"Hafta {week} ({day}) planlama ufkunun dışında.")
        return found

    @staticmethod
    def need(table: dict, key, what: str):
        if key not in table:
            raise PlanFixtureError(f"Fikstürdeki kayıt veride yok: {what} {key}")
        return table[key]


def _spec(r: _Resolver, spec: dict) -> dict:
    out = {}
    if "type" in spec:
        out["MovementType"] = spec["type"]
    if "stock" in spec:
        out["StockId"] = r.need(r.bk["Stock"], spec["stock"], "stok")
    if "po" in spec:
        out["PurchaseOrderLineId"] = r.need(r.bk["PurchaseOrderLine"], spec["po"], "satın alma satırı")
    if "supply" in spec:
        out["supply_ref"] = spec["supply"]
    if "fulfillment" in spec:
        out["fulfillment_ref"] = spec["fulfillment"]
    if "material" in spec:
        out["MaterialId"] = r.need(r.material, spec["material"], "malzeme")
    return out


def data_day(session, data_version_id: int) -> date:
    """Sentetik verinin üretim günü: veri versiyonunun (yerel) tarihi (yükleme günü)."""
    import sqlalchemy as sa
    return _local_date(session.execute(sa.text("SELECT CreatedAt FROM adm.DataVersion WHERE Id = :v"), {"v": data_version_id}).scalar_one())


def result_for(session, plan_run_id: int, plan: dict, today: date | None = None, on: date | None = None):
    """Fikstürdeki bir planın motor sonucu (`PlanResult`): kodlar Id'ye, haftalar dönemlere çevrilmiş. Talep kopyası önceden kurulmuş olmalı."""
    import sqlalchemy as sa
    from app.engine.interface import PlanResult
    today = today or date.today()
    run = session.execute(sa.text("SELECT DataVersionId, ScenarioDefinitionId FROM planning.PlanRun WHERE Id = :id"), {"id": plan_run_id}).one()
    r = _Resolver(session, run.DataVersionId, run.ScenarioDefinitionId, today, on or data_day(session, run.DataVersionId))
    demand = {}
    for did, so, fc, due in session.execute(sa.text("SELECT Id, SalesOrderLineId, ForecastId, DuePeriodStart FROM planning.PlannedDemand WHERE PlanRunId = :r"),
                                            {"r": plan_run_id}):
        demand[("SalesOrderLine", so) if so is not None else ("Forecast", fc)] = (did, due)
    supply = []
    for s in plan["supply"]:
        p, proposed = r.period(s["week"]), r.period(s["proposed_week"])
        mid = r.need(r.material, s["material"], "malzeme")
        alloc, lead = s.get("alloc"), s.get("lead_days")
        supply.append({
            "ref": s["ref"], "SupplyNo": s.get("SupplyNo"), "SupplyType": s["SupplyType"], "Source": s["Source"],
            "WorkOrderId": r.need(r.work_order, s["work_order"], "üretim siparişi") if s.get("work_order") else None,
            "MaterialId": mid, "LocationId": r.location, "Uom": r.base_uom[mid], "PeriodStart": p.start, "PeriodEnd": p.end,
            "OrderDate": p.start - timedelta(days=lead) if lead is not None and (s["SupplyType"] == PURCHASE or s["IsSubcontract"]) else None,
            "ProductionVersionId": r.need(r.version, (s["version_material"], s["version"]), "üretim versiyonu") if s.get("version") else None,
            "BOMCode": s.get("BOMCode"), "RouteCode": s.get("RouteCode"),
            "SupplierId": r.need(r.supplier, s["supplier"], "tedarikçi") if s.get("supplier") else None, "IsSubcontract": s["IsSubcontract"],
            "IsCustomAllocated": bool(alloc), "AllocationLevel": alloc[0] if alloc else None, "AllocationKey": alloc[1] if alloc else None,
            "Quantity": s["Quantity"], "RoundedQuantity": s["RoundedQuantity"], "ProposedQuantity": s["ProposedQuantity"], "ProposedPeriodStart": proposed.start,
            "IsManual": s["IsManual"], "IsFixed": s["IsFixed"], "IsIncluded": True})
    fulfillment = []
    for f in plan["fulfillment"]:
        table, bk = f["demand"]
        rid = r.need(r.bk[table], bk, "talep")
        did, due = r.need(demand, (table, rid), "plan hesabının talebi")
        p = r.period(f["week"])
        fulfillment.append({"ref": f["ref"], "PlannedDemandId": did, "PeriodStart": p.start, "PeriodEnd": p.end, "Quantity": f["Quantity"],
                            "IsTardy": due is not None and p.start > due})
    overtime = [{"ResourceGroupId": r.need(r.group, o["group"], "kaynak grubu"), "LocationId": r.location, "PeriodStart": r.period(o["week"]).start,
                 "PeriodEnd": r.period(o["week"]).end, "Overtime": o["Overtime"], "CapacityUnit": o["CapacityUnit"]} for o in plan["overtime"]]
    transfers = [{"MaterialId": r.need(r.material, t["material"], "malzeme"), "LocationId": r.location, "PeriodStart": r.period(t["week"]).start,
                  "PeriodEnd": r.period(t["week"]).end, "AllocationLevel": t["level"], "AllocationKey": t["key"], "Quantity": t["Quantity"], "Uom": t["Uom"]}
                 for t in plan["transfers"]]
    roots = {**{bk: ("SalesOrderLine", i) for bk, i in r.bk["SalesOrderLine"].items()}, **{bk: ("Forecast", i) for bk, i in r.bk["Forecast"].items()}}
    pegging = []
    for g in plan["pegging"]:
        root = demand[roots[g["root"]]][0] if g.get("root") in roots and roots[g["root"]] in demand else None
        pegging.append({"ref": g["ref"], "supply": _spec(r, g["supply"]), "demand": _spec(r, g["demand"]), "parent_ref": g.get("parent"),
                        "PlannedDemandId": root, "Quantity": g["Quantity"], "Level": g["Level"],
                        "ConsumingMaterialId": r.need(r.material, g["consuming"], "malzeme") if g.get("consuming") else None, "IsFromGeneral": g["IsFromGeneral"]})
    return PlanResult(engine_used=ENGINE, solver=SOLVER, planned_supply=supply, demand_fulfillment=fulfillment, planned_overtime=overtime,
                      allocation_transfers=transfers, pegging=pegging)


ORDER_TYPES = ("Kesin sipariş", "Teklif", "Beklemedeki sipariş")


def write_warnings_and_metrics(session, plan_run_id: int, today: date | None = None) -> dict:
    """Fikstürün uyarıları ve metrikleri (K-205): çıktılar yazıldıktan sonra plan tablolarından hesaplanır. Önem yazılmaz (ekranda eşikten)."""
    import sqlalchemy as sa
    from app.planning import capacity_view, metrics
    today = today or date.today()
    p = {"run": plan_run_id}
    session.execute(sa.text("DELETE FROM planning.PlanWarning WHERE PlanRunId = :run"), p)
    session.execute(sa.text("DELETE FROM planning.PlanMetric WHERE PlanRunId = :run"), p)
    rows: list[dict] = []

    def add(code, kind, oid, value, message, start=None, end=None, group=None, material=None, demand=None, supply=None):
        """Uyarı satırı: dönem ve ilgili kayıt ayrı alanlarda (K-206); ObjectType ve ObjectId genel bağ."""
        rows.append({"PlanRunId": plan_run_id, "WarningCode": code, "ObjectType": kind, "ObjectId": oid, "Value": value, "Message": message[:400],
                     "PeriodStart": start, "PeriodEnd": end, "ResourceGroupId": group, "MaterialId": material, "PlannedDemandId": demand, "PlannedSupplyId": supply})

    from app.planning import derive
    scenario = session.execute(sa.text("SELECT ScenarioDefinitionId FROM planning.PlanRun WHERE Id = :run"), p).scalar_one()
    ends = {x.start: x.end for x in derive.plan_periods(session, scenario, today)}

    types = ", ".join(f"N'{t}'" for t in ORDER_TYPES)
    for did, oid, no, line, late, unmet, days, due, mat in session.execute(sa.text(
            "SELECT d.Id, d.SalesOrderLineId, d.OrderNo, d.[LineNo], d.LateQuantity, d.UnmetQuantity, DATEDIFF(day, d.DuePeriodStart, d.LastFulfillmentPeriodStart), "
            f"d.DuePeriodStart, d.MaterialId FROM planning.PlannedDemand d WHERE d.PlanRunId = :run AND d.IsIncluded = 1 AND d.DemandType IN ({types}) "
            "AND (d.LateQuantity > 0.001 OR d.UnmetQuantity > 0.001)"), p):
        link = dict(start=due, end=ends.get(due), material=mat, demand=did)
        if late and late > 0.001:
            add("ORDER_LATE", "Sipariş", oid, days or 0, f"Sipariş {no}/{line}: {float(late):g} birim {days or 0} gün geç karşılanıyor.", **link)
        if unmet and unmet > 0.001:
            add("ORDER_UNMET", "Sipariş", oid, float(unmet), f"Sipariş {no}/{line}: {float(unmet):g} birim karşılanamıyor.", **link)
    for did, oid, unmet, due, mat in session.execute(sa.text(
            "SELECT Id, ForecastId, UnmetQuantity, DuePeriodStart, MaterialId FROM planning.PlannedDemand WHERE PlanRunId = :run AND IsIncluded = 1 "
            "AND DemandType = N'Tahmin' AND UnmetQuantity > 0.001"), p):
        add("FORECAST_UNMET", "Tahmin", oid, float(unmet), f"Tahmin {oid}: {float(unmet):g} birim karşılanamıyor.", start=due, end=ends.get(due), material=mat, demand=did)
    for g in capacity_view.group_periods(session, plan_run_id, today):
        when = g["PeriodStart"].strftime("%d.%m.%Y")
        if g["Overload"] > capacity_view.EPS:
            pct = 100 * g["Load"] / g["AvailableCapacity"] if g["AvailableCapacity"] else 0
            add("CAP_OVERLOAD", "Kaynak grubu", g["ResourceGroupId"], round(pct, 2),
                f"{g['Code']}, {when} döneminde %{pct:.1f} dolu; ek mesaiden sonra {g['Overload']:.1f} saat aşım.",
                start=g["PeriodStart"], end=g["PeriodEnd"], group=g["ResourceGroupId"])
        if g["Overtime"] > capacity_view.EPS:
            add("OVERTIME_USE", "Kaynak grubu", g["ResourceGroupId"], round(g["Overtime"], 2), f"{g['Code']}, {when} döneminde {g['Overtime']:.1f} saat ek mesai.",
                start=g["PeriodStart"], end=g["PeriodEnd"], group=g["ResourceGroupId"])
    for sid, no, order_date, rounded, qty, start, end, mat in session.execute(sa.text(
            "SELECT Id, SupplyNo, OrderDate, RoundedQuantity, Quantity, PeriodStart, PeriodEnd, MaterialId FROM planning.PlannedSupply WHERE PlanRunId = :run "
            "AND IsIncluded = 1 AND SupplyType = N'Satın alma' AND Source = N'Plan'"), p):
        link = dict(start=start, end=end, material=mat, supply=sid)
        if order_date is not None and order_date < today:
            days = (today - order_date).days
            add("PURCHASE_LATE", "Tedarik planı", sid, days, f"Satın alma planı {no}: sipariş tarihi {order_date:%d.%m.%Y}, {days} gün geçmiş.", **link)
        if rounded is not None and float(rounded) - float(qty) > 0.001:
            add("MAT_EXCESS", "Tedarik planı", sid, float(rounded) - float(qty),
                f"Satın alma planı {no}: sipariş lotu nedeniyle {float(rounded) - float(qty):g} birim fazla stok.", **link)
    if rows:
        session.execute(sa.text(
            "INSERT INTO planning.PlanWarning (PlanRunId, WarningCode, ObjectType, ObjectId, Value, Message, PeriodStart, PeriodEnd, ResourceGroupId, MaterialId, "
            "PlannedDemandId, PlannedSupplyId, UpdatedAt) VALUES (:PlanRunId, :WarningCode, :ObjectType, :ObjectId, :Value, :Message, :PeriodStart, :PeriodEnd, "
            ":ResourceGroupId, :MaterialId, :PlannedDemandId, :PlannedSupplyId, SYSUTCDATETIME())"), rows)
    values = metrics.compute(session, plan_run_id)
    session.execute(sa.text("INSERT INTO planning.PlanMetric (PlanRunId, MetricCode, Value) VALUES (:r, :c, :v)"),
                    [{"r": plan_run_id, "c": k, "v": v} for k, v in values.items()])
    return {"warnings": len(rows), "metrics": len(values)}


def after_write(today: date | None = None):
    """Yazıcının çıktılardan sonra çağırdığı adım: uyarı, metrik ve tutarlılık denetimi (hata varsa yazım geri alınır)."""
    def hook(session, plan_run_id: int) -> None:
        from app.planning import checks
        write_warnings_and_metrics(session, plan_run_id, today)
        found = checks.problems(session, plan_run_id, today)
        if found:
            raise PlanFixtureError("Tutarlılık denetimi: " + "; ".join(f"{p['check']}: {p['detail']}" for p in found[:8]))
    return hook


def synthetic_version(session) -> int:
    """Fikstürün yükleneceği veri versiyonu: en son sentetik versiyon; sentetik olmayan veri varsa yüklenmez."""
    import sqlalchemy as sa
    from .load import non_synthetic
    found = non_synthetic(session.connection())
    if found:
        raise PlanFixtureError("Veritabanında sentetik olmayan veri var; plan fikstürü yalnız sentetik veride yüklenir: " + ", ".join(found[:5]))
    v = session.execute(sa.text("SELECT MAX(Id) FROM adm.DataVersion WHERE IsSynthetic = 1")).scalar()
    if v is None:
        raise PlanFixtureError("Sentetik veri yok; önce python -m app.data.synthetic load.")
    return v


def fixture_runs(session) -> list[int]:
    import sqlalchemy as sa
    return [r[0] for r in session.execute(sa.text("SELECT Id FROM planning.PlanRun WHERE Solver = :s"), {"s": SOLVER})]


def load_plans(session, today: date | None = None, fixture: dict | None = None, on: date | None = None) -> list[dict]:
    """Üç planı yükler (önceki fikstür planları silinir); tek işlem, commit'i çağıran yapar. Dönen: plan başına plan hesabı ve sayılar."""
    import sqlalchemy as sa
    from app.data.cleanup import delete_runs
    from app.engine.writer import write_outputs
    from app.planning import demand as demand_copy
    today = today or date.today()
    version = synthetic_version(session)
    on = on or data_day(session, version)
    fixture = fixture or fixture_for(on)
    delete_runs(session.connection(), fixture_runs(session))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    out = []
    for plan in fixture["plans"]:
        if plan["scenario"] == "Baz":
            sid = session.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE IsBase = 1")).scalar_one()
        else:
            sid = session.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE Name = :n AND IsSynthetic = 1"), {"n": plan["scenario"]}).scalar_one()
        at = now + timedelta(days=plan["night"])
        scenario = session.execute(sa.text("INSERT INTO planning.Scenario (ScenarioDefinitionId, DataVersionId, CreatedAt, Status) OUTPUT inserted.Id "
                                           "VALUES (:s, :v, :at, N'Bitti')"), {"s": sid, "v": version, "at": at}).scalar_one()
        run = session.execute(sa.text("INSERT INTO planning.PlanRun (ScenarioId, DataVersionId, ScenarioDefinitionId, EngineUsed, Solver, StartedAt, EndedAt, Status) "
                                      "OUTPUT inserted.Id VALUES (:sc, :v, :s, :e, :so, :at, :at, N'Bitti')"),
                              {"sc": scenario, "v": version, "s": sid, "e": ENGINE, "so": SOLVER, "at": at}).scalar_one()
        session.execute(sa.text("UPDATE planning.Scenario SET PlanRunId = :r WHERE Id = :s"), {"r": run, "s": scenario})
        demand_copy.copy(session, run, today)
        result = result_for(session, run, plan, today, on)
        counts = write_outputs(session, run, result, today=today, after=after_write(today))
        out.append({"plan": plan["name"], "plan_run": run, **counts})
    return out


# ====================================================================================================================== özet (demo)

TABLES = ("PlannedDemand", "PlannedSupply", "DemandFulfillment", "PlannedOvertime", "PlannedAllocationTransfer", "MaterialTransaction", "CapacityLoad", "Pegging",
          "PlanWarning", "PlanMetric")


def _table(rows: list, head: list[str]) -> list[str]:
    cells = [[("" if v is None else (f"{v:%d.%m.%Y}" if isinstance(v, date) else (f"{float(v):g}" if hasattr(v, "quantize") or isinstance(v, float) else str(v))))
              for v in r] for r in rows]
    widths = [max([len(h)] + [len(c[i]) for c in cells]) for i, h in enumerate(head)]
    return ["    " + " | ".join(h.ljust(w) for h, w in zip(head, widths))] + ["    " + " | ".join(c.ljust(w) for c, w in zip(row, widths)) for row in cells]


def summary(session, today: date | None = None) -> str:
    """Yüklü fikstür planlarının özeti: plan başına satır sayıları, Baz · güncel'de 12 durumun kanıt satırları, öteki planların farkları, denetimler."""
    import sqlalchemy as sa
    from app.planning import capacity_view, checks
    today = today or date.today()
    runs = session.execute(sa.text(
        "SELECT r.Id, sd.Name, ISNULL(sd.IsBase, 0), sc.CreatedAt FROM planning.PlanRun r JOIN planning.Scenario sc ON sc.Id = r.ScenarioId "
        "JOIN param.ScenarioDefinition sd ON sd.Id = r.ScenarioDefinitionId WHERE r.Solver = :s ORDER BY sc.CreatedAt DESC, r.Id"), {"s": SOLVER}).all()
    if not runs:
        return "Yüklü plan fikstürü yok (python -m app.data.synthetic plan)."
    named = {}
    for rid, scenario, base, created in runs:
        name = ("Baz · güncel" if not any(v[0] == "Baz · güncel" for v in named.values()) else "Baz · önceki gece") if base else scenario
        named[rid] = (name, created)
    out = ["Plan fikstürü (K-205)", "", "Satır sayıları"]
    counts = []
    for rid, (name, created) in named.items():
        n = [session.execute(sa.text(f"SELECT COUNT(*) FROM planning.{t} WHERE PlanRunId = :r"), {"r": rid}).scalar() for t in TABLES]
        counts.append([name, rid, created.date() if created else None, *n])
    out += _table(counts, ["Plan", "Plan hesabı", "Gece", "Talep", "Tedarik planı", "Karşılama", "Ek mesai", "Transfer", "Hareket", "Yük", "Pegging", "Uyarı", "Metrik"])
    base = next(rid for rid, (name, _) in named.items() if name == "Baz · güncel")
    q = lambda sql, **p: session.execute(sa.text(sql), {"r": base, **p}).all()  # noqa: E731
    section = lambda title, rows, head: out.extend(["", title] + (_table(rows, head) if rows else ["    (satır yok)"]))  # noqa: E731

    section("1 · Kısmen zamanında, kısmen geç sipariş (SO-1027)", q(
        "SELECT f.OrderNo, f.PeriodStart, f.Quantity, f.IsTardy, d.DuePeriodStart, d.OnTimeQuantity, d.LateQuantity FROM planning.DemandFulfillment f "
        "JOIN planning.PlannedDemand d ON d.Id = f.PlannedDemandId WHERE f.PlanRunId = :r AND f.OrderNo = :o ORDER BY f.PeriodStart", o=d.LATE_ORDER),
        ["Sipariş", "Dönem", "Karşılama", "Gecikmeli", "Vade dönemi", "Zamanında", "Geciken"])
    section("2 · Hiç karşılanamayan sipariş (SO-1040)", q(
        "SELECT d.OrderNo, d.DemandQuantity, d.FulfilledQuantity, d.UnmetQuantity, (SELECT COUNT(*) FROM planning.PlanWarning w WHERE w.PlanRunId = :r "
        "AND w.WarningCode = N'ORDER_UNMET' AND w.ObjectId = d.SalesOrderLineId) FROM planning.PlannedDemand d WHERE d.PlanRunId = :r AND d.OrderNo = :o",
        o=d.IMPOSSIBLE_ORDER), ["Sipariş", "Talep", "Karşılanan", "Karşılanmayan", "ORDER_UNMET"])
    isl5 = [g for g in capacity_view.group_periods(session, base, today) if g["Code"] == d.BOTTLENECK_GROUP and (g["Overtime"] or g["Overload"] > 0)]
    section("3 · Kapasitesi dolan grup ve ek mesai (ISL5)", [[g["PeriodStart"], round(g["Load"], 1), round(g["AvailableCapacity"], 1), round(g["Overtime"], 2),
                                                               round(100 * g["Load"] / g["AvailableCapacity"], 1) if g["AvailableCapacity"] else None,
                                                               round(100 * g["Load"] / (g["AvailableCapacity"] + g["Overtime"]), 1) if g["AvailableCapacity"] else None,
                                                               round(max(g["Overload"], 0), 1)] for g in isl5],
            ["Dönem", "Yük", "Kapasite", "Ek mesai", "Doluluk %", "Ek mesaili doluluk %", "Aşım"])
    section("4 · Özel alokasyon ve genelden transfer", q(
        "SELECT m.Code, t.PeriodStart, t.AllocationLevel, t.AllocationKey, t.Quantity FROM planning.PlannedAllocationTransfer t "
        "JOIN core.Material m ON m.Id = t.MaterialId AND m.VersionTo IS NULL WHERE t.PlanRunId = :r ORDER BY m.Code, t.PeriodStart"),
        ["Malzeme", "Dönem", "Seviye", "Anahtar", "Miktar"])
    section("   Pegging'de genelden karşılanan (arz gerçek genel arz)", q(
        "SELECT TOP 5 m.Code, g.SupplyMovementType, g.SupplyAllocationKey, g.DemandMovementType, g.DemandAllocationKey, g.Quantity, g.IsFromGeneral "
        "FROM planning.Pegging g JOIN core.Material m ON m.Id = g.MaterialId AND m.VersionTo IS NULL WHERE g.PlanRunId = :r AND g.IsFromGeneral = 1 ORDER BY g.Id"),
        ["Malzeme", "Arz türü", "Arz anahtarı", "İhtiyaç türü", "İhtiyaç anahtarı", "Miktar", "Genelden"])
    section("5 · Kullanılmayan ayrılmış arz (sahibi kapanmış ya da yok)", q(
        "SELECT m.Code, t.MovementType, t.AllocationKey, t.Quantity, (SELECT ISNULL(SUM(g.Quantity), 0) FROM planning.Pegging g WHERE g.SupplyTransactionId = t.Id) "
        "FROM planning.MaterialTransaction t JOIN core.Material m ON m.Id = t.MaterialId AND m.VersionTo IS NULL WHERE t.PlanRunId = :r AND t.Direction = N'+' "
        "AND (t.AllocationKey IN (:c, :p) OR t.AllocationKey LIKE :o)", c=d.MISSING_CUSTOMER, p=d.MISSING_PROJECT, o=f"{d.MISSING_ORDER}%"),
        ["Malzeme", "Hareket", "Anahtar", "Miktar", "Bağlanan"])
    section("6 · Fason üretim", q(
        "SELECT TOP 3 s.SupplyNo, m.Code, su.Code, s.OrderDate, s.PeriodStart, s.Quantity, (SELECT SUM(l.CapacityUsage) FROM planning.CapacityLoad l "
        "JOIN core.ResourceGroup g ON g.Id = l.ResourceGroupId AND g.VersionTo IS NULL AND g.IsSubcontractor = 1 WHERE l.PlannedSupplyId = s.Id) "
        "FROM planning.PlannedSupply s JOIN core.Material m ON m.Id = s.MaterialId AND m.VersionTo IS NULL LEFT JOIN core.Supplier su ON su.Id = s.SupplierId "
        "AND su.VersionTo IS NULL WHERE s.PlanRunId = :r AND s.IsSubcontract = 1 AND s.Source = N'Plan' ORDER BY s.PeriodStart"),
        ["No", "Malzeme", "Tedarikçi", "Sipariş tarihi", "Başlangıç", "Miktar", "Fason grup yükü"])
    section("7 · İki döneme bölünmüş üretim siparişi (WO-5012)", q(
        "SELECT s.SupplyNo, s.Source, s.PeriodStart, s.Quantity, (SELECT COUNT(*) FROM planning.MaterialTransaction t WHERE t.PlannedSupplyId = s.Id AND t.Direction = N'-'), "
        "(SELECT SUM(l.CapacityUsage) FROM planning.CapacityLoad l WHERE l.PlannedSupplyId = s.Id) FROM planning.PlannedSupply s WHERE s.PlanRunId = :r "
        "AND s.SupplyNo = N'WO-5012' ORDER BY s.PeriodStart"), ["No", "Kaynak", "Başlangıç", "Miktar", "Bileşen ihtiyacı satırı", "Yük"])
    section("8 · Sabitlenmiş ve elle değiştirilmiş kayıt", q(
        "SELECT s.SupplyNo, m.Code, s.IsFixed, s.IsManual, s.Quantity, s.ProposedQuantity, s.PeriodStart, s.ProposedPeriodStart FROM planning.PlannedSupply s "
        "JOIN core.Material m ON m.Id = s.MaterialId AND m.VersionTo IS NULL WHERE s.PlanRunId = :r AND (s.IsFixed = 1 OR s.IsManual = 1)"),
        ["No", "Malzeme", "Sabit", "Elle", "Miktar", "Öneri miktarı", "Başlangıç", "Öneri dönemi"])
    section("9 · Alternatif üretim versiyonu (ALT-017)", q(
        "SELECT TOP 3 s.SupplyNo, m.Code, pv.Code, s.BOMCode, (SELECT SUM(t.Quantity) FROM planning.MaterialTransaction t JOIN core.Material c ON c.Id = t.MaterialId "
        "AND c.VersionTo IS NULL WHERE t.PlannedSupplyId = s.Id AND c.Code = :only) FROM planning.PlannedSupply s JOIN core.Material m ON m.Id = s.MaterialId "
        "AND m.VersionTo IS NULL JOIN core.ProductionVersion pv ON pv.Id = s.ProductionVersionId AND pv.VersionTo IS NULL WHERE s.PlanRunId = :r AND m.Code = :alt "
        "ORDER BY s.PeriodStart", alt=d.ALTERNATIVE_PARENT, only=d.ALTERNATIVE_ONLY), ["No", "Malzeme", "Versiyon", "Ürün ağacı", f"{d.ALTERNATIVE_ONLY} ihtiyacı"])
    section("10 · Yuvarlanmış satın alma (artan stok)", q(
        "SELECT TOP 3 s.SupplyNo, m.Code, s.Quantity, s.RoundedQuantity, s.RoundedQuantity - s.Quantity FROM planning.PlannedSupply s JOIN core.Material m "
        "ON m.Id = s.MaterialId AND m.VersionTo IS NULL WHERE s.PlanRunId = :r AND s.RoundedQuantity > s.Quantity ORDER BY s.RoundedQuantity - s.Quantity DESC"),
        ["No", "Malzeme", "Miktar", "Yuvarlanmış", "Fazla"])
    section("11 · Sipariş tarihi geçmişte kalan satın alma planı", q(
        "SELECT TOP 3 s.SupplyNo, m.Code, s.OrderDate, s.PeriodStart, w.Value FROM planning.PlannedSupply s JOIN core.Material m ON m.Id = s.MaterialId "
        "AND m.VersionTo IS NULL JOIN planning.PlanWarning w ON w.PlanRunId = s.PlanRunId AND w.WarningCode = N'PURCHASE_LATE' AND w.ObjectId = s.Id "
        "WHERE s.PlanRunId = :r ORDER BY CASE WHEN m.Code = :late THEN 0 ELSE 1 END, w.Value DESC", late=d.LATE_MATERIAL),
        ["No", "Malzeme", "Sipariş tarihi", "Başlangıç", "Gün geçmiş"])
    section("12 · Plana dahil olmayan talep (Teklif)", q(
        "SELECT d.OrderNo, d.DemandType, d.DemandQuantity, d.IsIncluded, d.FulfilledQuantity FROM planning.PlannedDemand d WHERE d.PlanRunId = :r AND d.IsIncluded = 0"),
        ["Sipariş", "Tür", "Talep", "Plana dahil", "Karşılanan"])
    metrics_rows = []
    for rid, (name, _) in named.items():
        m = dict(session.execute(sa.text("SELECT MetricCode, Value FROM planning.PlanMetric WHERE PlanRunId = :r"), {"r": rid}).all())
        metrics_rows.append([name, m.get("OnTimePct"), m.get("LateLines"), m.get("UnmetLines"), m.get("OvertimeHours"), m.get("OverloadedGroupPeriods"),
                             m.get("MaxUtilizationPct")])
    section("Üç planın metrikleri", metrics_rows, ["Plan", "Zamanında %", "Geciken satır", "Karşılanmayan satır", "Ek mesai", "Aşırı yüklü grup × dönem", "En yüksek doluluk %"])
    out += ["", "Tutarlılık denetimleri"]
    for rid, (name, _) in named.items():
        found = checks.problems(session, rid, today)
        out.append(f"    {name}: " + ("geçti (bakiye, talep, arz, yük ve ek mesai, pegging, uyarı)" if not found else
                                      f"{len(found)} sorun: " + "; ".join(f"{p['check']}: {p['detail']}" for p in found[:5])))
    return "\n".join(out)
