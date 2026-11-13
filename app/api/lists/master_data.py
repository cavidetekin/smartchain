"""Ana veri (ekran 03, fonksiyon 10) ve İşlem verisi (ekran 29, fonksiyon 102) ekranlarının listeleri (K-168, K-169): aktarılan veri, salt okunur.

Her tablo için ortak liste, tablo modelinden üretilir: etiket ve değer listesi docs'tan gelen `info`'dan; sistem kolonları (kimlik, versiyon, parti)
dışarıda, son değişiklik zamanı seçilebilir. İlişki kolonları (LocationId, MaterialId…) alt sorguda güncel kayıtla eşlenip koda döner
(`LocationCode`, `MaterialCode`…). Standart görünümde aktarılan bütün alanlar açıktır (K-169); Aktif kolonu gizli, çünkü aktarım pasif kaydı
kapatır (K-149); versiyonsuz Lokasyon'da pasif kalır, orada açıktır (K-153).
Miktarların ondalığı satırın biriminden (K-88): malzeme miktarları malzemenin temel birimi, bileşen miktarı bileşen birimi (boşsa bileşenin
temel birimi), kapasite ve tüketim kaynağın kapasite birimi. İlişkiden gelen birim listede kolon değildir (`UnitOfRow`), yalnız ondalık içindir.
Malzeme mevcut `materials` listesidir (görünümler korunur).
"""
from dataclasses import dataclass, field

import sqlalchemy as sa

from app.manual import MANUAL_COLUMN, MANUAL_LABEL, STATES, state_column
from db.models import ENTITY_CATALOG, metadata

from .definition import ListDefinition
from .materials import MATERIALS

SYSTEM = ("VersionFrom", "VersionTo", "ImportBatchId", "BusinessKey")
HIDDEN = ("IsActive", "UpdatedAt")  # Standart görünümde gizli (K-169)
UNIT_OF_ROW = "UnitOfRow"
NAMES = {row[0]: row[1] for row in ENTITY_CATALOG} | {"UnitOfMeasure": "Birim", "ResourceGroupAssignment": "Grup ataması"}
SLUGS = {row[0]: row[4] for row in ENTITY_CATALOG} | {"UnitOfMeasure": "birim"}


def _code(a: sa.Alias) -> sa.ColumnElement:
    return a.c.Code


# İlişki kolonu → (hedef tablo, koda dönen kolonun adı, hedefte gösterilecek değer)
REFS = {
    "LocationId": ("Location", "LocationCode", _code), "MaterialId": ("Material", "MaterialCode", _code),
    "ComponentMaterialId": ("Material", "ComponentMaterialCode", _code), "ReferenceMaterialId": ("Material", "ReferenceMaterialCode", _code),
    "ReferenceProductionVersionId": ("ProductionVersion", "ReferenceProductionVersionCode", _code),
    "ProductionVersionId": ("ProductionVersion", "ProductionVersionCode", _code),
    "ResourceId": ("Resource", "ResourceCode", _code), "ResourceGroupId": ("ResourceGroup", "ResourceGroupCode", _code),
    "SupplierId": ("Supplier", "SupplierCode", _code), "SubcontractorId": ("Supplier", "SubcontractorCode", _code),
    "CalendarId": ("Calendar", "CalendarCode", _code), "ProjectGroupId": ("ProjectGroup", "ProjectGroupCode", _code),
    "CustomerId": ("Customer", "CustomerCode", _code), "ProjectId": ("Project", "ProjectCode", _code),
    "LendingProjectId": ("Project", "LendingProjectCode", _code), "BorrowingProjectId": ("Project", "BorrowingProjectCode", _code),
    "WorkOrderId": ("WorkOrder", "WorkOrderCode", lambda a: a.c.WorkOrderNo),
    "ParentWorkOrderId": ("WorkOrder", "ParentWorkOrderCode", lambda a: a.c.WorkOrderNo),
    "SalesOrderLineId": ("SalesOrderLine", "SalesOrderLineCode",  # "sipariş no / satır no" (K-169)
                         lambda a: sa.case((a.c.Id.is_(None), None), else_=sa.func.concat(a.c.OrderNo, " / ", sa.cast(a.c.LineNo, sa.Unicode(10))))),
}


@dataclass(frozen=True)
class Spec:
    table: str
    name: str
    decimals: dict[str, int] = field(default_factory=dict)
    percent: frozenset[str] = frozenset()
    unit_decimals: frozenset[str] = frozenset()
    # Satırın birimi: tablonun kolonu (unit) ya da ilişkideki birim (unit_ref: ilişki kolonu, hedefteki birim kolonu); ikisi birlikteyse
    # tablonun kolonu boşken ilişkideki (ör. bileşen birimi yoksa bileşenin temel birimi)
    unit: str | None = None
    unit_ref: tuple[str, str] | None = None
    function: int = 10


ADD = {f"AdditionalNumber{i}": 2 for i in range(1, 4)}
MATERIAL_UNIT = ("MaterialId", "BaseUom")
CAPACITY_UNIT = ("ResourceId", "CapacityUnit")

