"""Alan değişikliği (K-173; fonksiyon 14): kaydın geçmişi `adm.FieldChange`'te, değişiklik anında aynı veritabanı işleminde yazılır.

Yazanlar: aktarım (yeni kayıt, değişen kaydın değişen alanları, kapanan kayıt; Lokasyon ve Birim dahil), manuel değer girme ve kaldırma,
Aşama 7'de Smartchain girişleri. Okurken versiyon farkı çıkarılmaz: manuel değer ve Smartchain alanları güncel versiyon satırını yerinde
değiştirir, Lokasyon ve Birim versiyonsuzdur, kural izi yalnız güncel hâli tutar. Değerler alanın tipinden metne çevrilmiş hâldedir
(`app.manual.as_text`); okurken alanın tipine ve ondalığına göre biçimlenir (`format_value`).
"""
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.manual import EFFECT, KEY_LENGTH, MANUAL, as_text, core_table, kind
from db.models import metadata

FIELD_CHANGE = metadata.tables["adm.FieldChange"]
DATA_VERSION = metadata.tables["adm.DataVersion"]
CREATED, CHANGED, CLOSED = "Oluştu", "Değişti", "Kapandı"
TRANSFER, MANUAL_SOURCE, MANUAL_REMOVE = "Aktarım", "Manuel değer", "Manuel değer kaldırma"
MANUAL_KEPT = "Manuel değer korundu"
VALUE_LENGTH = 400
# İzlenmeyen kolonlar: kimlik, versiyon ve sistem alanları
SYSTEM_COLUMNS = frozenset({"Id", "VersionFrom", "VersionTo", "ImportBatchId", "BusinessKey", "UpdatedAt", "IsSynthetic"})


def tracked_columns(table: str) -> list[str]:
    """Geçmişi tutulan alanlar: sistem ve ön hesap dışındaki iş alanları."""
    t = core_table(table)
    return [c.name for c in t.c if c.name not in SYSTEM_COLUMNS and (c.info or {}).get("source") not in ("Sistem", "Ön hesap")]


def current_version(session: Session) -> int | None:
    return session.execute(sa.select(sa.func.max(DATA_VERSION.c.Id))).scalar()


def _text(value) -> str | None:
    return None if value is None else str(value)[:VALUE_LENGTH]


def record(session: Session, table: str, key, field: str | None, old: str | None, new: str | None, source: str, user_id: int | None,
           change_type: str = CHANGED, rule_id: int | None = None, note: str | None = None) -> None:
    """Smartchain'de yapılan bir değişiklik (manuel değer, Aşama 7 girişleri): o anki güncel veri versiyonuyla."""
    session.execute(sa.insert(FIELD_CHANGE).values(
        TableName=table, RecordKey=str(key), FieldName=field, ChangeType=change_type, OldValue=_text(old), NewValue=_text(new),
        DataVersionId=current_version(session), At=sa.func.sysutcdatetime(), Source=source, UserId=user_id, DataRuleId=rule_id, Note=note))


# ------------------------------------------------------------------ aktarım

def _base(entity: str, run, key: sa.ColumnElement, change_type: str) -> list:
    return [sa.literal(entity, sa.Unicode(60)), sa.cast(key, sa.Unicode(KEY_LENGTH)), sa.literal(change_type, sa.Unicode(10)),
            sa.literal(run.version, sa.BigInteger), sa.literal(run.now, sa.DateTime), sa.literal(TRANSFER, sa.Unicode(40)),
            sa.literal(getattr(run, "user_id", None), sa.Integer)]


BASE_COLS = ["TableName", "RecordKey", "ChangeType", "DataVersionId", "At", "Source", "UserId"]


def _rule(entity: str, prc_field: str | None, staging_row) -> sa.ColumnElement:
    if prc_field is None:
        return sa.null()
    return (sa.select(EFFECT.c.DataRuleId).where(EFFECT.c.EntityName == entity, EFFECT.c.StagingRowId == staging_row, EFFECT.c.FieldName == prc_field)
            .limit(1).correlate_except(EFFECT).scalar_subquery())


