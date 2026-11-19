"""Veri kalitesi kontrolü (fonksiyon 20, K-174): takipli Uyarı kuralları `core`'da, Smartchain kontrolleri, birleştirme, önem.

Kurallar `sqlkit.core_layer()` içinde çalışır: katalogdaki koşullar ve tablolar arası kurallar `core`'un `prc` biçimli izdüşümünü okur.
`core`'da kodu kaybolan "bağlı kayıt bulunamadı" kuralı (RES.REF_SUBCONTRACTOR) işlenmiş staging'de çalışır, bulgu kaydın `core` karşılığına iş
anahtarıyla bağlanır. Bulgular geçici tabloya yazılır, sonra uyarılarla birleşir: ilk kez çıkan Yeni, önceden olan Açık, Yok sayıldı korunur
(kaydı yok saymadan sonra değiştiyse Açık), çıkmayan uyarı silinir (yok sayılmış olsa da); yalnız kontrolün kapsamındaki kurallar ve tablolarda.
"""
import logging
from collections.abc import Callable
from datetime import date

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.integration.contract import ENTITIES
from app.integration.structural import key_fields
from app.validation import catalog as cat, conditions, engine, sqlkit
from app.validation.sqlkit import _key_part, current as is_current, shown
from db.models import metadata

from . import HIGH, NORMAL, SOURCE_RULE, SOURCE_SMARTCHAIN, STATE_IGNORED, STATE_NEW, STATE_OPEN, chain
from .checks import CHECKS

log = logging.getLogger("smartchain.quality")
W = metadata.tables["adm.DataQualityWarning"]
RULE = metadata.tables["adm.ValidationRule"]
PATH = metadata.tables["adm.DemandChainPath"]
# core'da kodu kaybolan bağ: çözülemeyen isteğe bağlı kod core'a boş yazılır; kural işlenmiş staging'de çalışır
CORE_LOST = frozenset({"RG.REF_SUBCONTRACTOR"})
SEP, LABEL_SEP = " · ", ": "  # "Malzeme: HAM-022 · Tedarikçi: TED-02"
LABEL_SKIP = frozenset({"LocationCode", "LineItemNo"})  # Faz 1 tek lokasyon; alt satır kimlikte kalır, etikette yok
NAMES = {e.table: e.name for e in ENTITIES}
FIELDS = metadata.tables["adm.FieldDefinition"]

_md = sa.MetaData()
HITS = sa.Table("#dq_hits", _md, sa.Column("CheckCode", sa.Unicode(60)), sa.Column("Source", sa.Unicode(12)), sa.Column("ValidationRuleId", sa.Integer),
                sa.Column("EntityName", sa.Unicode(60)), sa.Column("RecordKey", sa.Unicode(60)), sa.Column("RecordLabel", sa.Unicode(200)),
                sa.Column("RuleName", sa.Unicode(200)), sa.Column("Message", sa.Unicode(400)), sa.Column("FixField", sa.Unicode(60)))
SCOPE = sa.Table("#dq_scope", _md, sa.Column("CheckCode", sa.Unicode(60)), sa.Column("EntityName", sa.Unicode(60)))
COLS = [c.name for c in HITS.c]


def key_labels(session: Session, entity: str) -> dict[str, str]:
    """Kayıt etiketinin alan adları, veri sözlüğünden (FieldDefinition, K-88): bağ kodu `core`'daki Id alanının etiketiyle (MaterialCode →
    MaterialId "Malzeme"), tablonun kendi kodu tablonun adıyla ("Kaynak: T-05"), öteki alanlar kendi etiketiyle; etiket yoksa alan adı."""
    rows = session.execute(sa.select(FIELDS.c.FieldName, sa.func.coalesce(FIELDS.c.Label, FIELDS.c.StandardLabel)).where(FIELDS.c.TableName == entity))
    fields = {name: label.strip() for name, label in rows if label and label.strip()}
    core = metadata.tables.get(f"core.{entity}")
    out = {}
    for k in key_fields(entity):
        ref = f"{k[:-4]}Id" if k.endswith("Code") else None
        if k == "Code":
            out[k] = NAMES.get(entity) or fields.get(k) or k
        elif ref and core is not None and ref in core.c and ref in fields:
            out[k] = fields[ref]
        else:
            out[k] = fields.get(k) or k
    return out


