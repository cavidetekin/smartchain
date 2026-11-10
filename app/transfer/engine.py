"""Aktarım motoru: tam (fonksiyon 05, 07) ve kısmi (fonksiyon 06) (K-133, K-135, K-140, K-145, K-146, K-149…K-151, K-153, K-155).

Kısmide yalnız seçilen grupların tabloları yazılır; seçilmeyen tablolar yazılmamış sayılır, bağlı ana verisi mevcut veride olmayan satır bekler.

Tek işlem, ya hep ya hiç: yeni veri versiyonu açılır, tablolar katalog sırasıyla (ebeveyn önce) yazılır. Tablo başına küme SQL:
1. Çözümle: prc satırları core kolon adlarıyla geçici tabloya; kodlar core'un güncel satırlarından Id'ye çevrilir; satırın durumu
   (1 aktarılır · 2 aktarılmaz, core'daki önceki hâli kalır · 3 kapsam dışı, core'da kapatılır).
2. Eşleştir: core'un güncel tekil anahtarıyla; eşleşmeyen aktarılacak satır yeni Id alır; tablo içi bağ (orijinal iş emri) aynı aktarımdan çözülür.
3. Değişeni bul, kapat (`VersionTo` = yeni versiyon − 1), ekle (aynı Id, `VersionFrom` = yeni versiyon); korunan kolonlar önceki versiyondan.
4. prc'de aktarılan satır "Aktarıldı"; değerin kaynağı (kuralla değişen alanlar, K-148); sayılar DataVersionEntity'ye.
"""
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration import references as refs
from app.integration.contract import ENTITIES, entity as contract_entity
from app.validation import catalog as cat, engine as validation
from app.validation.sqlkit import _key_part, present
from db.models import metadata

from .groups import group_tables
from .mapping import UNVERSIONED, RefColumn, TableMap, id_name, order, table_map

log = logging.getLogger("smartchain.transfer")

