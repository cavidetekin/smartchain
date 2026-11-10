"""Validasyon listeleri (ekran 02 ve 27, fonksiyon 04 ve 100; K-134, K-136, K-139, K-140, K-143).

Kayıtlar tablo başına iki listedir, ikisi de işlenmiş katmanın (`prc`, kurallar uygulanmış) bütün satırlarını okur:
`validation-records-<tablo>` Bulgulu satırlar içindir, ilk kolonlar Sorun (satırın bulguları) ve Sınıf (en ağır);
`validation-data-<tablo>` Kuralla değişenler ve Tüm satırlar içindir, Sorun ve Sınıf en sonda. Teknik alanlar yalnız süzmede
kullanılır, kolon değildir (`filter_only`): `HasFindings`, `HasEffects` (üç seçenek) ve `RuleIds` (",12,15,"; Bulgular'da kurala
tıklayınca). "Değiştiren kural" kuralla değişen hücrelerin kural adlarıdır; gizli `RuleEffects` hücre izinin ipucunu taşır
(alan, sıra, kural, ham değer). Excel'i "Hatalı kayıtları indir"dir (K-91). Kural listesinde yapısal kontroller görünmez (K-139).
"""
import sqlalchemy as sa

from app.integration.contract import ENTITIES, stg_columns
from app.validation import catalog as cat
from app.validation.sqlkit import labels as field_labels
from db.models import metadata

from .definition import ListDefinition

FINDING = metadata.tables["adm.ValidationFinding"]
RULE = metadata.tables["adm.ValidationRule"]
DATA_RULE = metadata.tables["adm.DataRule"]
EFFECT = metadata.tables["adm.DataRuleEffect"]
UNIT, RECORD = "", ""  # RuleEffects: alan, sıra, kural, ham değer; hücreler arası ayraç
SEVERITIES = list(cat.SEVERITIES)


def _records_source(entity: str) -> tuple[sa.Subquery, list[str]]:
    s = metadata.tables[f"prc.{entity}"]
    rank = sa.case((FINDING.c.Severity == cat.ERROR, 1), (FINDING.c.Severity == cat.WARNING, 2), else_=3)
    problem = sa.func.concat(sa.func.coalesce(FINDING.c.FieldName + sa.literal(": ", sa.Unicode), sa.literal("", sa.Unicode)), FINDING.c.Message)
    agg = (sa.select(FINDING.c.StagingRowId, sa.func.min(rank).label("Rank"),
                     sa.func.string_agg(sa.cast(problem, sa.Unicode(None)), sa.literal_column("N' · '")).label("Problems"),
                     sa.func.concat(sa.literal(",", sa.Unicode), sa.func.string_agg(sa.cast(FINDING.c.ValidationRuleId, sa.Unicode(20)), sa.literal_column("N','")),
                                    sa.literal(",", sa.Unicode)).label("RuleIds"))
           .where(FINDING.c.EntityName == entity, FINDING.c.StagingRowId.is_not(None)).group_by(FINDING.c.StagingRowId).subquery("agg"))
    piece = sa.func.concat(EFFECT.c.FieldName, sa.literal(UNIT, sa.Unicode), DATA_RULE.c.Seq, sa.literal(UNIT, sa.Unicode), DATA_RULE.c.Name,
                           sa.literal(UNIT, sa.Unicode), sa.func.coalesce(EFFECT.c.RawValue, sa.literal("", sa.Unicode)))
    effects = (sa.select(EFFECT.c.StagingRowId, sa.func.string_agg(sa.cast(piece, sa.Unicode(None)), sa.literal_column(f"N'{RECORD}'")).label("RuleEffects"))
               .select_from(EFFECT.join(DATA_RULE, DATA_RULE.c.Id == EFFECT.c.DataRuleId))
               .where(EFFECT.c.EntityName == entity).group_by(EFFECT.c.StagingRowId).subquery("effects"))
    distinct = (sa.select(EFFECT.c.StagingRowId, DATA_RULE.c.Name).select_from(EFFECT.join(DATA_RULE, DATA_RULE.c.Id == EFFECT.c.DataRuleId))
                .where(EFFECT.c.EntityName == entity).distinct().subquery("changed_by"))
    rule_names = (sa.select(distinct.c.StagingRowId, sa.func.string_agg(sa.cast(distinct.c.Name, sa.Unicode(None)), sa.literal_column("N', '")).label("RuleNames"))
                  .group_by(distinct.c.StagingRowId).subquery("rule_names"))
    names = [c.name for c in stg_columns(entity)]
    worst = sa.case((agg.c.Rank == 1, cat.ERROR), (agg.c.Rank == 2, cat.WARNING), (agg.c.Rank == 3, cat.INFO), else_=sa.null()).label("Severity")
    has_findings = sa.cast(sa.case((agg.c.StagingRowId.is_not(None), 1), else_=0), sa.Boolean).label("HasFindings")
    has_effects = sa.cast(sa.case((effects.c.StagingRowId.is_not(None), 1), else_=0), sa.Boolean).label("HasEffects")
    source = (sa.select(s.c.StagingRowId.label("Id"), agg.c.Problems, worst, s.c.SourceRowNo.label("RowNo"), *[s.c[n] for n in names], agg.c.RuleIds,
                        effects.c.RuleEffects, rule_names.c.RuleNames, has_findings, has_effects)
              .select_from(s.outerjoin(agg, agg.c.StagingRowId == s.c.StagingRowId).outerjoin(effects, effects.c.StagingRowId == s.c.StagingRowId)
                           .outerjoin(rule_names, rule_names.c.StagingRowId == s.c.StagingRowId))
              .subquery(f"records_{entity}"))
    return source, names