def _labelled(label: str, part: sa.ColumnElement) -> sa.ColumnElement:
    """"Etiket: değer"; boş değer CONCAT_WS'te atlansın diye NULL."""
    return sa.case((sa.func.coalesce(part, "") == "", sa.null()), else_=sa.func.concat(sa.literal(label + LABEL_SEP, sa.Unicode), part))


def record_label(t, entity: str, labels: dict[str, str]) -> sa.ColumnElement:
    """Ekrandaki Kayıt: iş anahtarı alan etiketleriyle ("Malzeme: HAM-022 · Tedarikçi: TED-02"); lokasyon ve alt satır numarası olmadan."""
    keys = [k for k in key_fields(entity) if k not in LABEL_SKIP and k in t.c] or [k for k in key_fields(entity) if k in t.c]
    if not keys:
        return sa.cast(t.c.StagingRowId if "StagingRowId" in t.c else t.c.Id, sa.Unicode(200))
    parts = [_labelled(labels.get(k, k), _key_part(t.c[k])) for k in keys]
    return sa.func.left(parts[0] if len(parts) == 1 else sa.func.concat_ws(SEP, *parts), 200)


def fix_field(rdef: cat.RuleDef) -> str | None:
    """Kural oluştur'un hedefi: koşulu tek grupta yalnız "boş" olan kural (boş alan türü sorun)."""
    if rdef.groups and len(rdef.groups) == 1 and rdef.groups[0] and all(c.operator == cat.EMPTY for c in rdef.groups[0]):
        return rdef.groups[0][0].field
    return None


def _create_temp(session: Session) -> None:
    session.execute(text("IF OBJECT_ID('tempdb..#dq_hits') IS NOT NULL DROP TABLE #dq_hits"))
    session.execute(text("IF OBJECT_ID('tempdb..#dq_scope') IS NOT NULL DROP TABLE #dq_scope"))
    c = "COLLATE DATABASE_DEFAULT"  # geçici tablo tempdb'nin harmanlamasıyla açılmasın (karşılaştırmalar veritabanındakiyle)
    session.execute(text(f"CREATE TABLE #dq_hits (CheckCode nvarchar(60) {c}, Source nvarchar(12) {c}, ValidationRuleId int NULL, EntityName nvarchar(60) {c}, "
                         f"RecordKey nvarchar(60) {c}, RecordLabel nvarchar(200) {c}, RuleName nvarchar(200) {c}, Message nvarchar(400) {c}, "
                         f"FixField nvarchar(60) {c} NULL)"))
    session.execute(text(f"CREATE TABLE #dq_scope (CheckCode nvarchar(60) {c}, EntityName nvarchar(60) {c})"))


def _selects(rule: dict, rdef: cat.RuleDef, t, record_id, base_where: Callable[[], sa.ColumnElement], labels: dict[str, str]) -> list[sa.Select]:
    entity = rule["EntityName"]
    head = [sa.literal(rule["Code"], sa.Unicode(60)), sa.literal(SOURCE_RULE, sa.Unicode(12)), sa.literal(rule["Id"], sa.Integer),
            sa.literal(entity, sa.Unicode(60)), sa.cast(record_id, sa.Unicode(60)), record_label(t, entity, labels), sa.literal(rule["Name"][:200], sa.Unicode(200))]
    fix = sa.literal(fix_field(rdef), sa.Unicode(60))
    out = []
    if rdef.groups:
        wheres = [conditions.group_where(t, entity, list(g)) for g in rdef.groups]
        out.append(sa.select(*head, sa.literal(rule["Message"][:400], sa.Unicode(400)), fix).where(base_where(), is_current(t), sa.or_(*wheres)))
    for check in rdef.checks:
        message = sa.literal(rule["Message"], sa.Unicode(400))
        if rdef.append_value and check.field:
            message = sa.func.concat(message, sa.literal(" ", sa.Unicode), shown(t.c[check.field]))
        out.append(sa.select(*head, sa.func.left(message, 400), fix).where(base_where(), is_current(t), check.where(t)))
    return out