def write_transfer(session: Session, m, run, tmp: sa.Table, ok: int, keep: int, differs: Callable) -> None:
    """Versiyonlu tablonun aktarımı (karşılaştırmadan sonra, kapatmadan önce): yeni kayıt, değişen alan (kural varsa kural), kapanan kayıt."""
    t = m.core
    session.execute(sa.insert(FIELD_CHANGE).from_select(BASE_COLS, sa.select(*_base(m.entity, run, tmp.c.Id, CREATED))
                                                        .where(tmp.c.St == ok, tmp.c.M == sa.false())))
    to_prc = {core: f for f in [c.name for c in m.prc.columns] if (core := m.prc_to_core(f))}
    c = t.alias("fc_cur")
    changed = session.execute(sa.select(tmp.c.Id).where(tmp.c.St == ok, tmp.c.Ch == sa.true()).limit(1)).first() is not None
    for n in (m.compare if changed else ()):  # değişen kayıt yoksa alan alan karşılaştırma yok
        col = t.c[n]
        sel = (sa.select(*_base(m.entity, run, tmp.c.Id, CHANGED), sa.literal(n, sa.Unicode(60)), as_text(c.c[n], col), as_text(tmp.c[n], col),
                         _rule(m.entity, to_prc.get(n), tmp.c.StagingRowId))
               .select_from(tmp.join(c, sa.and_(c.c.Id == tmp.c.Id, c.c.VersionTo.is_(None))))
               .where(tmp.c.St == ok, tmp.c.Ch == sa.true(), differs(c.c[n], tmp.c[n])))
        session.execute(sa.insert(FIELD_CHANGE).from_select([*BASE_COLS, "FieldName", "OldValue", "NewValue", "DataRuleId"], sel))
    gone = ~sa.exists().where(tmp.c.Id == t.c.Id, tmp.c.St.in_([ok, keep]))
    session.execute(sa.insert(FIELD_CHANGE).from_select(BASE_COLS, sa.select(*_base(m.entity, run, t.c.Id, CLOSED)).where(t.c.VersionTo.is_(None), gone)))


def write_manual_kept(session: Session, entity: str, run, core: sa.Table, field: str, hit: list, incoming, staging_row) -> None:
    """Manuel değerin korunduğu hücrede alttaki değer değiştiyse (hücre değişmez): eski ve yeni alttaki değer, "Manuel değer korundu"."""
    col = core.c[field]
    from app.manual import differs, from_text
    sel = (sa.select(*_base(entity, run, sa.cast(MANUAL.c.RecordKey, sa.Unicode(KEY_LENGTH)), CHANGED), sa.literal(field, sa.Unicode(60)),
                     MANUAL.c.UnderlyingValue, as_text(incoming, col), _rule(entity, field, staging_row), sa.literal(MANUAL_KEPT, sa.Unicode(100)))
           .where(*hit, differs(from_text(MANUAL.c.UnderlyingValue, col), incoming, col)))
    session.execute(sa.insert(FIELD_CHANGE).from_select([*BASE_COLS, "FieldName", "OldValue", "NewValue", "DataRuleId", "Note"], sel))


def snapshot_location(session: Session) -> dict:
    """Lokasyon (versiyonsuz, birkaç satır) aktarımdan önce ve sonra okunur; fark Python'da çıkarılır (prc ve core aynı adlı)."""
    t = core_table("Location")
    names = [n for n in tracked_columns("Location") if n != "Code"]
    rows = session.execute(sa.select(t.c.Id, t.c.Code, *[as_text(t.c[n], t.c[n]).label(n) for n in names])).mappings().all()
    manual = session.execute(sa.select(MANUAL.c.RecordKey, MANUAL.c.FieldName, MANUAL.c.UnderlyingValue).where(MANUAL.c.TableName == "Location")).all()
    return {"rows": {r["Code"]: dict(r) for r in rows}, "manual": {(m.RecordKey, m.FieldName): m.UnderlyingValue for m in manual}, "names": names}


