"""Hazır kural kataloğu docs/06 fonksiyon 04 tablosuyla birebir (K-137, K-139); koşul çevirisi (K-136, K-139). Veritabanı gerekmez."""
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

from app.integration.contract import ENTITIES, stg_columns
from app.validation import catalog as cat, conditions
from app.validation.conditions import Condition, ConditionError
from app.validation.sqlkit import alias, current

DOCS06 = (Path(__file__).resolve().parents[1] / "docs" / "06-fonksiyonlar.md").read_text(encoding="utf-8")
TYPE_OF = {"Yapısal": cat.STRUCTURAL, "Mantıksal": cat.LOGICAL, "Küme": cat.LOGICAL, "Tablolar arası": cat.CROSS}


def docs_rules() -> list[dict]:
    start = DOCS06.index("| KOD | TABLO | AD | KOŞUL | SINIF | TÜR | DÜZENLENİR | OKUNAN |")
    rows = []
    for line in DOCS06[start:].splitlines()[2:]:
        if not line.startswith("|"):
            break
        code, table, name, condition, severity, kind, editable, reads = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip()[1:-1])]
        rows.append(dict(code=code, table=table, name=name, condition=condition, severity=severity, kind=kind, editable=editable,
                         reads=tuple(r.strip() for r in reads.split(",") if r.strip())))
    return rows


EDITABLE = {"Evet": True, "Sınıf, aktiflik": False, "Kilitli": False}


def test_every_documented_rule_is_in_the_catalog():
    by_key = cat.by_key()
    codes = {}
    for r in cat.catalog():
        codes.setdefault(r.code, []).append(r)
    for d in docs_rules():
        found = codes.get(d["code"])
        assert found, d["code"]
        if d["table"] != "Hepsi":
            assert [r.table for r in found] == [d["table"]], d["code"]
            rule = by_key[(d["table"], d["code"])]
            assert (rule.title, rule.condition, rule.severity, rule.check_type, rule.reads, rule.group, rule.editable) == \
                   (d["name"], d["condition"], d["severity"], TYPE_OF[d["kind"]], d["reads"], d["kind"] == "Küme", EDITABLE[d["editable"]]), d["code"]
        else:
            assert {(r.title, r.severity, r.check_type, r.editable) for r in found} == \
                   {(d["name"], d["severity"], TYPE_OF[d["kind"]], EDITABLE[d["editable"]])}, d["code"]
            assert {r.kind for r in found} == {cat.STRUCTURAL_KIND if d["kind"] == "Yapısal" else cat.BUILTIN_KIND}, d["code"]


def test_catalog_has_nothing_undocumented():
    assert {r.code for r in cat.catalog()} == {d["code"] for d in docs_rules()}


def test_structural_rules_are_on_every_table_and_locked():
    for e in ENTITIES:
        codes = {r.code for r in cat.catalog() if r.table == e.table and r.kind == cat.STRUCTURAL_KIND}
        assert {"STR.TYPE", "STR.LENGTH", "STR.REQUIRED"} <= codes, e.table


def test_negative_field_list_matches_docs():
    text = DOCS06[DOCS06.index("**Negatif değer alanları (ALL.NEGATIVE):**"):].split("\n", 1)[0]
    body = text.split(":**", 1)[1].split("Dışarıda:")[0]
    documented = {}
    for part in body.split("·"):
        table, fields = part.split(":", 1)
        documented[table.strip()] = tuple(f.strip().rstrip(".") for f in fields.split(","))
    assert documented == cat.NEGATIVE_FIELDS
    for table, fields in cat.NEGATIVE_FIELDS.items():
        assert not {"RemainingOverTimeYear", "RemainingOverTimeMonth", "Priority", "AlternativePriority"} & set(fields), table


def test_every_check_compiles_against_the_contract():
    """Kural koşulları gerçek stg kolonlarına bağlanır; yanlış alan adı burada düşer."""
    for rule in cat.catalog():
        for check in rule.checks:
            t = alias(rule.table)
            sql = sa.select(t.c.StagingRowId).where(current(t), check.where(t))
            sql.compile(dialect=mssql.dialect())
            if check.field:
                assert check.field in t.c, (rule.code, check.field)
        if rule.groups:  # editörle ifade edilen koşul geçerlidir (K-139)
            conditions.check(rule.table, [list(g) for g in rule.groups])
            sa.select(alias(rule.table).c.StagingRowId).where(conditions.where(rule.table, [list(g) for g in rule.groups])(alias(rule.table))).compile(dialect=mssql.dialect())
        assert rule.runs or rule.kind == cat.STRUCTURAL_KIND, rule.code
        assert all(r in {e.table for e in ENTITIES} for r in rule.reads), rule.code


def test_after_rules_fields_come_from_boşsa():
    required = {(r.table, c.field) for r in cat.catalog() if r.code == "STR.REQUIRED" for c in r.checks}
    assert ("Location", "Type") in required and ("Routing", "ResourceNumber") in required and ("Resource", "CapacityUnit") in required
    assert ("MaterialSupplier", "LeadTimeBasis") not in required  # yalnız tedarik süresi doluysa (MS.NO_BASIS)
    assert all(t != "MaterialSupplier" or f != "LeadTimeBasis" for t, f in required)