def evaluate_rule(session: Session, rule: dict, rdef: cat.RuleDef, day: date | None) -> None:
    """Kuralın bulguları geçici tabloya: `core` izdüşümünde; kodu kaybolan bağda işlenmiş staging'de, iş anahtarıyla `core`'a bağlanarak."""
    entity = rule["EntityName"]
    labels = key_labels(session, entity)
    if rdef.code in CORE_LOST:
        t = sqlkit.alias(entity, "_prc")
        c = sqlkit.core_projection(entity).alias("dq_core")
        keys = list(key_fields(entity))
        joined = sa.and_(*[sqlkit.same(t.c[k], c.c[k]) for k in keys])  # koşul staging'de, kimlik core'dan; core'da olmayan satır uyarı vermez
        for sel in _selects(rule, rdef, t, c.c.StagingRowId, lambda: joined, labels):
            session.execute(sa.insert(HITS).from_select(COLS, sel))
        return
    with sqlkit.core_layer(day):
        t = sqlkit.alias(entity, "_dq")
        for sel in _selects(rule, rdef, t, t.c.StagingRowId, lambda: sa.true(), labels):
            session.execute(sa.insert(HITS).from_select(COLS, sel))


def evaluate_check(session: Session, check) -> None:
    t = chain.core(check.table)
    label = record_label(t, check.table, key_labels(session, check.table))  # core'da bulunan anahtar alanlarıyla ("Kaynak: T-05")
    code = sa.func.left(t.c.Code, 200) if "Code" in t.c else sa.cast(t.c.Id, sa.Unicode(200))
    sel = sa.select(sa.literal(check.code, sa.Unicode(60)), sa.literal(SOURCE_SMARTCHAIN, sa.Unicode(12)), sa.null(), sa.literal(check.table, sa.Unicode(60)),
                    sa.cast(t.c.Id, sa.Unicode(60)), label, sa.literal(check.title, sa.Unicode(200)),
                    sa.func.left(sa.func.concat(sa.literal(check.message, sa.Unicode), sa.literal(" ", sa.Unicode), code), 400),
                    sa.literal(check.fix_field, sa.Unicode(60))).where(chain.current(t), check.where(t))
    session.execute(sa.insert(HITS).from_select(COLS, sel))


def _rule_rows(session: Session) -> list[dict]:
    return [dict(r) for r in session.execute(sa.select(RULE).where(RULE.c.Kind != cat.STRUCTURAL_KIND).order_by(RULE.c.Id)).mappings()]


def in_scope(rule: dict, rdef: cat.RuleDef | None, tables: set[str] | None) -> bool:
    if tables is None or rule["EntityName"] in tables:
        return True
    return bool(rdef is not None and set(rdef.reads) & tables)


def tracked(rule: dict) -> bool:
    return bool(rule["IsActive"]) and rule["Severity"] == cat.WARNING and bool(rule["TrackQuality"])