MASTER_SPECS: tuple[Spec, ...] = (
    Spec("MaterialReference", "master-material-reference", {"TimeFactor": 2}),
    Spec("ProductionVersion", "master-production-version", ADD, unit_decimals=frozenset({"BaseQuantity"}), unit_ref=MATERIAL_UNIT),
    Spec("BOM", "master-bom", {"ScrapRatio": 2, **ADD}, percent=frozenset({"ScrapRatio"}), unit_decimals=frozenset({"Quantity"}),
         unit="ComponentUom", unit_ref=("ComponentMaterialId", "BaseUom")),
    Spec("Routing", "master-routing", {"TransferQuantity": 2, "WaitingTimeHours": 2, "TransferTimeHours": 2, **ADD},
         unit_decimals=frozenset({"Consumption"}), unit_ref=CAPACITY_UNIT),
    Spec("Resource", "master-resource",
         {"SubconFixedLeadTimeDays": 2, "SubconVariableDaysPerUnit": 4, "RemainingOverTimeYear": 2, "RemainingOverTimeMonth": 2, **ADD},
         unit_decimals=frozenset({"DailyCapacity"}), unit="CapacityUnit"),
    Spec("ResourceGroup", "master-resource-group", ADD),
    Spec("ResourceGroupAssignment", "master-resource-group-assignment"),
    Spec("Supplier", "master-supplier", ADD),
    Spec("MaterialSupplier", "master-material-supplier", {"QuotaRatio": 2, "FixedLeadTimeDays": 0, "VariableLeadTimeDays": 4, **ADD},
         percent=frozenset({"QuotaRatio"}), unit_decimals=frozenset({"MinimumOrderQuantity", "OrderLotSize", "MaximumOrderQuantity"}),
         unit_ref=MATERIAL_UNIT),
    Spec("Customer", "master-customer", ADD),
    Spec("Location", "master-location", ADD),
    Spec("UnitOfMeasure", "master-unit-of-measure"),
    Spec("UomConversion", "master-uom-conversion", {"Factor": 4}),
)

TX = 102  # İşlem verisi görüntüleme (K-169)
TRANSACTION_SPECS: tuple[Spec, ...] = (
    Spec("SalesOrderLine", "transaction-sales-order", ADD, unit_decimals=frozenset({"OpenQuantity", "OrderedQuantity", "DeliveredQuantity"}),
         unit_ref=MATERIAL_UNIT, function=TX),
    Spec("Forecast", "transaction-forecast", ADD, unit_decimals=frozenset({"Quantity"}), unit_ref=MATERIAL_UNIT, function=TX),
    Spec("Project", "transaction-project", ADD, function=TX),
    Spec("ProjectGroup", "transaction-project-group", ADD, function=TX),
    Spec("Stock", "transaction-stock", ADD, unit_decimals=frozenset({"Quantity"}), unit_ref=MATERIAL_UNIT, function=TX),
    Spec("BorrowPayback", "transaction-borrow-payback", ADD, unit_decimals=frozenset({"BorrowedQuantity", "PaidBackQuantity"}),
         unit_ref=MATERIAL_UNIT, function=TX),
    Spec("WorkOrder", "transaction-work-order", ADD,
         unit_decimals=frozenset({"OrderedQuantity", "OpenQuantity", "CompletedQuantity", "ScrapQuantity"}), unit_ref=MATERIAL_UNIT, function=TX),
    Spec("WorkOrderComponent", "transaction-work-order-component", {"ScrapRatio": 2, **ADD}, percent=frozenset({"ScrapRatio"}),
         unit_decimals=frozenset({"RequiredQuantity", "IssuedQuantity", "RemainingQuantity", "UnitUsage"}), unit_ref=MATERIAL_UNIT, function=TX),
    Spec("WorkOrderOperation", "transaction-work-order-operation", {"TransferQuantity": 2, "WaitingTimeHours": 2, "TransferTimeHours": 2, **ADD},
         unit_decimals=frozenset({"PlannedConsumption", "ConfirmedConsumption", "RemainingConsumption"}), unit_ref=CAPACITY_UNIT, function=TX),
    Spec("ProductionConfirmation", "transaction-production-confirmation", ADD, unit_decimals=frozenset({"ConfirmedQuantity"}),
         unit_ref=MATERIAL_UNIT, function=TX),
    Spec("PurchaseOrderLine", "transaction-purchase-order", ADD,
         unit_decimals=frozenset({"OpenQuantity", "OrderedQuantity", "ReceivedQuantity"}), unit_ref=MATERIAL_UNIT, function=TX),
    Spec("EmployeeAbsence", "transaction-employee-absence", {"HoursPerDay": 2, **ADD}, function=TX),
)


def _current(t: sa.Table) -> sa.ColumnElement:
    """Eşlenen kaydın güncel versiyonu (liste her zaman son veri versiyonunu gösterir)."""
    return t.c.VersionTo.is_(None) if "VersionTo" in t.c else sa.true()


