"""Yapısal kontrol (fonksiyon 03 ön kontrol, fonksiyon 04-01; K-129). Sözleşmeden okur, veritabanına bağlanmaz.

Tek kod: Excel okuyucu ham hücreyi, 3.3 ve 3.4 `stg` satırını verir. "Boşsa satır yüklenmez" alanlar burada reddedilir;
veri kuralıyla dolan alanların (Resource.CapacityUnit) boş kontrolü kurallardan sonradır (docs/06).
"""
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import sqlalchemy as sa

from db.dictionary import is_additional
from db.models import metadata

from .contract import TemplateField, fields, stg_columns

ERROR, WARNING, INFO = "Hata", "Uyarı", "Bilgi"
VALUE_LENGTH = 255
TRUE_WORDS, FALSE_WORDS = {"1", "true", "doğru", "evet"}, {"0", "false", "yanlış", "hayır"}
INT_MAX = 2_147_483_647


@dataclass(frozen=True)
class Finding:
    severity: str
    check: str
    message: str
    row: int | None = None
    field: str | None = None
    value: str | None = None
    key: str | None = None


class BadValue(ValueError):
    """Hücre alanın tipine uymuyor; metni kullanıcıya gider."""

    def __init__(self, check: str, message: str):
        super().__init__(message)
        self.check, self.message = check, message


def key_fields(table: str) -> list[str]:
    """Sözleşmedeki anahtar (docs/03 ANAHTAR = UK), alan sırasıyla."""
    return [c.name for c in stg_columns(table) if "UK" in c.info.get("key", "")]


def check_columns(table: str, header: Sequence[object], labels: Mapping[str, str] | None = None) -> list[Finding]:
    """Başlık: eksik zorunlu kolon hata; tanınmayan kolon ve etiketsiz ek alan bilgi (yok sayılır, K-88)."""
    found = fields(table, labels)
    known = {f.name for f in found}
    names = [str(h).strip() for h in header if h not in (None, "")]
    out = [Finding(ERROR, "missing_column", f"Zorunlu kolon yok: {f.name} ({f.label}). Şablonu yeniden indirin.", field=f.name)
           for f in found if f.required and f.name not in names]
    out += [Finding(ERROR, "repeated_column", f"Kolon iki kez var: {n}.", field=n) for n in sorted({n for n in names if names.count(n) > 1})]
    stg = {c.name for c in stg_columns(table)}
    for name in dict.fromkeys(names):
        if name in known:
            continue
        if name in stg and is_additional(name):
            out.append(Finding(INFO, "unlabelled_column", f"Etiketsiz ek alan yok sayıldı: {name}.", field=name))
        else:
            out.append(Finding(INFO, "unknown_column", f"Tanınmayan kolon yok sayıldı: {name}.", field=name))
    return out


def _text(value) -> str | None:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # sayı hücresindeki kod: 1001.0 değil 1001
    if isinstance(value, datetime):
        value = value.date() if (value.hour, value.minute, value.second) == (0, 0, 0) else value
    text = str(value).strip()
    return text or None


def _decimal(value) -> Decimal:
    if isinstance(value, bool):
        return Decimal(int(value))
    if isinstance(value, (int, float, Decimal)):
        if isinstance(value, float) and not math.isfinite(value):
            raise BadValue("type", "Sayı bekleniyor.")
        return Decimal(str(value))
    text = str(value).strip().replace(" ", "")
    if "," in text:  # Türkçe biçim: 1.234,5
        text = text.replace(".", "").replace(",", ".")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise BadValue("type", "Sayı bekleniyor.") from exc
    if not number.is_finite():
        raise BadValue("type", "Sayı bekleniyor.")
    return number


