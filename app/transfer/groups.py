"""Kısmi aktarımın grupları (fonksiyon 06; K-150, K-155). docs/00 K-150 ile birebir (test karşılaştırır).

Her işlem verisi tablosu tam bir grupta; Proje ve Proje grubu katalogda Ana veri, istisna olarak Talep grubuyla aktarılır.
"""
from collections.abc import Iterable

GROUPS: dict[str, tuple[str, ...]] = {
    "Talep": ("SalesOrderLine", "Forecast", "Project", "ProjectGroup"),
    "Stok": ("Stock", "BorrowPayback"),
    "Üretim": ("WorkOrder", "WorkOrderComponent", "WorkOrderOperation", "ProductionConfirmation"),
    "Satın alma": ("PurchaseOrderLine",),
    "İzin": ("EmployeeAbsence",),
}


class UnknownGroup(ValueError):
    pass


def group_tables(groups: Iterable[str]) -> set[str]:
    """Seçilen grupların tabloları; bilinmeyen grup UnknownGroup."""
    tables: set[str] = set()
    for g in groups:
        if g not in GROUPS:
            raise UnknownGroup(g)
        tables.update(GROUPS[g])
    return tables