def run(session: Session, tables: set[str] | None = None, day: date | None = None, progress: Callable[[str], None] | None = None) -> dict:
    """Kontrol; tables None ise hepsi. Kendi işleminde, sonunda commit."""
    engine.sync_rules(session)
    session.execute(text("EXEC sp_getapplock @Resource = N'quality:run', @LockMode = N'Exclusive', @LockOwner = N'Transaction', @LockTimeout = -1"))
    today = day or session.execute(text("SELECT CAST(GETDATE() AS date)")).scalar_one()
    now = session.execute(text("SELECT SYSUTCDATETIME()")).scalar_one()
    _create_temp(session)
    rules = _rule_rows(session)
    evaluated = 0
    for rule in rules:
        rdef = engine.definition(session, rule)
        if not in_scope(rule, rdef, tables):
            continue
        session.execute(sa.insert(SCOPE).values(CheckCode=rule["Code"], EntityName=rule["EntityName"]))
        if not tracked(rule) or rdef is None or not (rdef.groups or rdef.checks):
            continue
        if progress and evaluated % 10 == 0:
            progress(f"Veri kalitesi · {rule['Name']}"[:100])
        try:
            with session.begin_nested():
                evaluate_rule(session, rule, rdef, day)
        except Exception:  # bir kural çökerse ötekiler sürer; kuralın uyarıları önceki hâlinde kalır
            log.exception("Veri kalitesi kuralı %s (%s) çalışmadı", rule["Code"], rule["EntityName"])
            session.execute(sa.delete(SCOPE).where(SCOPE.c.CheckCode == rule["Code"], SCOPE.c.EntityName == rule["EntityName"]))
        evaluated += 1
    for check in CHECKS:
        if tables is not None and check.table not in tables:
            continue
        session.execute(sa.insert(SCOPE).values(CheckCode=check.code, EntityName=check.table))
        evaluate_check(session, check)
    if progress:
        progress("Veri kalitesi · talep zinciri")
    counts = chain.rebuild(session, today)
    stats = merge(session, now, full=tables is None)
    session.execute(sa.delete(PATH))
    session.commit()
    log.info("Veri kalitesi: %s kural, %s", evaluated, stats)
    return {**stats, "rules": evaluated, "chain": counts}


def merge(session: Session, now, full: bool) -> dict:
    """Bulgular ↔ uyarılar; yok sayılanın yeniden açılması; önem."""
    p = {"now": now, "new": STATE_NEW, "open": STATE_OPEN, "ignored": STATE_IGNORED, "high": HIGH, "normal": NORMAL}
    session.execute(text("IF OBJECT_ID('tempdb..#dq_one') IS NOT NULL DROP TABLE #dq_one"))
    session.execute(text("SELECT * INTO #dq_one FROM (SELECT h.*, ROW_NUMBER() OVER (PARTITION BY CheckCode, EntityName, RecordKey ORDER BY (SELECT 0)) AS rn "
                         "FROM #dq_hits h) x WHERE rn = 1"))
    kept = session.execute(text(
        "UPDATE w SET State = CASE WHEN w.State = :new THEN :open ELSE w.State END, LastSeenAt = :now, RecordLabel = h.RecordLabel, RuleName = h.RuleName, "
        "Message = h.Message, FixField = h.FixField, ValidationRuleId = h.ValidationRuleId, Source = h.Source "
        "FROM adm.DataQualityWarning w JOIN #dq_one h ON h.CheckCode = w.CheckCode AND h.EntityName = w.EntityName AND h.RecordKey = w.RecordKey"), p).rowcount
    added = session.execute(text(
        "INSERT INTO adm.DataQualityWarning (Source, ValidationRuleId, CheckCode, EntityName, RecordKey, RecordLabel, RuleName, Message, FixField, Importance, "
        "State, FirstSeenAt, LastSeenAt) "
        "SELECT h.Source, h.ValidationRuleId, h.CheckCode, h.EntityName, h.RecordKey, h.RecordLabel, h.RuleName, h.Message, h.FixField, :normal, :new, :now, :now "
        "FROM #dq_one h WHERE NOT EXISTS (SELECT 1 FROM adm.DataQualityWarning w WHERE w.CheckCode = h.CheckCode AND w.EntityName = h.EntityName "
        "AND w.RecordKey = h.RecordKey)"), p).rowcount
    gone = "NOT EXISTS (SELECT 1 FROM #dq_one h WHERE h.CheckCode = w.CheckCode AND h.EntityName = w.EntityName AND h.RecordKey = w.RecordKey)"
    removed = session.execute(text(
        f"DELETE w FROM adm.DataQualityWarning w JOIN #dq_scope s ON s.CheckCode = w.CheckCode AND s.EntityName = w.EntityName WHERE {gone}")).rowcount
    if full:  # kuralı ya da kontrolü artık olmayan uyarı
        removed += session.execute(text(
            "DELETE w FROM adm.DataQualityWarning w WHERE NOT EXISTS (SELECT 1 FROM #dq_scope s WHERE s.CheckCode = w.CheckCode AND s.EntityName = w.EntityName)")).rowcount
    reopened = reopen_changed(session)
    importance(session)
    return {"added": added, "kept": kept, "removed": removed, "reopened": reopened}


