"""Malzeme listesi (core.Material). Şimdilik tablo bileşeni denemesi (/tablo); malzeme ekranı 6.1'de."""
from .definition import ListDefinition

MATERIALS = ListDefinition(
    name="materials",
    table="core.Material",
    fields=(
        "Code", "Name", "MaterialLevel", "MaterialGroup", "BaseUom", "DefaultProcurement", "Ownership",
        "IsPurchasable", "IsProducible", "IsSellable", "IsProjectTracked", "IsPhantom",
        "ProductionLeadTimeDays", "GoodsReceiptDays", "SafetyStock", "MaxStock", "LotSizePolicy",
        "MinLot", "MaxLot", "LotMultiple", "AssemblyScrapPct", "ShelfLifeDays",
        *(f"AdditionalText{i}" for i in range(1, 8)), *(f"AdditionalNumber{i}" for i in range(1, 4)),
        "UpdatedAt",
    ),
    default_visible=("Code", "Name", "MaterialLevel", "MaterialGroup", "BaseUom", "DefaultProcurement",
                     "ProductionLeadTimeDays", "SafetyStock", "UpdatedAt"),
    default_sort=(("Code", "asc"),),
    server_values=frozenset({"MaterialGroup", "BaseUom"}),
)