def _date(value) -> date | datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = str(value).strip()
    for pattern in ("%d.%m.%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            pass
    raise BadValue("type", "Tarih bekleniyor (gg.aa.yyyy).")


def convert(kind: str, value, length: int | None = None, whole_digits: int | None = None):
    """Ham hücre → stg değeri. Boş ise None; uymuyorsa BadValue."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if kind == "text":
        text = _text(value)
        if text is not None and length and len(text) > length:
            raise BadValue("length", f"En çok {length} karakter olabilir ({len(text)}).")
        return text
    if kind == "bool":
        word = str(int(value)) if isinstance(value, (bool, int, float)) and float(value).is_integer() else str(value).strip().casefold()
        if word in TRUE_WORDS:
            return 1
        if word in FALSE_WORDS:
            return 0
        raise BadValue("type", "1 ya da 0 bekleniyor.")
    if kind in ("date", "datetime"):
        return _date(value)
    if type(value) in (int, float) and math.isfinite(value) and kind == "number":  # en sık yol: Excel sayı hücresi
        if whole_digits is not None and abs(value) >= 10 ** whole_digits:
            raise BadValue("range", f"Sayı alana sığmıyor: virgülden önce en çok {whole_digits} basamak.")
        return float(value)
    number = _decimal(value)
    if kind == "integer":
        if number != number.to_integral_value():
            raise BadValue("type", "Tam sayı bekleniyor.")
        if abs(number) > INT_MAX:
            raise BadValue("range", "Sayı alana sığmıyor.")
        return int(number)
    if whole_digits is not None and abs(number) >= Decimal(10) ** whole_digits:
        raise BadValue("range", f"Sayı alana sığmıyor: virgülden önce en çok {whole_digits} basamak.")
    return float(number)


@dataclass
class RowChecker:
    """Bir tablonun satır kontrolü. check: (stg değerleri ya da None, bulgular). Hata varsa satır ham veriye yazılmaz."""
    table: str
    labels: Mapping[str, str] | None = None
    fields: list[TemplateField] = field(init=False)

    def __post_init__(self):
        self.fields = fields(self.table, self.labels)
        columns = {c.name: c for c in stg_columns(self.table)}
        self._length = {f.name: getattr(columns[f.name].type, "length", None) for f in self.fields}
        self._digits = {}
        for f in self.fields:
            t = columns[f.name].type
            if f.kind == "number":
                self._digits[f.name] = t.precision - t.scale
        self._key = key_fields(self.table)

    def row_key(self, raw: Mapping[str, object]) -> str | None:
        parts = [_text(raw[n]) for n in self._key if raw.get(n) not in (None, "")]
        return " · ".join(p for p in parts if p)[:200] or None

    def check(self, row_no: int | None, raw: Mapping[str, object]) -> tuple[dict | None, list[Finding]]:
        out, findings = {}, []

        def add(severity, check, message, f, value=None):
            shown = None if value is None else _text(value)
            findings.append(Finding(severity, check, message, row_no, f.label, shown[:VALUE_LENGTH] if shown else None, self.row_key(raw)))

        for f in self.fields:
            value = raw.get(f.name)
            try:
                converted = convert(f.kind, value, self._length[f.name], self._digits.get(f.name))
            except BadValue as exc:
                add(ERROR, exc.check, exc.message, f, value)
                continue
            out[f.name] = converted
            if converted is None:
                if f.required:
                    add(ERROR, "required", "Zorunlu alan boş.", f)
            elif f.values and converted not in f.values:
                add(INFO, "value_list", f"Smartchain değerleri: {', '.join(f.values)}.", f, value)
        return (None if any(x.severity == ERROR for x in findings) else out), findings


def has_key(table: str) -> bool:
    return bool(key_fields(table))


def duplicate_query(table: str, batch_id: int) -> sa.Select:
    """Partideki tekrar eden anahtarlar (K-129). SQL'de: Excel, SQL arayüzü ve API aynı sorguyu kullanır, karşılaştırma veritabanı harmanlamasıyla."""
    t = metadata.tables[f"stg.{table}"]
    keys = [t.c[n] for n in key_fields(table)]
    counted = sa.select(t.c.StagingRowId, t.c.SourceRowNo, *keys, sa.func.count().over(partition_by=keys).label("n"),
                        sa.func.dense_rank().over(order_by=keys).label("grp")).where(t.c.ImportBatchId == batch_id).subquery("x")
    return sa.select(counted).where(counted.c.n > 1).order_by(counted.c.grp, counted.c.SourceRowNo, counted.c.StagingRowId)


def duplicate_message(row_numbers: Sequence[int]) -> str:
    """Aynı kayıt 201 ve 202. satırlarda"""
    rows = [str(n) for n in row_numbers]
    return f"Aynı kayıt {', '.join(rows[:-1])} ve {rows[-1]}. satırlarda"
