"""Öncelik yönetimi listeleri (ekran 32, fonksiyon 25; K-195): Müşteri, Proje ve Sipariş sekmeleri ve kartlardaki tahminler. Her liste ana verinin
(ve işlem verisinin) ilgili listesinden türetilir (`capacity.from_master`): bütün alanlar ve İlişkili alanlar Alanlar'dan açılır; üstüne senaryonun
girilmiş öncelik grubu ("Öncelik grubu", "Kaynağı") ve hesaplanan "Geçerli öncelik grubu", "Öncelik kaynağı" gelir. Satırın kimliği kaydın
kimliğidir; yazma uçları (`/api/priorities/<düzey>`) bu kimlikle çalışır. Sipariş listesinde yalnız açık satırlar (açık miktarı sıfırdan büyük).

İşlem verisi'nin Satış siparişi ve Tahmin listeleri de iki hesaplanan alanı taşır (`with_priority`): kapalı gelir, seçili senaryoya göre hesaplanır.
"""
from dataclasses import replace

import sqlalchemy as sa

from app import priorities as rules
from app.periods import cache

from .capacity import from_master, master_fields
from .definition import ListDefinition, SourceContext
from .master_data import BY_NAME
from .period_tables import skeleton

FUNCTION = 25
EFFECTIVE, SOURCE = "EffectivePriorityGroup", "PrioritySource"
ERP_LABEL = "ERP önceliği"
_ENTRY = {"JoinId": sa.BigInteger(), rules.FIELD: sa.Integer(), "Origin": sa.Unicode(20), "StoredId": sa.BigInteger(), "OverriddenFields": sa.Unicode(400),
          "BaseValues": sa.UnicodeText(), "CanRestore": sa.Boolean()}
_COMPUTED = {EFFECTIVE: sa.Integer(), SOURCE: sa.Unicode(10)}
_ORIGINS = [rules.BASE, rules.DIFF, rules.OWN]
_SOURCES = [rules.ORDER, rules.PROJECT, rules.CUSTOMER, rules.NONE]
_LABELS = {rules.FIELD: rules.LABEL, EFFECTIVE: "Geçerli öncelik grubu", SOURCE: "Öncelik kaynağı", "Origin": "Kaynağı", "Priority": ERP_LABEL, "StoredId": "Saklanan satır",
           "OverriddenFields": "Senaryoda değişen alanlar", "BaseValues": "Baz değerleri", "CanRestore": "Senaryo farkı kaldırılabilir",
           "CustomerId": "Müşteri no", "ProjectId": "Proje no"}      # kartların süzmesi (etiketsiz alan sorguda tanınmaz)
_NOTES = {rules.FIELD: "Bu ekranda girilen 1–5 öncelik grubu; küçük olan önce. Boşsa ERP önceliği, o da yoksa hiyerarşide bir üst düzey",
          "Priority": "ERP'den ya da veri kuralından gelen öncelik; burada düzenlenmez. 1–5 dışındaysa yok sayılır",
          EFFECTIVE: "Hiyerarşiden çıkan sonuç: sipariş → proje → müşteri; hiçbirinde değer yoksa 5",
          SOURCE: "Geçerli öncelik grubunun geldiği düzey: Sipariş · Proje · Müşteri · Yok",
          "Origin": "Baz: Baz senaryodan okunur · Senaryo farkı: Baz'daki değer bu senaryoda değiştirildi · Senaryo: yalnız bu senaryoda"}
# Girilen değerin satırı (senaryo + kayıt başına tek): Baz senaryoda "Kaynağı" Baz
_ENTERED = (f"SELECT q.RecordId AS JoinId, q.[{rules.FIELD}], CASE WHEN :pr_is_base = 1 THEN N'{rules.BASE}' ELSE q.Origin END AS Origin, COALESCE(q.OwnId, q.DiffId) AS StoredId, "
            f"q.OverriddenFields, q.BaseValues, q.CanRestore FROM ({rules.resolved_sql(':pr_sid', ':pr_base')}) q WHERE q.[Level] = N'@@LEVEL@@'")