OK, KEEP, CLOSE = 1, 2, 3
GUARD_NULL, GUARD_KEY, GUARD_PARENT, GUARD_WAIT = 1, 2, 3, 4  # validasyonda görünmeyen aktarılmayan: zorunlu kolon boş · aynı anahtar · ebeveyni aktarılmadı · kısmide ebeveyn tablo seçilmedi
TRANSFERRED, ERROR_ROW = "Aktarıldı", "Hatalı"
FULL, PARTIAL = "Tam", "Kısmi"
NOTE_EMPTY = "Veri gelmedi; mevcut veri korunur."
NOTE_WAITING = "{n} satır, bağlı ana veri henüz aktarılmadığı için bekliyor (kısmi aktarım)."  # K-151, K-155
DATA_VERSION = metadata.tables["adm.DataVersion"]
VERSION_ENTITY = metadata.tables["adm.DataVersionEntity"]
SOURCE = metadata.tables["adm.FieldValueSource"]
EFFECT = metadata.tables["adm.DataRuleEffect"]
CONFIG = metadata.tables["adm.IntegrationEntity"]
UNIT = metadata.tables["core.UnitOfMeasure"]
LOCATION = metadata.tables["core.Location"]
BIN = "Latin1_General_100_BIN2"
UNIT_FIELDS = (("Material", "BaseUom"), ("Resource", "CapacityUnit"), ("UomConversion", "FromUom"), ("UomConversion", "ToUom"),
               ("BOM", "ComponentUom"), ("SalesOrderLine", "Uom"), ("Forecast", "Uom"), ("Stock", "Uom"), ("WorkOrder", "Uom"),
               ("WorkOrderComponent", "Uom"), ("PurchaseOrderLine", "Uom"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class TableResult:
    entity: str
    name: str
    new: int | None = None
    changed: int | None = None
    closed: int | None = None
    not_transferred: int | None = None
    note: str | None = None
    batch_id: int | None = None
    transferred: bool = False

    def as_dict(self) -> dict:
        return {"entity": self.entity, "name": self.name, "new": self.new, "changed": self.changed, "closed": self.closed,
                "not_transferred": self.not_transferred, "note": self.note}


@dataclass
class Run:
    version: int
    now: datetime
    skipped: set[str] = field(default_factory=set)   # bu aktarımda yazılmayan tablolar (eşik, veri yok, kısmide seçilmeyen)
    waiting: set[str] = field(default_factory=set)   # kısmide seçilmeyen tablolar: onlara bağlı eksik satır bekler (K-155)


# ------------------------------------------------------------------ ön koşul ve plan

def threshold_note(session: Session, entity: str) -> str | None:
    """Eşik aşıldıysa notu (K-135): oran eşikten büyükse tablo aktarılmaz."""
    limit = session.execute(sa.select(CONFIG.c.ErrorThresholdPct).where(CONFIG.c.EntityName == entity)).scalar()
    if limit is None:
        return None
    rate = validation.counts(session, entity)["error_rate"]
    if rate is not None and rate > float(limit):
        return f"Hatalı satır oranı %{_pct(rate)}, eşik %{_pct(float(limit))}; tablo aktarılmadı, mevcut veri korunur."
    return None


def _pct(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def staged_batch(session: Session, entity: str) -> int | None:
    t = metadata.tables[f"stg.{entity}"]
    return session.execute(sa.select(sa.func.max(t.c.ImportBatchId)).where(t.c.IsCurrent == sa.true())).scalar()


# ------------------------------------------------------------------ birim (K-112)

def ensure_units(session: Session, entities: set[str] | None = None) -> int:
    """Diğer tablolarda geçen birim kodlarından eksik birimler; ad dönüşüm satırından, ondalık yazılmaz. Kısmide yalnız seçilen tablolardan (K-155)."""
    added = 0
    conv = metadata.tables["prc.UomConversion"]
    for code_col, name_col in ((conv.c.FromUom, conv.c.FromUomName), (conv.c.ToUom, conv.c.ToUomName)):
        sel = (sa.select(code_col, sa.func.max(name_col)).where(code_col.is_not(None), ~sa.exists().where(UNIT.c.Code == code_col)).group_by(code_col))
        if entities is None or "UomConversion" in entities:
            added += session.execute(sa.insert(UNIT).from_select(["Code", "Name"], sel)).rowcount
    for entity, column in UNIT_FIELDS:
        if entities is not None and entity not in entities:
            continue
        t = metadata.tables[f"prc.{entity}"]
        sel = sa.select(t.c[column]).where(t.c[column].is_not(None), ~sa.exists().where(UNIT.c.Code == t.c[column])).distinct()
        added += session.execute(sa.insert(UNIT).from_select(["Code"], sel)).rowcount
    return added


# ------------------------------------------------------------------ çözümleme

def _core_current(entity: str, suffix: str) -> sa.Alias:
    t = metadata.tables[f"core.{entity}"]
    return t.alias(f"c_{entity.lower()}{suffix}")


def _is_current(a) -> sa.ColumnElement:
    return a.c.VersionTo.is_(None) if "VersionTo" in a.c else sa.true()


class Resolver:
    """Bir tablonun prc satırlarını core kolonlarına çeviren ifadeler."""

    def __init__(self, m: TableMap, p: sa.Alias, loc: sa.Alias | None):
        self.m, self.p, self.loc = m, p, loc
        self.ids: dict[str, sa.ColumnElement] = {}   # çocuk alanı (prc) → çözülmüş Id ifadesi
        if loc is not None:
            self.ids["LocationCode"] = loc.c.Id

    def parent_value(self, r: refs.Reference, child_field: str, parent_field: str, parent) -> tuple[sa.ColumnElement, sa.ColumnElement]:
        """(ebeveyn kolonu, çocuk değeri): ebeveynde aynı adlı kolon varsa kod, yoksa ebeveynin Id kolonu ve çocuğun çözülmüş Id'si."""
        if parent_field in parent.c:
            return parent.c[parent_field], self.p.c[child_field]
        return parent.c[id_name(parent_field)], self.ids[child_field]

    def resolve(self, rc: RefColumn, index: int) -> sa.ColumnElement:
        r = rc.ref
        a = _core_current(r.parent, f"_{index}")
        conds = [_is_current(a)]
        if r.by_location:
            conds.append(a.c.LocationId == self.loc.c.Id)
        for i, (cf, pf) in enumerate(zip(r.fields, r.parent_fields)):
            col, value = self.parent_value(r, cf, pf, a)
            conds.append(col == value if i == 0 else sa.or_(self.p.c[cf].is_(None), col == value))
        # iç içe çözümlemede (versiyon → malzeme) bütün dış tablolara bağlanır, yalnız bir üst seviyeye değil
        expr = sa.select(a.c.Id).where(*conds).order_by(a.c.Id).limit(1).correlate_except(a).scalar_subquery()
        self.ids[r.fields[0]] = expr
        return expr


def _prc_parent_exists(r: refs.Reference, p, *extra) -> sa.ColumnElement:
    """Ebeveyn prc'de var mı (kodlarla, catalog eşleşmesi)."""
    a = metadata.tables[f"prc.{r.parent}"].alias(f"pp_{r.prefix.lower()}_{r.key.lower()}")
    return sa.exists().where(present(a), *cat._match(r, p, a), *[e(a) for e in extra])


def _typed(column: sa.Column):
    """Geçici tablo kolon tipi: metinde veritabanının sıralaması (tempdb'ninki değil; karşılaştırmada çakışma olmasın)."""
    t = column.type
    if isinstance(t, sa.String):
        return sa.Unicode(t.length, collation="DATABASE_DEFAULT")
    return t


def _temp_table(session: Session, m: TableMap) -> sa.Table:
    cols = [sa.Column("StagingRowId", sa.BigInteger), sa.Column("PrcBatchId", sa.BigInteger), sa.Column("St", sa.SmallInteger),
            sa.Column("M", sa.Boolean), sa.Column("Ch", sa.Boolean), sa.Column("Gd", sa.SmallInteger), sa.Column("Id", sa.BigInteger),
            sa.Column("BusinessKey", sa.Unicode(200, collation="DATABASE_DEFAULT"))]
    cols += [sa.Column(name, _typed(m.core.c[name])) for name in m.compare]
    for rc in m.refs:
        if rc.self_ref:
            cols += [sa.Column(f"_self_{f}", _typed(m.prc.c[f])) for f in rc.ref.fields]
    tmp = sa.Table(f"#t_{m.entity}", sa.MetaData(), *cols)
    tmp.create(bind=session.connection())
    return tmp


def _resolve(session: Session, m: TableMap, run: Run, tmp: sa.Table) -> None:
    p = m.prc.alias("p")
    loc = LOCATION.alias("loc") if m.location else None
    rs = Resolver(m, p, loc)
    values: dict[str, sa.ColumnElement] = {n: p.c[n] for n in m.plain}
    close_conds, keep_conds, wait_conds = [], [], []
    if m.location:
        values["LocationId"] = loc.c.Id
        keep_conds.append(sa.and_(p.c.LocationCode.is_not(None), loc.c.Id.is_(None)))
    expand = None   # UomConversion: malzemeye özel satır her lokasyonun malzemesine (K-112)
    for i, rc in enumerate(m.refs):
        r, code = rc.ref, p.c[rc.ref.fields[0]]
        if rc.self_ref:
            values[rc.column] = sa.null()
            continue
        if m.entity == "UomConversion" and rc.column == "MaterialId":
            expand = _core_current("Material", "_x")
            values[rc.column] = expand.c.Id
            rs.ids[r.fields[0]] = expand.c.Id
            keep_conds.append(sa.and_(code.is_not(None), expand.c.Id.is_(None)))  # malzeme yoksa aktarılmaz (boş = genel dönüşüm olurdu, K-153)
            continue
        resolved = rs.resolve(rc, i)
        values[rc.column] = resolved
        missing = sa.and_(code.is_not(None), resolved.is_(None))
        parent_written = r.parent not in run.skipped
        if r.is_error:
            excluded = _prc_parent_exists(r, p, lambda a: sa.func.coalesce(a.c.RowStatus, "") != ERROR_ROW) if parent_written else sa.false()
            close_conds.append(sa.and_(missing, excluded))
            keep_conds.append(missing)
            if r.parent in run.waiting:
                wait_conds.append(missing)
        elif r.inactive and parent_written:   # ebeveyn yazılmadıysa mevcut verideki hâli geçerli (K-155)
            close_conds.append(sa.and_(missing, _prc_parent_exists(r, p, lambda a: a.c.IsActive == sa.false())))
    # Savunma: core'da zorunlu kolon boşsa satır aktarılmaz (validasyon bitmemiş ya da kural boşaltmış olabilir; işlem düşmesin); raporda notu
    null_conds = [values[n].is_(None) for n in values if not m.core.c[n].nullable]
    ref_keep = list(keep_conds)
    keep_conds += null_conds
    st_whens = []
    if "IsActive" in p.c:
        st_whens.append((p.c.IsActive == sa.false(), CLOSE))
    st_whens.append((sa.func.coalesce(p.c.RowStatus, "") == ERROR_ROW, KEEP))
    if close_conds:
        st_whens.append((sa.or_(*close_conds), CLOSE))
    if keep_conds:
        st_whens.append((sa.or_(*keep_conds), KEEP))
    status = sa.case(*st_whens, else_=OK)
    keys = [_key_part(p.c[k]) for k in m.business_key]
    business = sa.func.left(sa.func.concat_ws("|", *keys), 200) if len(keys) > 1 else sa.func.left(keys[0], 200)
    scoped = [p.c.IsActive == sa.false()] if "IsActive" in p.c else []
    whens = [(sa.or_(*scoped, sa.func.coalesce(p.c.RowStatus, "") == ERROR_ROW), 0)]
    if wait_conds:
        whens.append((sa.or_(*wait_conds), GUARD_WAIT))   # kısmi: bağlı ana veri seçilmeyen tabloda ve mevcut veride yok (K-155)
    if ref_keep:
        whens.append((sa.or_(*ref_keep), GUARD_PARENT))   # satır geçerli, ebeveyni core'da yok (ebeveyn Hatalı ya da aktarılmadı)
    if null_conds:
        whens.append((sa.or_(*null_conds), GUARD_NULL))
    guard = sa.case(*whens, else_=0)
    cols = {"StagingRowId": p.c.StagingRowId, "PrcBatchId": p.c.ImportBatchId, "St": status, "M": sa.false(), "Ch": sa.false(), "Gd": guard,
            "BusinessKey": business, **values}
    for rc in m.refs:
        if rc.self_ref:
            for f in rc.ref.fields:
                cols[f"_self_{f}"] = p.c[f]
    source = p
    if loc is not None:
        source = source.outerjoin(loc, loc.c.Code == p.c.LocationCode)
    if expand is not None:
        source = source.outerjoin(expand, sa.and_(expand.c.Code == p.c.MaterialCode, expand.c.VersionTo.is_(None)))
    sel = sa.select(*[v.label(k) for k, v in cols.items()]).select_from(source)
    session.execute(sa.insert(tmp).from_select(list(cols), sel))


# ------------------------------------------------------------------ eşleştirme, kapatma, ekleme

def _same(a, b) -> sa.ColumnElement:
    return sa.or_(a == b, sa.and_(a.is_(None), b.is_(None)))


def _differs(a, b) -> sa.ColumnElement:
    if isinstance(a.type, (sa.String, sa.Unicode)):
        a, b = a.collate(BIN), b.collate(BIN)
    return ~sa.or_(a == b, sa.and_(a.is_(None), b.is_(None)))


def _collisions(session: Session, m: TableMap, tmp: sa.Table) -> None:
    """Aynı core anahtarına düşen aktarılacak satırlar (isteğe bağlı bağlantı boş yazılınca olabilir) aktarılmaz: hangisinin doğru olduğu bilinemez."""
    keys = ", ".join(f"[{k}]" for k in m.key)
    session.execute(sa.text(f"WITH d AS (SELECT St, Gd, COUNT(*) OVER (PARTITION BY {keys}) AS n FROM [{tmp.name}] WHERE St = {OK}) "
                            f"UPDATE d SET St = {KEEP}, Gd = {GUARD_KEY} WHERE n > 1"))


def _match(session: Session, m: TableMap, tmp: sa.Table) -> None:
    c = m.core.alias("c")
    found = sa.select(c.c.Id).where(_is_current(c), *[_same(c.c[k], tmp.c[k]) for k in m.key]).order_by(c.c.Id).limit(1).scalar_subquery()
    session.execute(sa.update(tmp).values(Id=found))
    session.execute(sa.update(tmp).where(tmp.c.Id.is_not(None)).values(M=sa.true()))


def _new_ids(session: Session, m: TableMap, tmp: sa.Table) -> None:
    top = session.execute(sa.select(sa.func.max(m.core.c.Id))).scalar() or 0
    session.execute(sa.text(f"WITH n AS (SELECT Id, ROW_NUMBER() OVER (ORDER BY StagingRowId, BusinessKey) AS rn FROM [{tmp.name}] WHERE St = {OK} AND M = 0) "
                            "UPDATE n SET Id = :top + rn"), {"top": int(top)})


def _self_refs(session: Session, m: TableMap, tmp: sa.Table) -> None:
    for rc in m.refs:
        if not rc.self_ref:
            continue
        r = rc.ref
        o = tmp.alias("o")
        conds = [o.c.St.in_([OK, KEEP]), o.c.Id.is_not(None)]
        if r.by_location:
            conds.append(o.c.LocationId == tmp.c.LocationId)
        for cf, pf in zip(r.fields, r.parent_fields):
            conds.append(o.c[pf] == tmp.c[f"_self_{cf}"])
        session.execute(sa.update(tmp).where(tmp.c[f"_self_{r.fields[0]}"].is_not(None))
                        .values({rc.column: sa.select(o.c.Id).where(*conds).limit(1).scalar_subquery()}))


def _changed(session: Session, m: TableMap, tmp: sa.Table) -> None:
    c = m.core.alias("c")
    diff = sa.or_(*[_differs(c.c[n], tmp.c[n]) for n in m.compare])
    session.execute(sa.update(tmp).where(tmp.c.St == OK, tmp.c.M == sa.true(), sa.exists().where(c.c.Id == tmp.c.Id, _is_current(c), diff))
                    .values(Ch=sa.true()))


def _close(session: Session, m: TableMap, run: Run, tmp: sa.Table) -> int:
    t = m.core
    keep = sa.exists().where(tmp.c.Id == t.c.Id, sa.or_(tmp.c.St == KEEP, sa.and_(tmp.c.St == OK, tmp.c.Ch == sa.false())))
    return session.execute(sa.update(t).where(t.c.VersionTo.is_(None), ~keep).values(VersionTo=run.version - 1, UpdatedAt=run.now)).rowcount


def _insert(session: Session, m: TableMap, run: Run, tmp: sa.Table) -> None:
    prev = m.core.alias("prev")
    cols = {n: tmp.c[n] for n in m.compare}
    cols.update(Id=tmp.c.Id, VersionFrom=sa.literal(run.version), VersionTo=sa.null(), ImportBatchId=tmp.c.PrcBatchId,
                BusinessKey=tmp.c.BusinessKey, UpdatedAt=sa.literal(run.now))
    for n in m.preserved:
        cols[n] = prev.c[n]
    for n in m.precalc:
        cols[n] = sa.null()
    sel = (sa.select(*[v.label(k) for k, v in cols.items()])
           .select_from(tmp.outerjoin(prev, sa.and_(prev.c.Id == tmp.c.Id, prev.c.VersionTo == run.version - 1)))
           .where(tmp.c.St == OK, sa.or_(tmp.c.M == sa.false(), tmp.c.Ch == sa.true())))
    session.execute(sa.insert(m.core).from_select(list(cols), sel))


def _value_sources(session: Session, m: TableMap, tmp: sa.Table) -> None:
    """Kuralla değişen alanların kaynağı (K-148): eski Kural satırları silinir, kural izinden yeniden yazılır."""
    ids = sa.select(tmp.c.Id).where(tmp.c.St == OK)
    session.execute(sa.delete(SOURCE).where(SOURCE.c.TableName == m.entity, SOURCE.c.Source == "Kural", SOURCE.c.RecordId.in_(ids)))
    names = [(f, m.prc_to_core(f)) for f in [c.name for c in m.prc.columns]]
    names = [(f, core) for f, core in names if core]
    if not names:
        return
    field_expr = sa.case(*[(EFFECT.c.FieldName == f, sa.literal(core, sa.Unicode)) for f, core in names])
    sel = (sa.select(sa.literal(m.entity, sa.Unicode), tmp.c.Id, field_expr, sa.literal("Kural", sa.Unicode), EFFECT.c.DataRuleId,
                     sa.func.left(EFFECT.c.RawValue, 200))
           .select_from(tmp.join(EFFECT, sa.and_(EFFECT.c.EntityName == m.entity, EFFECT.c.StagingRowId == tmp.c.StagingRowId)))
           .where(tmp.c.St == OK, EFFECT.c.FieldName.in_([f for f, _ in names])))
    session.execute(sa.insert(SOURCE).from_select(["TableName", "RecordId", "FieldName", "Source", "DataRuleId", "ErpValue"], sel))


def _counts(session: Session, tmp: sa.Table) -> dict:
    row = session.execute(sa.select(
        sa.func.sum(sa.case((sa.and_(tmp.c.St == OK, tmp.c.M == sa.false()), 1), else_=0)),
        sa.func.sum(sa.case((sa.and_(tmp.c.St == OK, tmp.c.Ch == sa.true()), 1), else_=0)),
        sa.func.count(sa.distinct(sa.case((tmp.c.St == KEEP, tmp.c.StagingRowId)))))).one()
    return {"new": int(row[0] or 0), "changed": int(row[1] or 0), "not_transferred": int(row[2] or 0)}


def _guard_note(session: Session, m: TableMap, tmp: sa.Table) -> str | None:
    """Savunmayla aktarılmayan satırların tablo notu (veri aktarım raporu, K-151): validasyonda Hata görünmeyen durumlar."""
    nulls = [n for n in m.compare if not m.core.c[n].nullable]
    row = session.execute(sa.select(sa.func.count(sa.distinct(sa.case((tmp.c.Gd == GUARD_NULL, tmp.c.StagingRowId)))),
                                    sa.func.count(sa.distinct(sa.case((tmp.c.Gd == GUARD_KEY, tmp.c.StagingRowId)))),
                                    sa.func.count(sa.distinct(sa.case((sa.and_(tmp.c.Gd == GUARD_PARENT, tmp.c.St == KEEP), tmp.c.StagingRowId)))),
                                    sa.func.count(sa.distinct(sa.case((sa.and_(tmp.c.Gd == GUARD_WAIT, tmp.c.St == KEEP), tmp.c.StagingRowId)))),
                                    *[sa.func.sum(sa.case((sa.and_(tmp.c.Gd == GUARD_NULL, tmp.c[n].is_(None)), 1), else_=0)) for n in nulls])
                          .select_from(tmp)).one()
    parts = []
    if row[3]:
        parts.append(NOTE_WAITING.format(n=row[3]))
    if row[2]:
        parts.append(f"{row[2]} satır, bağlı olduğu ana veri aktarılmadığı için aktarılmadı.")
    if row[0]:
        fields = [m.core.c[n].info.get("label", n) for n, c in zip(nulls, row[4:]) if c]
        parts.append(f"{row[0]} satır, zorunlu alanı boş olduğu için aktarılmadı ({', '.join(fields)}).")
    if row[1]:
        parts.append(f"{row[1]} satır, aynı kayda düştüğü için aktarılmadı.")
    return " ".join(parts) if parts else None


def _mark(session: Session, m: TableMap, tmp: sa.Table) -> None:
    p = m.prc
    session.execute(sa.update(p).where(p.c.StagingRowId.in_(sa.select(tmp.c.StagingRowId).where(tmp.c.St == OK))).values(RowStatus=TRANSFERRED))


def transfer_table(session: Session, entity: str, run: Run) -> dict:
    m = table_map(entity)
    if entity in UNVERSIONED:
        return _transfer_location(session, m, run)
    tmp = _temp_table(session, m)
    try:
        _resolve(session, m, run, tmp)
        _collisions(session, m, tmp)
        _match(session, m, tmp)
        _new_ids(session, m, tmp)
        _self_refs(session, m, tmp)
        _changed(session, m, tmp)
        counts = _counts(session, tmp)
        note = _guard_note(session, m, tmp)
        closed = _close(session, m, run, tmp)
        _insert(session, m, run, tmp)
        _value_sources(session, m, tmp)
        _mark(session, m, tmp)
    finally:
        tmp.drop(bind=session.connection())
    return {**counts, "closed": closed - counts["changed"], "note": note}


def _transfer_location(session: Session, m: TableMap, run: Run) -> dict:
    """Lokasyon versiyonsuz (K-153): kodla eşleşir, eklenir ya da güncellenir; staging'de olmayan ve pasif lokasyon IsActive 0."""
    p, t = m.prc, LOCATION
    ok = sa.and_(sa.func.coalesce(p.c.IsActive, sa.true()) == sa.true(), sa.func.coalesce(p.c.RowStatus, "") != ERROR_ROW)
    names = list(m.plain)
    changed_cond = sa.or_(*[_differs(t.c[n], p.c[n]) for n in names if n != "Code"])
    changed = session.execute(sa.update(t).where(sa.exists().where(p.c.Code == t.c.Code, ok, changed_cond))
                              .values({n: sa.select(p.c[n]).where(p.c.Code == t.c.Code, ok).limit(1).scalar_subquery() for n in names if n != "Code"})).rowcount
    sel = sa.select(*[p.c[n] for n in names], sa.literal(False)).where(ok, ~sa.exists().where(t.c.Code == p.c.Code))
    new = session.execute(sa.insert(t).from_select(names + ["IsSynthetic"], sel)).rowcount
    keep = sa.exists().where(p.c.Code == t.c.Code, sa.or_(ok, sa.func.coalesce(p.c.RowStatus, "") == ERROR_ROW), sa.func.coalesce(p.c.IsActive, sa.true()) == sa.true())
    closed = session.execute(sa.update(t).where(sa.func.coalesce(t.c.IsActive, sa.true()) == sa.true(), ~keep).values(IsActive=False)).rowcount
    not_transferred = session.execute(sa.select(sa.func.count()).select_from(p).where(sa.func.coalesce(p.c.RowStatus, "") == ERROR_ROW,
                                                                                     sa.func.coalesce(p.c.IsActive, sa.true()) == sa.true())).scalar()
    session.execute(sa.update(p).where(ok).values(RowStatus=TRANSFERRED))
    return {"new": new, "changed": changed, "closed": closed, "not_transferred": int(not_transferred or 0)}


# ------------------------------------------------------------------ aktarım

def lock(session: Session) -> None:
    """Aktarım kilidi ve bütün tabloların validasyon kilidi (işlem boyunca): aktarım sürerken validasyon prc'yi yeniden kuramaz."""
    validation._applock(session, "transfer")
    for e in ENTITIES:
        validation._applock(session, f"validation:table:{e.table}")


def run_transfer(session: Session, user_id: int | None, progress: Callable[[str], None] | None = None,
                 groups: list[str] | None = None) -> dict:
    """Grup yoksa bütün tablolar (tam), varsa yalnız seçilen grupların tabloları (kısmi, K-155); commit çağıranındır (iş kaydıyla aynı işlemde)."""
    selected = group_tables(groups) if groups else None
    lock(session)
    now = utcnow()
    version = session.execute(sa.insert(DATA_VERSION).values(LocationId=None, CreatedAt=now, LoadType=PARTIAL if selected else FULL, CreatedBy=user_id,
                                                             IsPinned=False, IsSynthetic=False).returning(DATA_VERSION.c.Id)).scalar_one()
    run = Run(int(version), now)
    names = order()
    if selected:
        run.waiting = {e for e in names if e not in selected}
        run.skipped |= run.waiting
        names = tuple(e for e in names if e in selected)
    ensure_units(session, set(names) if selected else None)
    results: list[TableResult] = []
    for i, entity in enumerate(names, 1):
        info = contract_entity(entity)
        res = TableResult(entity, info.name if info else entity, batch_id=staged_batch(session, entity))
        if progress:
            progress(f"{res.name} · {i} / {len(names)}")
        if not _has_raw(session, entity):
            res.note = NOTE_EMPTY
            run.skipped.add(entity)
        elif (note := threshold_note(session, entity)) is not None:
            res.note = note
            run.skipped.add(entity)
        else:
            counts = transfer_table(session, entity, run)
            res.new, res.changed, res.closed, res.not_transferred = counts["new"], counts["changed"], counts["closed"], counts["not_transferred"]
            res.note = counts.get("note")
            res.transferred = True
        session.execute(sa.insert(VERSION_ENTITY).values(DataVersionId=run.version, EntityName=entity, ImportBatchId=res.batch_id, NewCount=res.new,
                                                         ChangedCount=res.changed, ClosedCount=res.closed, NotTransferredCount=res.not_transferred,
                                                         Note=res.note))
        results.append(res)
    return {"data_version": run.version, "tables": [r.as_dict() for r in results]}


def _has_raw(session: Session, entity: str) -> bool:
    """Staging'de güncel satır var mı (IsActive = Hayır satırlar dahil; hepsi pasifse tablo aktarılır, kayıtlar kapatılır)."""
    t = metadata.tables[f"stg.{entity}"]
    return session.execute(sa.select(t.c.StagingRowId).where(t.c.IsCurrent == sa.true()).limit(1)).first() is not None
