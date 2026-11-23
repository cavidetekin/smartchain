"""Model kısıtları listesi (ekran 31, fonksiyon 103; K-189): her güncel kaynak grubu bir satır (kaydı olmayan dahil), senaryonun çözümlenmiş
değerleriyle (K-176). Satırın kimliği kaynak grubunun kimliğidir; yazma uçları (`/api/model-constraints/resource-groups`) bu kimlikle çalışır.

Liste ana verinin Kaynak grubu listesinden türetilir (`capacity.from_master`): ana verideki bütün alanlar ve İlişkili alanlar (Lokasyon)
Alanlar'dan açılır; Standart'ta Lokasyon · Kaynak grubu · Ad · Kritik · Kapasite birimi · Kısıtsız kapasite çarpanı · Hedef doluluk (%) · Kaynağı.
"""
import sqlalchemy as sa

from app import modelconstraints as rules
from app.params import resolve
from app.periods import cache

from .capacity import ERP, from_master, master_fields
from .definition import ListDefinition, SourceContext
from .master_data import BY_NAME
from .period_tables import skeleton

FUNCTION = 103
_MASTER = BY_NAME["master-resource-group"]
_EXTRA = {"JoinId": sa.BigInteger(), rules.FACTOR: sa.Numeric(9, 4), rules.TARGET: sa.Numeric(6, 2), "Origin": sa.Unicode(20), "StoredId": sa.BigInteger(),
          "OverriddenFields": sa.Unicode(400), "BaseValues": sa.UnicodeText(), "CanRestore": sa.Boolean()}
# Senaryo + grup başına tek satır (`rules.resolved_sql`): senaryonun kendi kaydı ile Baz kaydı aynı gruptaysa senaryonun değeri, "Senaryo farkı"
_SQL = (f"SELECT x.ResourceGroupId AS JoinId, x.[{rules.FACTOR}], x.[{rules.TARGET}], CASE WHEN :mc_is_base = 1 THEN N'{resolve.BASE}' ELSE x.Origin END AS Origin, "
        f"COALESCE(x.OwnId, x.DiffId) AS StoredId, x.OverriddenFields, x.BaseValues, x.CanRestore FROM ({rules.resolved_sql(':mc_sid', ':mc_base')}) x")


def _source(ctx: SourceContext) -> sa.FromClause:
    scenario = cache.scenario_row(ctx.session, ctx.scenario_id)
    extra = sa.text(_SQL).bindparams(sa.bindparam("mc_sid", ctx.scenario_id, sa.Integer()), sa.bindparam("mc_base", cache.base_of(ctx.session, scenario), sa.Integer()),
                                     sa.bindparam("mc_is_base", 1 if scenario["IsBase"] else 0, sa.Integer())
                                     ).columns(*[sa.column(n, t) for n, t in _EXTRA.items()]).subquery("mc_values")
    return from_master(_MASTER, extra, "mc")


_SHOWN = ("LocationCode", "Code", "Name", "IsCritical", "CapacityUnit", rules.FACTOR, rules.TARGET, "Origin")   # Lokasyon kodun solunda (K-189)
_FIELDS = master_fields(_MASTER, _SHOWN, extra=(rules.FACTOR, rules.TARGET, "Origin"))

RESOURCE_GROUP_CONSTRAINTS = ListDefinition(
    name="model-constraints-resource-groups", table="core.ResourceGroup", function=FUNCTION, versioned=False,
    title="Model kısıtları · Kaynak grubu", file_slug="model-kisitlari-kaynak-grubu",
    source=from_master(_MASTER, skeleton(_EXTRA, "mc_values"), "mc"), source_factory=_source,
    fields=_FIELDS, default_visible=_SHOWN, default_sort=(("Code", "asc"),),
    server_values=_MASTER.server_values | frozenset({"Type", "CapacityUnit"}),
    decimals={**{f: d for f, d in _MASTER.decimals.items() if f in _FIELDS}, **rules.DECIMALS},
    values={**_MASTER.values, "Origin": [resolve.BASE, resolve.DIFF, resolve.OWN]},
    labels={**_MASTER.labels, "Code": "Kaynak grubu", "Name": "Ad", "IsCritical": "Kritik", "CapacityUnit": "Kapasite birimi", **rules.LABELS, "Origin": "Kaynağı", "StoredId": "Saklanan satır", "OverriddenFields": "Senaryoda değişen alanlar",
            "BaseValues": "Baz değerleri", "CanRestore": "Senaryo farkı kaldırılabilir"},
    notes={rules.FACTOR: "Kaynak kısıtı Kısıtsız olan senaryoda grubun dönem üst sınırı = kullanılabilir kapasite × çarpan; boşsa sınır yok. Yalnız kritik grupta",
           rules.TARGET: "Kesin sınır değil, hedef: \"Hedef doluluğun üstü\" hedefinin eşiği; boşsa hedef yok. Yalnız kritik grupta",
           "Origin": "Baz: Baz senaryodan okunur · Senaryo farkı: Baz'daki değer bu senaryoda değiştirildi · Senaryo: yalnız bu senaryoda"},
    key_fields=("StoredId", "OverriddenFields", "BaseValues", "CanRestore", "LocationCode"), filter_only=("Id",),
    related_table="ResourceGroup",
)
assert ERP not in RESOURCE_GROUP_CONSTRAINTS.values["Origin"]   # bu listede ERP satırı yok

MODEL_CONSTRAINT_LISTS = (RESOURCE_GROUP_CONSTRAINTS,)
