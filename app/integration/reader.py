"""Yüklenen Excel dosyasının okuyucusu (fonksiyon 03, K-129). Veritabanı bilmez; satırları akıtır, belleğe almaz."""
import posixpath
import re
import warnings
import zipfile
from xml.etree import ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from .contract import FIRST_DATA_ROW, Entity, entity
from .template import NOTES_SHEET, VERSION_SHEET

MAX_UNPACKED_BYTES = 4 * 1024 * 1024 * 1024  # açılmış toplam boyut sınırı: sıkıştırma bombası
REQUIRED_PARTS = ("[Content_Types].xml", "xl/workbook.xml")


class BadFile(ValueError):
    """Dosya açılamadı ya da xlsx değil; metni kullanıcıya gider."""


@dataclass(frozen=True)
class Identity:
    """Gizli sayfadan: tablo ve sürüm. Sayfa yoksa boş."""
    table: str | None
    version: int | None
    first_row: int


def check_package(path: Path, max_unpacked: int = MAX_UNPACKED_BYTES) -> None:
    """Açmadan önce: gerçekten xlsx mi, makro içeriyor mu, açılınca sınırı aşıyor mu."""
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
    except (zipfile.BadZipFile, OSError) as exc:
        raise BadFile("Dosya okunamadı: geçerli bir Excel (.xlsx) dosyası değil.") from exc
    names = {i.filename for i in infos}
    if not all(p in names for p in REQUIRED_PARTS):
        raise BadFile("Dosya okunamadı: geçerli bir Excel (.xlsx) dosyası değil.")
    if "xl/vbaProject.bin" in names:
        raise BadFile("Makro içeren dosya yüklenemez; .xlsx olarak kaydedin.")
    if sum(i.file_size for i in infos) > max_unpacked:
        raise BadFile("Dosya açıldığında çok büyük; yüklenemez.")


_COL = re.compile(r"^([A-Z]+)")


def _identity_from_pairs(pairs: dict) -> Identity:
    table = pairs.get("Tablo")
    version = pairs.get("Sürüm")
    first = pairs.get("İlk veri satırı")
    return Identity(str(table) if table else None, int(version) if isinstance(version, (int, float)) else None,
                    int(first) if isinstance(first, (int, float)) and first >= 2 else FIRST_DATA_ROW)


def _number(text: str):
    try:
        value = float(text)
    except ValueError:
        return text
    return int(value) if value.is_integer() else value


def _ns(el) -> str:
    """Öğenin ad alanı (etiket "{ad alanı}ad"); sabit adres yazılmaz, Strict OOXML dosyası da okunur."""
    return el.tag[1:].split("}", 1)[0] if el.tag.startswith("{") else ""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def quick_identity(path: Path) -> Identity:
    """Şablon bilgisi dosyayı açmadan (K-158): yalnız gizli sayfanın XML'i ve gerekiyorsa paylaşılan metinlerin baştaki kısmı okunur.
    Büyük dosyada metin tablosu belleğe alınmaz (K-129). Sayfa yoksa boş kimlik."""
    check_package(path)
    try:
        with zipfile.ZipFile(path) as z:
            book = ET.fromstring(z.read("xl/workbook.xml"))
            sheet = next((s for s in book.iter(f"{{{_ns(book)}}}sheet") if s.get("name") == VERSION_SHEET), None)
            if sheet is None:
                return Identity(None, None, FIRST_DATA_ROW)
            rel_id = next(v for k, v in sheet.attrib.items() if _local(k) == "id")
            rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            target = next(r.get("Target") for r in rels.iter(f"{{{_ns(rels)}}}Relationship") if r.get("Id") == rel_id)
            part = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
            root = ET.fromstring(z.read(part))
            m = _ns(root)
            cells: list[tuple[int, str, str, str | None]] = []   # (satır, kolon, tip, değer)
            for c in root.iter(f"{{{m}}}c"):
                ref, kind = c.get("r", ""), c.get("t", "n")
                found = _COL.match(ref)
                col = found.group(1) if found else ""
                if col not in ("A", "B"):
                    continue
                if kind == "inlineStr":
                    value = "".join(t.text or "" for t in c.iter(f"{{{m}}}t"))
                else:
                    v = c.find(f"{{{m}}}v")
                    value = v.text if v is not None else None
                cells.append((int(ref[len(col):] or 0), col, kind, value))
            wanted = {int(v) for _, _, k, v in cells if k == "s" and v is not None}
            shared: dict[int, str] = {}
            if wanted and "xl/sharedStrings.xml" in z.namelist():
                with z.open("xl/sharedStrings.xml") as f:
                    index = 0
                    for _event, el in ET.iterparse(f):
                        if _local(el.tag) == "si":
                            if index in wanted:
                                shared[index] = "".join(t.text or "" for t in el.iter() if _local(t.tag) == "t")
                                if len(shared) == len(wanted):
                                    break
                            index += 1
                            el.clear()
    except (KeyError, StopIteration, ET.ParseError, zipfile.BadZipFile, OSError) as exc:
        raise BadFile("Dosya okunamadı: geçerli bir Excel (.xlsx) dosyası değil.") from exc
    rows: dict[int, dict[str, object]] = {}
    for row, col, kind, value in cells:
        resolved = shared.get(int(value)) if kind == "s" and value is not None else (_number(value) if kind == "n" and value is not None else value)
        rows.setdefault(row, {})[col] = resolved
    pairs = {str(r["A"]).strip(): r.get("B") for r in rows.values() if r.get("A") not in (None, "")}
    return _identity_from_pairs(pairs)