def _decimals(entity: str) -> dict[str, int]:
    return {c.name: min(getattr(c.type, "scale", 0) or 0, 4) for c in stg_columns(entity) if isinstance(c.type, sa.Numeric) and not isinstance(c.type, sa.Integer)}


FILTER_ONLY = ("RuleIds", "HasFindings", "HasEffects")  # teknik: yalnız süzme (K-143)


def records_list(entity, data_first: bool = False) -> ListDefinition:
    """data_first: Kuralla değişenler ve Tüm satırlar için; Sorun ve Sınıf en sonda (K-143)."""
    source, names = _records_source(entity.table)
    labels = {**{n: l for n, l in field_labels(entity.table).items() if not n.startswith("Additional")}, "RowNo": "Satır", "Problems": "Sorun", "Severity": "Sınıf",
              "RuleNames": "Değiştiren kural", "RuleEffects": "Kural izi", "RuleIds": "Kurallar", "HasFindings": "Bulgulu", "HasEffects": "Kuralla değişti"}
    fields = ("RowNo", *names, "RuleNames", "Problems", "Severity") if data_first else ("Problems", "Severity", "RowNo", *names, "RuleNames")
    kind = "data" if data_first else "records"
    return ListDefinition(
        name=f"validation-{kind}-{entity.table}", table=f"prc.{entity.table}",
        title=f"{'Staging verisi' if data_first else 'Hatalı kayıtlar'} · {entity.name}",
        file_slug=f"{'staging-verisi' if data_first else 'hatali-kayitlar'}-{entity.slug}", function=4, versioned=False, source=source, fields=fields,
        default_visible=fields, default_sort=(("RowNo", "asc"),), filter_only=FILTER_ONLY,
        labels=labels, values={"Severity": SEVERITIES}, decimals=_decimals(entity.table),
        key_fields=("RuleEffects",),  # hücre izi her satırda döner, kolon değildir (K-140)
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
    fields=("EntityLabel", "RuleName", "ConditionText", "Severity", "Message", "Kind", "CheckType", "IsActive", "EntityOrder", "EntityName", "Code"),
    default_visible=("EntityLabel", "RuleName", "ConditionText", "Severity", "Message", "Kind", "CheckType", "IsActive"),  # Kontrol türü açık (K-146)
    default_sort=(("EntityOrder", "asc"), ("Code", "asc")),
    key_fields=("Id", "EntityName", "Kind", "Severity", "IsActive", "Code", "IsCustomized", "Editable"),
    labels={"EntityLabel": "Tablo", "RuleName": "Kural", "ConditionText": "Koşul", "Severity": "Sınıf", "Message": "Mesaj", "Kind": "Tür",
            "IsActive": "Aktif", "CheckType": "Kontrol türü", "EntityOrder": "Yükleme sırası", "EntityName": "Teknik tablo adı", "Code": "Kod"},
    values={"Severity": SEVERITIES, "Kind": list(cat.KINDS), "CheckType": list(cat.CHECK_TYPES), "EntityLabel": [e.name for e in ENTITIES]},
)

RECORDS_LISTS = tuple(records_list(e, data_first) for e in ENTITIES for data_first in (False, True))
