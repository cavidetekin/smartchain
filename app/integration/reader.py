"""Yüklenen Excel dosyasının okuyucusu (fonksiyon 03, K-129). Veritabanı bilmez; satırları akıtır, belleğe almaz."""
import warnings
import zipfile
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
        table = pairs.get("Tablo")
        version = pairs.get("Sürüm")
        first = pairs.get("İlk veri satırı")
        return Identity(str(table) if table else None, int(version) if isinstance(version, (int, float)) else None,
                        int(first) if isinstance(first, (int, float)) and first >= 2 else FIRST_DATA_ROW)

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