def _entered(level: str) -> str:
    return _ENTERED.replace("@@LEVEL@@", level)


def _binds(ctx: SourceContext, is_base: bool = True) -> list[sa.BindParameter]:
    scenario = cache.scenario_row(ctx.session, ctx.scenario_id)
    out = [sa.bindparam("pr_sid", ctx.scenario_id, sa.Integer()), sa.bindparam("pr_base", cache.base_of(ctx.session, scenario), sa.Integer())]
    return [*out, sa.bindparam("pr_is_base", 1 if scenario["IsBase"] else 0, sa.Integer())] if is_base else out


def _text(sql: str, types: dict, name: str, ctx: SourceContext) -> sa.FromClause:
    return sa.text(sql).bindparams(*_binds(ctx, ":pr_is_base" in sql)).columns(*[sa.column(n, t) for n, t in types.items()]).subquery(name)


def _derived(name: str, master: ListDefinition, sql: str, types: dict, shown: tuple[str, ...], title: str, slug: str, *, where=None, labels: dict | None = None,
             keys: tuple[str, ...] = (), filters: tuple[str, ...] = ()) -> ListDefinition:
    """Ana veri listesinden türetilen liste: ek kolonlar kimlikle birleşir; `where`: satır süzmesi (ör. yalnız açık sipariş)."""
    def build(extra: sa.FromClause) -> sa.FromClause:
        src = from_master(master, extra, f"{name}_m".replace("-", "_"))
        return src if where is None else sa.select(*src.c).where(where(src)).subquery(name.replace("-", "_"))

    extra_fields = tuple(f for f in types if f not in ("JoinId", "StoredId", "OverriddenFields", "BaseValues", "CanRestore"))
    fields = master_fields(master, shown, extra=extra_fields)
    return ListDefinition(
        name=name, table=master.table, function=FUNCTION, versioned=False, title=title, file_slug=slug,
        source=build(skeleton(types, f"{name}_x".replace("-", "_"))), source_factory=lambda ctx: build(_text(sql, types, f"{name}_x".replace("-", "_"), ctx)),
        fields=fields, default_visible=shown, default_sort=master.default_sort, server_values=master.server_values,
        decimals={f: d for f, d in master.decimals.items() if f in fields}, percent=frozenset(f for f in master.percent if f in fields),
        unit_field=master.unit_field, unit_decimals=frozenset(f for f in master.unit_decimals if f in fields),
        values={**master.values, "Origin": _ORIGINS, SOURCE: _SOURCES, rules.FIELD: list(rules.GROUPS), EFFECTIVE: list(rules.GROUPS)},
        labels={**master.labels, **_LABELS, **(labels or {})}, notes={**master.notes, **_NOTES},
        key_fields=tuple(k for k in ("StoredId", "OverriddenFields", "BaseValues", "CanRestore", *keys) if k in types or k in keys),
        filter_only=("Id", *filters), related_table=master.related_table,
    )


_CUSTOMER, _PROJECT = BY_NAME["master-customer"], BY_NAME["transaction-project"]
_ORDER, _FORECAST = BY_NAME["transaction-sales-order"], BY_NAME["transaction-forecast"]

CUSTOMERS = _derived("priority-customers", _CUSTOMER, _entered(rules.CUSTOMER), _ENTRY, ("Code", "Name", "Priority", rules.FIELD, "Origin"),
                     "Öncelik yönetimi · Müşteri", "oncelik-musteri", labels={"Code": "Müşteri", "Name": "Ad"})
PROJECTS = _derived("priority-projects", _PROJECT, _entered(rules.PROJECT), _ENTRY, ("Code", "Name", "Priority", rules.FIELD, "Origin"),
                    "Öncelik yönetimi · Proje", "oncelik-proje", labels={"Code": "Proje", "Name": "Ad"})

