"""Validasyon listeleri (ekran 02 ve 27, fonksiyon 04 ve 100; K-134, K-136, K-139).

Kayıtlar tablo başınadır: satır no ve kaydın alanları tablonun `stg` satırından gelir; ilk kolonlar Sorun (satırın bulguları) ve Sınıf
(en ağır). `RuleIds` (",12,15,") kurala göre süzmek içindir: çekmecede Bulgular'daki kurala tıklayınca. Excel'i "Hatalı kayıtları indir"dir (K-91).
Kural listesinde yapısal kontroller görünmez (K-139).
"""
import sqlalchemy as sa

from app.integration.contract import ENTITIES, stg_columns
from app.validation import catalog as cat
from app.validation.sqlkit import labels as field_labels
from db.models import metadata

from .definition import ListDefinition

FINDING = metadata.tables["adm.ValidationFinding"]
RULE = metadata.tables["adm.ValidationRule"]
SEVERITIES = list(cat.SEVERITIES)


def _records_source(entity: str) -> tuple[sa.Subquery, list[str]]:
    s = metadata.tables[f"stg.{entity}"]
    rank = sa.case((FINDING.c.Severity == cat.ERROR, 1), (FINDING.c.Severity == cat.WARNING, 2), else_=3)
    problem = sa.func.concat(sa.func.coalesce(FINDING.c.FieldName + sa.literal(": ", sa.Unicode), sa.literal("", sa.Unicode)), FINDING.c.Message)
    agg = (sa.select(FINDING.c.StagingRowId, sa.func.min(rank).label("Rank"),
                     sa.func.string_agg(sa.cast(problem, sa.Unicode(None)), sa.literal_column("N' · '")).label("Problems"),
                     sa.func.concat(sa.literal(",", sa.Unicode), sa.func.string_agg(sa.cast(FINDING.c.ValidationRuleId, sa.Unicode(20)), sa.literal_column("N','")),
                                    sa.literal(",", sa.Unicode)).label("RuleIds"))
           .where(FINDING.c.EntityName == entity, FINDING.c.StagingRowId.is_not(None)).group_by(FINDING.c.StagingRowId).subquery("agg"))
    names = [c.name for c in stg_columns(entity)]
    worst = sa.case((agg.c.Rank == 1, cat.ERROR), (agg.c.Rank == 2, cat.WARNING), else_=cat.INFO).label("Severity")
    source = (sa.select(s.c.StagingRowId.label("Id"), agg.c.Problems, worst, s.c.SourceRowNo.label("RowNo"), *[s.c[n] for n in names], agg.c.RuleIds)
              .select_from(s.join(agg, agg.c.StagingRowId == s.c.StagingRowId)).where(s.c.IsCurrent == sa.true()).subquery(f"records_{entity}"))
    return source, names


def _decimals(entity: str) -> dict[str, int]:
    return {c.name: min(getattr(c.type, "scale", 0) or 0, 4) for c in stg_columns(entity) if isinstance(c.type, sa.Numeric) and not isinstance(c.type, sa.Integer)}


def records_list(entity) -> ListDefinition:
    source, names = _records_source(entity.table)
    labels = {**{n: l for n, l in field_labels(entity.table).items() if not n.startswith("Additional")}, "RowNo": "Satır", "Problems": "Sorun", "Severity": "Sınıf",
              "RuleIds": "Kurallar"}
    fields = ("Problems", "Severity", "RowNo", *names, "RuleIds")
    return ListDefinition(
        name=f"validation-records-{entity.table}", table=f"stg.{entity.table}", title=f"Hatalı kayıtlar · {entity.name}",
        file_slug=f"hatali-kayitlar-{entity.slug}", function=4, versioned=False, source=source, fields=fields,
        default_visible=tuple(f for f in fields if f != "RuleIds"), default_sort=(("RowNo", "asc"),),
        labels=labels, values={"Severity": SEVERITIES}, decimals=_decimals(entity.table),
    )


_EDITABLE = [(e, r.code) for r in cat.catalog() for e in [r.table] if r.editable]


def _editable() -> sa.ColumnElement:
    by_table: dict[str, list[str]] = {}
    for table, code in _EDITABLE:
        by_table.setdefault(table, []).append(code)
    builtin = sa.or_(*[sa.and_(RULE.c.EntityName == t, RULE.c.Code.in_(codes)) for t, codes in by_table.items()])
    return sa.case((RULE.c.Kind == cat.USER_KIND, True), (builtin, True), else_=False).label("Editable")


_rules_source = (sa.select(RULE.c.Id, RULE.c.EntityName, RULE.c.Code, RULE.c.Name.label("RuleName"), RULE.c.IsCustomized, _editable(),
                           RULE.c.ConditionText, RULE.c.Severity, RULE.c.Message, RULE.c.Kind, RULE.c.CheckType, RULE.c.IsActive,
                           sa.case(*[(RULE.c.EntityName == e.table, e.name) for e in ENTITIES], else_=RULE.c.EntityName).label("EntityLabel"),
                           sa.case(*[(RULE.c.EntityName == e.table, i) for i, e in enumerate(ENTITIES, 1)], else_=99).label("EntityOrder"))
                 .where(RULE.c.Kind != cat.STRUCTURAL_KIND)  # yapısal kontroller görünmez, çalışır (K-139)
                 .subquery("validation_rules"))

VALIDATION_RULES = ListDefinition(
    name="validation-rules", table="adm.ValidationRule", title="Validasyon kuralları", file_slug="validasyon-kurallari", function=100, versioned=False,
    source=_rules_source,
    fields=("EntityLabel", "RuleName", "ConditionText", "Severity", "Message", "Kind", "IsActive", "CheckType", "EntityOrder", "EntityName", "Code"),
    default_visible=("EntityLabel", "RuleName", "ConditionText", "Severity", "Message", "Kind", "IsActive"),
    default_sort=(("EntityOrder", "asc"), ("Code", "asc")),
    key_fields=("Id", "EntityName", "Kind", "Severity", "IsActive", "Code", "IsCustomized", "Editable"),
    labels={"EntityLabel": "Tablo", "RuleName": "Kural", "ConditionText": "Koşul", "Severity": "Sınıf", "Message": "Mesaj", "Kind": "Tür",
            "IsActive": "Aktif", "CheckType": "Kontrol türü", "EntityOrder": "Yükleme sırası", "EntityName": "Teknik tablo adı", "Code": "Kod"},
    values={"Severity": SEVERITIES, "Kind": list(cat.KINDS), "CheckType": list(cat.CHECK_TYPES), "EntityLabel": [e.name for e in ENTITIES]},
)

RECORDS_LISTS = tuple(records_list(e) for e in ENTITIES)
