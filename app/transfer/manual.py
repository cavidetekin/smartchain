"""Manuel değerin aktarımda korunması (K-170, K-148): gelen değer alttaki değer olarak saklanır, yerine manuel değer konur.

Manuel değer karşılaştırmadan önce konduğu için yalnız manuel değer farkı "değişti" sayılmaz, yeni versiyon açmaz; manuel değer yeni versiyona aynen
taşınır. Alttaki değerin kaynağı kural izinden (kural varsa "Kural", yoksa "ERP"); manuel değer girildiğindeki alttaki değerle farklıysa
"değişti" işaretlenir. Manuel değer yalnız ilişki ve anahtar olmayan iş alanlarındadır (aynı adlı kolonlar).
"""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.manual import EFFECT, ERP, MANUAL, RULE_SOURCE, KEY_LENGTH, as_text, differs, from_text


def fields(session: Session, entity: str, plain) -> list[str]:
    names = session.execute(sa.select(MANUAL.c.FieldName).where(MANUAL.c.TableName == entity).distinct()).scalars().all()
    return [n for n in names if n in plain]


def _underlying(entity: str, field: str, value, staging_row, col) -> dict:
    rule = (sa.select(EFFECT.c.DataRuleId).where(EFFECT.c.EntityName == entity, EFFECT.c.StagingRowId == staging_row, EFFECT.c.FieldName == field)
            .limit(1).correlate_except(EFFECT).scalar_subquery())  # satır dış sorgudan (geçici tablo ya da prc)
    return {"UnderlyingValue": as_text(value, col), "UnderlyingRuleId": rule, "UnderlyingSource": sa.case((rule.is_not(None), RULE_SOURCE), else_=ERP),
            "IsBaseChanged": sa.case((differs(from_text(MANUAL.c.BaseValue, col), value, col), sa.true()), else_=sa.false())}


def apply_versioned(session: Session, entity: str, core: sa.Table, plain, tmp: sa.Table, ok: int) -> None:
    """Eşleşen ve aktarılacak satırlarda (geçici tablo, karşılaştırmadan önce)."""
    for f in fields(session, entity, plain):
        col = core.c[f]
        hit = [MANUAL.c.TableName == entity, MANUAL.c.FieldName == f, MANUAL.c.RecordKey == sa.cast(tmp.c.Id, sa.Unicode(KEY_LENGTH)),
               tmp.c.St == ok, tmp.c.M == sa.true()]
        session.execute(sa.update(MANUAL).where(*hit).values(_underlying(entity, f, tmp.c[f], tmp.c.StagingRowId, col)))
        session.execute(sa.update(tmp).where(*hit).values({f: from_text(MANUAL.c.Value, col)}))


def location_value(field: str, core: sa.Table, incoming, col) -> sa.ColumnElement:
    """Lokasyon (versiyonsuz, K-153) güncellemesinde gelen değerin yerine manuel değer (varsa)."""
    mv = MANUAL.alias(f"mv_{field}")
    match = [mv.c.TableName == "Location", mv.c.FieldName == field, mv.c.RecordKey == sa.cast(core.c.Id, sa.Unicode(KEY_LENGTH))]
    # iç içe alt sorguda core satırı dış sorgudan gelir (kendiliğinden ilişkilendirme bir üst seviyeye bakar)
    value = sa.select(from_text(mv.c.Value, col)).where(*match).limit(1).correlate_except(mv).scalar_subquery()
    return sa.case((sa.exists().where(*match).correlate_except(mv), value), else_=incoming)


def location_underlying(session: Session, manual: list[str], prc: sa.Table, core: sa.Table, ok) -> None:
    """Lokasyonun alttaki değeri: gelen satırın değeri."""
    c = core.alias("loc_core")  # prc ve core aynı adlı: takma ad
    for f in manual:
        col = core.c[f]
        session.execute(sa.update(MANUAL).where(MANUAL.c.TableName == "Location", MANUAL.c.FieldName == f,
                                                MANUAL.c.RecordKey == sa.cast(c.c.Id, sa.Unicode(KEY_LENGTH)), prc.c.Code == c.c.Code, ok)
                        .values(_underlying("Location", f, prc.c[f], prc.c.StagingRowId, col)))