def test_strong_components_find_only_real_cycles():
    graph = {"A": ["B"], "B": ["C"], "C": ["A"], "D": ["E"], "E": []}
    comp = cat._strong_components(graph)
    assert comp["A"] == comp["B"] == comp["C"] and "D" not in comp and "E" not in comp


# ------------------------------------------------------------------ koşullar (K-136)

def sql_of(entity: str, groups) -> str:
    t = alias(entity)
    return str(sa.select(t.c.StagingRowId).where(conditions.where(entity, groups)(t)).compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True}))


def test_groups_are_and_inside_or_between():
    sql = sql_of("Material", [[Condition("MinLot", "Boş değil"), Condition("MaxLot", "Boş")], [Condition("LotMultiple", ">", compare_field="MaxLot")]])
    assert "material.[MinLot] IS NOT NULL AND material.[MaxLot] IS NULL OR material.[LotMultiple] > material.[MaxLot]" in sql


@pytest.mark.parametrize("op, value, fragment", [
    ("=", "5", "= 5"), ("≠", "5", "!= 5"), (">", "5", "> 5"), ("<", "5", "< 5"), ("≥", "1.234,5", ">= 1234.5"), ("≤", "0,5", "<= 0.5"),
    ("Listede", "1, 2,3", "IN (1, 2, 3)"),
])
def test_number_operators(op, value, fragment):
    assert fragment in sql_of("Material", [[Condition("SafetyStock", op, value)]])


def test_text_operators_escape_like():
    assert "LIKE N'%a[%]b%'" in sql_of("Material", [[Condition("Name", "İçerir", "a%b")]])
    assert "LIKE N'HAM[_]%'" in sql_of("Material", [[Condition("Code", "İle başlar", "HAM_")]])


def test_values_are_bound_not_inlined():
    t = alias("Material")
    compiled = sa.select(t.c.StagingRowId).where(conditions.where("Material", [[Condition("Name", "=", "x'; DROP TABLE y; --")]])(t)).compile(dialect=mssql.dialect())
    assert "DROP TABLE" not in str(compiled) and "x'; DROP TABLE y; --" in compiled.params.values()


def test_dates_and_bools_parse():
    assert conditions._parse("date", "01.02.2027") == date(2027, 2, 1) == conditions._parse("date", "2027-02-01")
    assert conditions._parse("bool", "Evet") is True and conditions._parse("number", "1.234,50") == Decimal("1234.50")


@pytest.mark.parametrize("c, problem", [
    (Condition("Yok", "=", "1"), "Alan yok"), (Condition("MinLot", "Benzer", "1"), "Operatör yok"), (Condition("MinLot", "Eşittir", "1"), "Operatör yok"),
    (Condition("MinLot", "İçerir", "1"), "yalnız metin"), (Condition("MinLot", "=", None), "Değer boş"),
    (Condition("MinLot", "=", "abc"), "tipine uymuyor"), (Condition("MinLot", ">", compare_field="Name"), "tipi uyumlu"),
    (Condition("StagingRowId", "Boş değil"), "Alan yok"), (Condition("MinLot", "Dolu"), "Operatör yok"),
])
def test_invalid_conditions(c, problem):
    with pytest.raises(ConditionError, match=problem):
        conditions.validate("Material", c)


def test_sentence_reads_like_the_screen():
    groups = [[Condition("MinLot", "Boş değil"), Condition("MaxLot", "Boş")], [Condition("LotMultiple", ">", compare_field="MaxLot")]]
    assert conditions.sentence("Material", groups) == "Minimum lot boş değil ve Maksimum lot boş veya Lot katı > Maksimum lot"


def test_not_equal_includes_empty():
    """≠ boş değeri de kapsar (K-139): boş bayrak "1 değil" sayılır."""
    assert "material.[SafetyStock] IS NULL OR material.[SafetyStock] != 5" in sql_of("Material", [[Condition("SafetyStock", "≠", "5")]])


def test_operators_are_symbols_then_names():
    assert conditions.OPERATORS == ("=", "≠", ">", "<", "≥", "≤", "İçerir", "İle başlar", "Listede", "Boş", "Boş değil")


def test_builtin_names_and_messages_are_user_language():
    for r in cat.catalog():
        assert "arsayılan" not in r.title + r.message + r.condition, r.code
        if r.kind != cat.STRUCTURAL_KIND:
            assert not re.search(r"\b[A-Z][a-z]+[A-Z]\w*", r.title + " " + r.condition), (r.code, r.title, r.condition)


def test_condition_fields_exclude_system_columns():
    names = set(conditions.columns("Material"))
    assert not {"StagingRowId", "ImportBatchId", "IsCurrent", "RowStatus"} & names and names <= {c.name for c in stg_columns("Material")}
