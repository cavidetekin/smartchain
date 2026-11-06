"""SQL çekiminin kaynağı (fonksiyon 01 ve 91, K-130): entegrasyon veritabanını yalnız okur.

Bağlantı aynı instance, aynı kimlik, başka veritabanı; şifre saklanmaz. Bu dosyadan yazma ve DDL çıkmaz (tests/test_sql_source.py denetler).
View adı SQL'e sys.views'da bulunduktan sonra girer; kullanıcıdan SQL alınmaz.
"""
import hashlib
import os
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from db.dictionary import is_additional

from . import structural
from .contract import fields, stg_columns

SIGNAL_TABLE = "ERP_LoadLog"
READY, RUNNING, NO_SIGNAL = "ready", "running", "none"
COMPATIBLE, WITH_WARNINGS, INCOMPATIBLE = "Uyumlu", "Uyarılı", "Hatalı"
FETCH_ROWS = 5000
DATABASE_NAME = re.compile(r"^[A-Za-z0-9_]{1,128}$")
TEXT_TYPES = {"char", "varchar", "nchar", "nvarchar", "text", "ntext"}
INTEGERS = {"tinyint", "smallint", "int", "bigint"}
NUMBERS = INTEGERS | {"decimal", "numeric", "float", "real", "money", "smallmoney"}
DATES = {"date", "datetime", "datetime2", "smalldatetime", "datetimeoffset"}
TYPES_OF_KIND = {"number": NUMBERS, "integer": INTEGERS | {"decimal", "numeric"}, "bool": INTEGERS | {"bit"}, "date": DATES}
KIND_WORDS = {"number": "sayı", "integer": "tam sayı", "bool": "evet / hayır", "date": "tarih"}


class SourceError(Exception):
    """Entegrasyon veritabanına ulaşılamıyor ya da beklenen yapı yok; metni kullanıcıya gider."""


@dataclass(frozen=True)
class Signal:
    """Bir tablonun bitti sinyali (docs/03): tablo satırı ile toplu satırlar birlikte okunur."""
    state: str
    id: int | None = None
    finished_at: datetime | None = None


@dataclass
class ViewCheck:
    """Uyum denetimi: kolon adı birebir. Hata varsa tablo okunmaz, uyarı okumayı durdurmaz."""
    matched: int = 0
    expected: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)  # okunacak kolonlar

    @property
    def status(self) -> str:
        return INCOMPATIBLE if self.errors else WITH_WARNINGS if self.warnings else COMPATIBLE

    @property
    def message(self) -> str | None:
        return " ".join(self.errors or self.warnings)[:400] or None


def valid_database(name: str) -> bool:
    return bool(DATABASE_NAME.match(name))


def _refuse_in_tests(database: str) -> None:
    """Testler geliştirme veritabanına dokunmaz (K-103): okuma bile adı _test ile biten veritabanından olur."""
    if "PYTEST_CURRENT_TEST" in os.environ and not database.lower().endswith("_test"):
        raise RuntimeError(f"Test sırasında veritabanının adı _test ile bitmeli; '{database}' reddedildi.")


