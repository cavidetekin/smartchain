"""Dünden bugüne listeleri (ekran 28, fonksiyon 101; K-159, K-160). Sürümsüzdür.

`raw-compare`: tablo başına özet, 25 tablonun hepsi (verisi olmayan da). `raw-compare-changes`: güncellenen alanlar. `raw-compare-new-<tablo>` ve
`raw-compare-missing-<tablo>`: yeni gelen ve gelmeyen kayıtların tablonun bütün alanlarıyla hâli ("Veriyi gör" gibi).
"""
import sqlalchemy as sa

from app.compare import raw as compare
from app.integration.contract import ENTITIES, stg_columns
from app.validation.sqlkit import labels as field_labels
from db.models import metadata

from .data_entities import _catalog
from .definition import ListDefinition
from .validation import _decimals

SUMMARY = metadata.tables["adm.RawCompare"]
ROW = metadata.tables["adm.RawCompareRow"]
NO_DATA = "Veri yok"
STATES = [compare.READY, compare.NO_PREVIOUS, compare.FAILED, NO_DATA]

_change = sa.cast(sa.case((SUMMARY.c.YesterdayRows > 0, sa.cast(SUMMARY.c.TodayRows - SUMMARY.c.YesterdayRows, sa.Numeric(18, 4)) / SUMMARY.c.YesterdayRows)), sa.Numeric(18, 4))
_source = (sa.select(_catalog.c.Id, _catalog.c.Id.label("CatalogOrder"), _catalog.c.Entity, _catalog.c.Name, SUMMARY.c.YesterdayAt, SUMMARY.c.TodayAt, SUMMARY.c.TodayLoad,
                     SUMMARY.c.YesterdayRows, SUMMARY.c.TodayRows, _change.label("ChangePct"), SUMMARY.c.NewCount, SUMMARY.c.MissingCount, SUMMARY.c.ChangedCount,
                     sa.func.coalesce(SUMMARY.c.State, sa.literal_column(f"N'{NO_DATA}'", sa.Unicode)).label("State"))
           .select_from(_catalog.outerjoin(SUMMARY, SUMMARY.c.EntityName == _catalog.c.Entity)).subquery("raw_compare"))

_FIELDS = ("Name", "YesterdayAt", "TodayAt", "TodayLoad", "YesterdayRows", "TodayRows", "ChangePct", "NewCount", "MissingCount", "ChangedCount", "State", "CatalogOrder", "Entity")
RAW_COMPARE = ListDefinition(
    name="raw-compare", table="adm.RawCompare", title="Dünden bugüne", file_slug="dunden-bugune", function=101, versioned=False, source=_source,
    key_fields=("Entity", "Name", "State", "NewCount", "MissingCount", "ChangedCount"),
    fields=_FIELDS, default_visible=_FIELDS[:-2], default_sort=(("CatalogOrder", "asc"),),
    labels={"Name": "Tablo", "YesterdayAt": "Dünkü veri", "TodayAt": "Bugünkü veri", "TodayLoad": "Bugünkü yükleme", "YesterdayRows": "Dünkü satır", "TodayRows": "Bugünkü satır",
            "ChangePct": "Değişim %", "NewCount": "Yeni gelen", "MissingCount": "Gelmeyen", "ChangedCount": "Güncellenen", "State": "Durum", "CatalogOrder": "Yükleme sırası",
            "Entity": "Teknik tablo adı"},
    values={"TodayLoad": [compare.LOAD_FULL, compare.LOAD_CHANGED, compare.LOAD_MIXED], "State": STATES},
    percent=frozenset({"ChangePct"}), decimals={"ChangePct": 1},
    notes={"YesterdayAt": "Son verinin gününden önceki günlerde gelen son veri.", "TodayAt": "Tablonun en son verisi.",
           "MissingCount": "Dün gelip bugün gelmeyen kayıtlar. Ekle / güncelle yüklemesi gelmeyen kayıt üretmez."},
)

_changes = (sa.select(ROW.c.Id, ROW.c.EntityName, ROW.c.RowKey, ROW.c.FieldLabel, ROW.c.OldValue, ROW.c.NewValue).where(ROW.c.Kind == compare.CHANGED).subquery("raw_compare_changes"))
RAW_COMPARE_CHANGES = ListDefinition(
    name="raw-compare-changes", table="adm.RawCompareRow", title="Güncellenenler", file_slug="guncellenenler", function=101, versioned=False, source=_changes,
    fields=("RowKey", "FieldLabel", "OldValue", "NewValue"), default_visible=("RowKey", "FieldLabel", "OldValue", "NewValue"),
    default_sort=(("RowKey", "asc"), ("FieldLabel", "asc")), filter_only=("EntityName",),
    labels={"RowKey": "Kayıt", "FieldLabel": "Alan", "OldValue": "Dünkü değer", "NewValue": "Bugünkü değer", "EntityName": "Teknik tablo adı"},
)


def _rows_list(entity, kind: str, slug: str, title: str) -> ListDefinition:
    s = metadata.tables[f"stg.{entity.table}"]
    names = [c.name for c in stg_columns(entity.table)]
    source = (sa.select(s.c.StagingRowId.label("Id"), ROW.c.RowKey, *[s.c[n] for n in names])
              .select_from(ROW.join(s, s.c.StagingRowId == ROW.c.StagingRowId)).where(ROW.c.EntityName == entity.table, ROW.c.Kind == kind)
              .subquery(f"raw_compare_{slug}_{entity.table}"))
    labels = {**{n: l for n, l in field_labels(entity.table).items() if not n.startswith("Additional")}, "RowKey": "Kayıt"}
    fields = ("RowKey", *names)
    return ListDefinition(name=f"raw-compare-{slug}-{entity.table}", table=f"stg.{entity.table}", title=f"{title} · {entity.name}", file_slug=f"{slug}-{entity.slug}", function=101,
                          versioned=False, source=source, fields=fields, default_visible=fields, default_sort=(("RowKey", "asc"),), labels=labels, decimals=_decimals(entity.table))


RAW_COMPARE_ROWS = tuple(_rows_list(e, kind, slug, title) for e in ENTITIES for kind, slug, title in ((compare.NEW, "new", "Yeni gelenler"), (compare.MISSING, "missing", "Gelmeyenler")))