def _build(spec: Spec) -> ListDefinition:
    table = metadata.tables[f"core.{spec.table}"]
    # İlk kolon "Manuel değer" (K-170): boş, Var, Var / ERP Güncellendi, Var / Kural Güncellendi, süzülebilir
    cols, fields = [state_column(spec.table, table)], [MANUAL_COLUMN]
    labels, values = {MANUAL_COLUMN: MANUAL_LABEL}, {MANUAL_COLUMN: STATES}
    joined = table
    aliases: dict[str, sa.Alias] = {}
    for c in table.c:
        info = c.info or {}
        if c.name in SYSTEM or c.name == "Id":
            cols.append(c)
            continue
        if c.name in REFS:
            target, code, shown = REFS[c.name]
            a = metadata.tables[f"core.{target}"].alias(f"r_{c.name}")
            aliases[c.name] = a
            joined = joined.outerjoin(a, sa.and_(a.c.Id == c, _current(a)))
            cols.append(shown(a).label(code))
            labels[code] = info.get("label") or code
            fields.append(code)
            continue
        if info.get("source") == "Sistem" and c.name != "UpdatedAt":
            continue
        cols.append(c)
        if info.get("label"):
            labels[c.name] = info["label"]
        if info.get("values"):
            values[c.name] = info["values"]
        fields.append(c.name)
    if "Id" not in table.c:  # birim: satır kimliği kod (ortak tablonun satır işlemleri için)
        cols.append(table.c.Code.label("Id"))
    unit = spec.unit
    if spec.unit_ref:
        ref, unit_col = spec.unit_ref
        related = aliases[ref].c[unit_col]
        cols.append((sa.func.coalesce(table.c[spec.unit], related) if spec.unit else related).label(UNIT_OF_ROW))
        unit = UNIT_OF_ROW
    source = sa.select(*cols).select_from(joined).subquery(f"md_{spec.table}")
    numeric = {f for f in fields if isinstance(source.c[f].type, sa.Numeric) and not isinstance(source.c[f].type, sa.Integer)}
    decimals = {f: spec.decimals[f] for f in numeric if f in spec.decimals}
    missing = numeric - set(decimals) - set(spec.unit_decimals)
    assert not missing, f"{spec.table}: ondalığı tanımsız sayı alanı {sorted(missing)}"  # K-88
    if "Id" in table.c:  # İlişkili kayıtlar kimlikle süzülür (K-173; yalnız süzmede)
        labels["Id"] = "Kayıt no"
    hidden = ("UpdatedAt",) if spec.table == "Location" else HIDDEN  # Lokasyon versiyonsuz, pasif kalır (K-153, K-169)
    return ListDefinition(
        name=spec.name,
        table=f"core.{spec.table}",
        title=NAMES[spec.table],
        file_slug=SLUGS[spec.table],
        function=spec.function,
        versioned="VersionFrom" in table.c,
        source=source,
        labels=labels,
        values=values,
        fields=tuple(fields),
        default_visible=tuple(f for f in fields if f not in hidden),
        default_sort=((next(f for f in fields if f not in ("LocationCode", MANUAL_COLUMN)), "asc"),),
        decimals=decimals,
        percent=spec.percent,
        unit_field=unit if spec.unit_decimals else None,
        unit_decimals=spec.unit_decimals,
        server_values=frozenset(f for f in fields if f.endswith("Code") and f != "Code") | ({"Id"} if "Id" in table.c else set()),
        filter_only=("Id",) if "Id" in table.c else (),
        manual_table=spec.table,
    )


MASTER_LISTS: tuple[ListDefinition, ...] = tuple(_build(s) for s in MASTER_SPECS)
TRANSACTION_LISTS: tuple[ListDefinition, ...] = tuple(_build(s) for s in TRANSACTION_SPECS)
BY_NAME = {d.name: d for d in (MATERIALS, *MASTER_LISTS, *TRANSACTION_LISTS)}

# Ekranların sekmeleri ve tabloları (K-168, K-169); ön yüz aynı sırayı kullanır, sayılar ucu bu tabloları sayar.
MASTER_TABS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("malzeme", ("materials", "master-material-reference")),
    ("urun-agaci-ve-rota", ("master-production-version", "master-bom", "master-routing")),
    ("kaynak", ("master-resource", "master-resource-group", "master-resource-group-assignment")),
    ("tedarikci-ve-musteri", ("master-supplier", "master-material-supplier", "master-customer")),
    ("lokasyon-ve-birim", ("master-location", "master-unit-of-measure", "master-uom-conversion")),
)
TRANSACTION_TABS: tuple[tuple[str, tuple[str, ...]], ...] = (  # aktarım grupları (K-150)
    ("talep", ("transaction-sales-order", "transaction-forecast", "transaction-project", "transaction-project-group")),
    ("stok", ("transaction-stock", "transaction-borrow-payback")),
    ("uretim", ("transaction-work-order", "transaction-work-order-component", "transaction-work-order-operation", "transaction-production-confirmation")),
    ("satin-alma", ("transaction-purchase-order",)),
    ("izin", ("transaction-employee-absence",)),
)