# Sipariş: girilen değer ve kaynağı + hiyerarşiden hesaplanan iki alan
_ORDER_SQL = (f"SELECT o.SalesOrderLineId AS JoinId, e.[{rules.FIELD}], o.{EFFECTIVE}, o.{SOURCE}, e.Origin, e.StoredId, e.OverriddenFields, e.BaseValues, e.CanRestore "
              f"FROM ({rules.orders_sql(':pr_sid', ':pr_base')}) o LEFT JOIN ({_entered(rules.ORDER)}) e ON e.JoinId = o.SalesOrderLineId")
_ORDER_TYPES = {"JoinId": sa.BigInteger(), rules.FIELD: sa.Integer(), **_COMPUTED, **{k: v for k, v in _ENTRY.items() if k not in ("JoinId", rules.FIELD)}}
_ORDER_SHOWN = ("LocationCode", "OrderNo", "LineNo", "CustomerCode", "ProjectCode", "MaterialCode", "RequestedDate", "OpenQuantity", "Priority", rules.FIELD, EFFECTIVE, SOURCE, "Origin")
ORDERS = _derived("priority-orders", _ORDER, _ORDER_SQL, _ORDER_TYPES, _ORDER_SHOWN, "Öncelik yönetimi · Sipariş", "oncelik-siparis",
                  where=lambda src: src.c.OpenQuantity > 0, keys=("CustomerId", "ProjectId"))      # kartlar müşteri ve proje koduyla süzer; kimlikler satırda döner

_FORECAST_SQL = f"SELECT f.ForecastId AS JoinId, f.{EFFECTIVE}, f.{SOURCE} FROM ({rules.forecasts_sql(':pr_sid', ':pr_base')}) f"
_FORECAST_TYPES = {"JoinId": sa.BigInteger(), **_COMPUTED}
_FORECAST_SHOWN = ("LocationCode", "MaterialCode", "CustomerCode", "ProjectCode", "Period", "Quantity", "Uom", EFFECTIVE, SOURCE)
FORECASTS = _derived("priority-forecasts", _FORECAST, _FORECAST_SQL, _FORECAST_TYPES, _FORECAST_SHOWN, "Öncelik yönetimi · Tahmin", "oncelik-tahmin",
                     keys=("CustomerId", "ProjectId"))

PRIORITY_LISTS = (CUSTOMERS, PROJECTS, ORDERS, FORECASTS)


def with_priority(master: ListDefinition, sql: str) -> ListDefinition:
    """İşlem verisi listesine (Satış siparişi, Tahmin) hesaplanan iki alanı ekler: kapalı gelir, seçili senaryoya göre hesaplanır (K-195). Liste
    öteki özelliklerini (manuel değer, ilişkili alanlar, Excel) olduğu gibi korur; yalnız kaynağı istekte kurulur."""
    types = {"JoinId": sa.BigInteger(), **_COMPUTED}
    name = master.name.replace("-", "_")

    def build(extra: sa.FromClause) -> sa.FromClause:
        m = master.source
        return sa.select(*m.c, *[c for c in extra.c if c.name != "JoinId"]).select_from(m.outerjoin(extra, extra.c.JoinId == m.c.Id)).subquery(f"{name}_pr")

    return replace(master, source=build(skeleton(types, f"{name}_x")), source_factory=lambda ctx: build(_text(sql, types, f"{name}_x", ctx)),
                   fields=(*master.fields, EFFECTIVE, SOURCE), values={**master.values, SOURCE: _SOURCES, EFFECTIVE: list(rules.GROUPS)},
                   labels={**master.labels, EFFECTIVE: _LABELS[EFFECTIVE], SOURCE: _LABELS[SOURCE]}, notes={**master.notes, EFFECTIVE: _NOTES[EFFECTIVE], SOURCE: _NOTES[SOURCE]})


TRANSACTION_WITH_PRIORITY = {
    "transaction-sales-order": with_priority(_ORDER, f"SELECT o.SalesOrderLineId AS JoinId, o.{EFFECTIVE}, o.{SOURCE} FROM ({rules.orders_sql(':pr_sid', ':pr_base')}) o"),
    "transaction-forecast": with_priority(_FORECAST, _FORECAST_SQL),
}