def _quoted(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


def definition_hash(definition: str | None) -> str:
    return hashlib.sha256((definition or "").encode("utf-8")).hexdigest()


def compare_columns(table: str, columns: Mapping[str, tuple[str, int]], labels: Mapping[str, str] | None = None) -> ViewCheck:
    """Sözleşme ile view kolonları (ad → tip, en büyük karakter; -1 sınırsız). Veritabanı bilmez."""
    expected = fields(table, labels)
    lengths = {c.name: getattr(c.type, "length", None) for c in stg_columns(table)}
    check = ViewCheck(expected=len(expected))
    known = {f.name for f in expected}
    for f in expected:
        if f.name not in columns:
            (check.errors if f.required else check.warnings).append(f"{'Zorunlu' if f.required else 'İsteğe bağlı'} kolon yok: {f.name} ({f.label}).")
            continue
        check.matched += 1
        check.columns.append(f.name)
        type_name, length = columns[f.name]
        allowed = TYPES_OF_KIND.get(f.kind)
        if allowed and type_name not in allowed:
            check.warnings.append(f"Kolon tipi farklı: {f.name} {KIND_WORDS[f.kind]} alanı, view'da {type_name}; dönüşmeyen satır hata olur.")
        limit = lengths.get(f.name)
        if f.kind == "text" and limit and (length == -1 or length > limit) and type_name in TEXT_TYPES:
            check.warnings.append(f"Kolon uzun: {f.name} en çok {limit} karakter; uzun değer satır hatası olur.")
    for name in columns:
        if name in known:
            continue
        stg = {c.name for c in stg_columns(table)}
        word = "Etiketsiz ek alan" if name in stg and is_additional(name) else "Tanınmayan kolon"
        check.warnings.append(f"{word} yok sayıldı: {name}.")
    return check


def read_signal(rows: list[tuple[int, datetime | None, datetime | None]]) -> Signal:
    """(Id, StartedAt, FinishedAt) satırları. En son başlayan bitmemişse yenileme sürüyor; değilse en son biten geçerli (K-130)."""
    if not rows:
        return Signal(NO_SIGNAL)
    started = max(rows, key=lambda r: (r[1] or r[2] or datetime.min, r[0]))
    if started[2] is None:
        return Signal(RUNNING, started[0])
    done = max((r for r in rows if r[2] is not None), key=lambda r: (r[2], r[0]))
    return Signal(READY, done[0], done[2])


class Source:
    """Bağlam yöneticisi: bağlantı işlem açmaz (AUTOCOMMIT), kilit tutmaz."""

    def __init__(self, base_url: URL, database: str, timeout: int):
        _refuse_in_tests(database)
        if not valid_database(database):
            raise SourceError("SQL kaynağının adı geçersiz.")
        self.database = database
        self.engine = sa.create_engine(base_url.set(database=database), poolclass=NullPool, connect_args={"timeout": timeout})

    def __enter__(self) -> "Source":
        try:
            self.conn = self.engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        except DBAPIError as exc:
            self.engine.dispose()
            raise SourceError(f"SQL kaynağına bağlanılamadı: {self.database}.") from exc
        return self

    def __exit__(self, *_exc) -> None:
        self.conn.close()
        self.engine.dispose()

    def account(self) -> str:
        return self.conn.execute(sa.text("SELECT SUSER_SNAME()")).scalar_one()

    def can_read(self) -> bool:
        """Veritabanında okuma yetkisi var mı (sistem kataloğundan)."""
        return bool(self.conn.execute(sa.text("SELECT HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'SELECT')")).scalar())

    def has_signal_table(self) -> bool:
        return self.conn.execute(sa.text("SELECT OBJECT_ID(:n, 'U')"), {"n": f"dbo.{SIGNAL_TABLE}"}).scalar() is not None

    def signal(self, table: str) -> Signal:
        if not self.has_signal_table():
            raise SourceError(f"{SIGNAL_TABLE} tablosu bulunamadı.")
        rows = self.conn.execute(sa.text(
            f"SELECT Id, StartedAt, FinishedAt FROM dbo.{SIGNAL_TABLE} WHERE EntityName = :t OR EntityName IS NULL"), {"t": table}).all()
        return read_signal([tuple(r) for r in rows])

    def view_exists(self, view: str) -> bool:
        return self.conn.execute(sa.text("SELECT 1 FROM sys.views WHERE name = :n AND schema_id = SCHEMA_ID('dbo')"), {"n": view}).first() is not None

    def _view(self, view: str) -> str:
        if not self.view_exists(view):
            raise SourceError(f"View bulunamadı: {view}.")
        return f"dbo.{_quoted(view)}"

    def view_columns(self, view: str) -> dict[str, tuple[str, int]]:
        name = self._view(view)
        try:
            self.conn.execute(sa.text(f"SELECT TOP 0 * FROM {name}")).close()  # kaynağı kalkmış view burada düşer
        except DBAPIError as exc:
            raise SourceError(f"View okunamıyor: {view}.") from exc
        rows = self.conn.execute(sa.text(
            "SELECT c.name, TYPE_NAME(c.system_type_id), COLUMNPROPERTY(c.object_id, c.name, 'charmaxlen') "
            "FROM sys.columns c WHERE c.object_id = OBJECT_ID(:v) ORDER BY c.column_id"), {"v": f"dbo.{view}"}).all()
        return {r[0]: (r[1], r[2] if r[2] is not None else 0) for r in rows}

    def check_view(self, table: str, view: str, labels: Mapping[str, str] | None = None) -> ViewCheck:
        return compare_columns(table, self.view_columns(view), labels)

    def duplicate_keys(self, table: str, view: str, columns: list[str]) -> int:
        """Tekrar eden anahtar sayısı; yalnız Bağlantıyı test et'te (okumada satır bulgusu olur)."""
        keys = [k for k in structural.key_fields(table) if k in columns]
        if not keys:
            return 0
        names = ", ".join(_quoted(k) for k in keys)
        return self.conn.execute(sa.text(
            f"SELECT COUNT(*) FROM (SELECT 1 AS x FROM {self._view(view)} GROUP BY {names} HAVING COUNT(*) > 1) d")).scalar_one()

    def definition(self, view: str) -> str | None:
        """Şifrelenmiş view'da boş."""
        return self.conn.execute(sa.text("SELECT OBJECT_DEFINITION(OBJECT_ID(:v))"), {"v": f"dbo.{view}"}).scalar()

    def _cursor_rows(self, sql: str, columns: list[str]) -> Iterator[tuple[int, dict[str, object]]]:
        cursor = self.conn.connection.cursor()
        try:
            cursor.execute(sql)
            number = 0
            while batch := cursor.fetchmany(FETCH_ROWS):
                for row in batch:
                    number += 1
                    yield number, dict(zip(columns, row))
        finally:
            cursor.close()

    def read_rows(self, view: str, columns: list[str]) -> Iterator[tuple[int, dict[str, object]]]:
        """(okuma sırası, alan → değer); belleğe alınmaz. Sıra yalnız bu okumada anlamlıdır, kayıt anahtarla bulunur."""
        names = ", ".join(_quoted(c) for c in columns)
        return self._cursor_rows(f"SELECT {names} FROM {self._view(view)}", columns)

    def sample(self, view: str, columns: list[str], rows: int) -> list[tuple[int, dict[str, object]]]:
        names = ", ".join(_quoted(c) for c in columns)
        return list(self._cursor_rows(f"SELECT TOP ({int(rows)}) {names} FROM {self._view(view)}", columns))