class Workbook:
    """Bağlam yöneticisi: dosyayı yalnız okuma kipinde açar, çıkışta kapatır (Windows'ta dosya silinebilsin)."""

    def __init__(self, path: Path):
        self.path = path

    def __enter__(self) -> "Workbook":
        check_package(self.path)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # openpyxl biçim uyarıları kullanıcıyı ilgilendirmez
                self.wb = load_workbook(self.path, read_only=True, data_only=True)
        except (InvalidFileException, KeyError, ValueError, OSError, zipfile.BadZipFile) as exc:
            raise BadFile("Dosya okunamadı: geçerli bir Excel (.xlsx) dosyası değil.") from exc
        return self

    def __exit__(self, *_exc) -> None:
        self.wb.close()

    def identity(self) -> Identity:
        if VERSION_SHEET not in self.wb.sheetnames:
            return Identity(None, None, FIRST_DATA_ROW)
        pairs = {}
        for row in self.wb[VERSION_SHEET].iter_rows(values_only=True, max_col=2):
            if row and row[0] not in (None, ""):
                pairs[str(row[0]).strip()] = row[1] if len(row) > 1 else None
        return _identity_from_pairs(pairs)

    def data_sheet(self, target: Entity):
        if target.name in self.wb.sheetnames:
            ws = self.wb[target.name]
        else:
            names = [n for n in self.wb.sheetnames if n not in (NOTES_SHEET, VERSION_SHEET)]
            if not names:
                raise BadFile("Dosyada veri sayfası yok.")
            ws = self.wb[names[0]]
        ws.reset_dimensions()  # bazı üreticiler boyutu yanlış yazar; satırlar kesilmesin
        return ws

    def header(self, target: Entity) -> list[object]:
        for row in self.data_sheet(target).iter_rows(min_row=1, max_row=1, values_only=True):
            return list(row)
        return []

    def rows(self, target: Entity, first_row: int) -> Iterator[tuple[int, dict[str, object]]]:
        """(Excel satır no, alan → ham değer); tamamen boş satır atlanır."""
        names = [str(h).strip() if h not in (None, "") else None for h in self.header(target)]
        for number, row in enumerate(self.data_sheet(target).iter_rows(min_row=first_row, values_only=True), first_row):
            data = {n: v for n, v in zip(names, row) if n}
            if any(v is not None and not (isinstance(v, str) and not v.strip()) for v in data.values()):
                yield number, data


def template_entity(identity: Identity) -> Entity | None:
    return entity(identity.table) if identity.table else None