def write_location(session: Session, run, before: dict, after: dict) -> None:
    """Lokasyonun yeni, değişen (manuel değerin korunduğu alanda alttaki değer) ve kapanan kayıtları."""
    prc = metadata.tables["prc.Location"]
    staging = dict(session.execute(sa.select(prc.c.Code, prc.c.StagingRowId)).all())
    rules = {(r.StagingRowId, r.FieldName): r.DataRuleId for r in session.execute(
        sa.select(EFFECT.c.StagingRowId, EFFECT.c.FieldName, EFFECT.c.DataRuleId).where(EFFECT.c.EntityName == "Location")).all()}
    base = {"TableName": "Location", "DataVersionId": run.version, "At": run.now, "Source": TRANSFER, "UserId": getattr(run, "user_id", None),
            "FieldName": None, "OldValue": None, "NewValue": None, "DataRuleId": None, "Note": None}
    out = []
    for code, row in after["rows"].items():
        key = str(row["Id"])
        old = before["rows"].get(code)
        if old is None:
            continue  # yeni: write_created_unversioned
        for n in after["names"]:
            rule = rules.get((staging.get(code), n))
            if n == "IsActive" and old[n] != row[n] and row[n] == "0":
                out.append({**base, "RecordKey": key, "ChangeType": CLOSED})
            elif old[n] != row[n]:
                out.append({**base, "RecordKey": key, "ChangeType": CHANGED, "FieldName": n, "OldValue": _text(old[n]), "NewValue": _text(row[n]), "DataRuleId": rule})
            elif (key, n) in after["manual"] and before["manual"].get((key, n)) != after["manual"][(key, n)]:
                out.append({**base, "RecordKey": key, "ChangeType": CHANGED, "FieldName": n, "OldValue": _text(before["manual"].get((key, n))),
                            "NewValue": _text(after["manual"][(key, n)]), "DataRuleId": rule, "Note": MANUAL_KEPT})
    if out:
        session.execute(sa.insert(FIELD_CHANGE), out)


def write_created_unversioned(session: Session, run, table: str) -> None:
    """Lokasyon ve Birim: oluşma satırı olmayan kayıtlar yeni eklenmiştir (eskiler geçişte doldurulur)."""
    t = core_table(table)
    key = t.c.Id if "Id" in t.c else t.c.Code
    seen = sa.exists().where(FIELD_CHANGE.c.TableName == table, FIELD_CHANGE.c.RecordKey == sa.cast(key, sa.Unicode(KEY_LENGTH)), FIELD_CHANGE.c.ChangeType == CREATED)
    session.execute(sa.insert(FIELD_CHANGE).from_select(BASE_COLS, sa.select(*_base(table, run, key, CREATED)).where(~seen)))


# ------------------------------------------------------------------ okurken biçim

def _tr_number(value: Decimal, decimals: int | None) -> str:
    if decimals is None:  # birimden ondalık: gereken kadar (en çok 6)
        text = f"{value:,.6f}".rstrip("0").rstrip(".")
    else:
        text = f"{value:,.{decimals}f}"
    return text.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")


def format_value(table: str, field: str | None, text: str | None, decimals: dict[str, int] | None = None, percent: frozenset[str] = frozenset()) -> str | None:
    """Saklanan metin ekrandaki biçime (K-88): sayı Türkçe ve alanın ondalığıyla, yüzde, tarih gg.aa.yyyy, bayrak Evet / Hayır."""
    if text is None or text == "" or field is None:
        return text
    try:
        col = core_table(table).c.get(field)
    except KeyError:
        return text
    if col is None:
        return text
    k = kind(col)
    try:
        if k == "bool":
            return "Evet" if text in ("1", "True", "true") else "Hayır"
        if k == "date":
            return date.fromisoformat(text[:10]).strftime("%d.%m.%Y")
        if k == "datetime":
            return datetime.fromisoformat(text).strftime("%d.%m.%Y %H:%M")
        if k == "integer":
            return _tr_number(Decimal(text), 0)
        if k == "number":
            d = (decimals or {}).get(field)
            if field in percent:
                return "%" + _tr_number(Decimal(text) * 100, 2 if d is None else d)
            return _tr_number(Decimal(text), d)
    except (ValueError, InvalidOperation):
        return text
    return text
