"""Malzeme listesi (core.Material). Şimdilik tablo bileşeni denemesi (/tablo); malzeme ekranı 6.1'de."""
from .definition import ListDefinition

MATERIALS = ListDefinition(
    name="materials",
    table="core.Material",
    title="Malzeme listesi",
    file_slug="malzeme",
    function=10,  # Ana veri görüntüleme (K-100)
    fields=(
        "Code", "Name", "MaterialLevel", "MaterialType", "MaterialGroup", "Brand", "PlannerCode", "MRPGroup", "BaseUom",
        "DefaultSupplyType", "IsCustomerSupplied", "IsActive", "IsCritical", "IsPurchasable", "IsProducible", "IsSellable",
        "IsSubcontractable", "IsCustomTracked", "IsPhantom", "IsNonStockable", "GoodsReceiptDays", "SafetyStock", "StockCoverageDays",
        "MaxStock", "LotSizePolicy", "MinLot", "MaxLot", "LotMultiple", "QtyPerBox", "QtyPerPallet", "ScrapRatio", "ShelfLifeDays",
        *(f"AdditionalText{i}" for i in range(1, 8)), *(f"AdditionalNumber{i}" for i in range(1, 4)),
        "UpdatedAt",
    ),
    default_visible=("Code", "Name", "MaterialLevel", "MaterialGroup", "BaseUom", "DefaultSupplyType",
                     "SafetyStock", "UpdatedAt"),
    default_sort=(("Code", "asc"),),
    server_values=frozenset({"MaterialGroup", "BaseUom"}),
    # Gün ondalıksız; fire oranı yüzde gösterilir, 2 ondalık (K-113); miktarlar temel birimin ondalığıyla (K-88).
    decimals={
        "StockCoverageDays": 0, "GoodsReceiptDays": 0, "ScrapRatio": 2,
        "AdditionalNumber1": 2, "AdditionalNumber2": 2, "AdditionalNumber3": 2,
    },
    percent=frozenset({"ScrapRatio"}),
    unit_field="BaseUom",
    unit_decimals=frozenset({"SafetyStock", "MaxStock", "MinLot", "MaxLot", "LotMultiple", "QtyPerBox", "QtyPerPallet"}),
    aggregates={"SafetyStock": "sum", "MaxStock": "sum",
                "StockCoverageDays": "avg", "GoodsReceiptDays": "avg", "ScrapRatio": "avg"},
)