def reopen_changed(session: Session, entity: str | None = None, record_key: str | None = None) -> int:
    """Yok sayıldıktan sonra kaydı değişen uyarı (ERP'den yeni versiyon ya da manuel değer; FieldChange, K-173) yeniden Açık."""
    where = ["w.State = :ignored", "EXISTS (SELECT 1 FROM adm.FieldChange f WHERE f.TableName = w.EntityName AND f.RecordKey = w.RecordKey AND f.At > w.IgnoredAt)"]
    p = {"ignored": STATE_IGNORED, "open": STATE_OPEN}
    if entity is not None:
        where += ["w.EntityName = :entity", "w.RecordKey = :key"]
        p |= {"entity": entity, "key": record_key}
    return session.execute(text("UPDATE w SET State = :open, IgnoreReason = NULL, IgnoredBy = NULL, IgnoredAt = NULL "
                                f"FROM adm.DataQualityWarning w WHERE {' AND '.join(where)}"), p).rowcount


def importance(session: Session) -> None:
    """Yüksek: kayıt talep zincirinde ya da malzemesi zincirdeki bir malzeme (K-174); değilse Normal."""
    p = {"high": HIGH, "normal": NORMAL}
    session.execute(text(
        "UPDATE w SET Importance = CASE WHEN EXISTS (SELECT 1 FROM adm.DemandChain d WHERE d.EntityName = w.EntityName "
        "AND d.RecordId = TRY_CAST(w.RecordKey AS bigint)) THEN :high ELSE :normal END FROM adm.DataQualityWarning w"), p)
    for name in sorted({e for (e,) in session.execute(sa.select(W.c.EntityName).distinct()).all()}):
        t = metadata.tables.get(f"core.{name}")
        if t is None or "MaterialId" not in t.c:
            continue
        cur = "AND t.VersionTo IS NULL" if "VersionTo" in t.c else ""
        session.execute(text(
            f"UPDATE w SET Importance = :high FROM adm.DataQualityWarning w JOIN core.[{name}] t ON t.Id = TRY_CAST(w.RecordKey AS bigint) {cur} "
            "JOIN adm.DemandChain d ON d.EntityName = N'Material' AND d.RecordId = t.MaterialId "
            "WHERE w.EntityName = :entity AND w.Importance <> :high"), {**p, "entity": name})
    # Kontrole özel önem (K-185): Yüksek = kayıt talep zincirinde VE kontrolün koşulu tutuyor (ör. kaynağın grubu kritik); geri kalanı Normal
    for check in CHECKS:
        if check.high_when is None:
            continue
        t = chain.core(check.table)
        session.execute(sa.update(W).where(W.c.CheckCode == check.code).values(Importance=NORMAL))
        qualifies = sa.select(sa.cast(t.c.Id, sa.Unicode(60))).where(chain.current(t), check.high_when(t))
        in_chain = sa.text("EXISTS (SELECT 1 FROM adm.DemandChain d WHERE d.EntityName = :entity AND d.RecordId = TRY_CAST(adm.DataQualityWarning.RecordKey AS bigint))")
        session.execute(sa.update(W).where(W.c.CheckCode == check.code, W.c.RecordKey.in_(qualifies), in_chain).values(Importance=HIGH),
                        {"entity": check.table})
