"""Senaryoya bağlı tabloların kayıt defteri (K-176, K-177): kopyalama, silme ve "Baz'dan ayır" bu listeyi dolaşır.

Tür:
- Ayar: tam kopya (parametreler, hedefler, planlama ufku, öncelik kuralları, uyarı eşikleri). Kopyalanınca tamamı gelir; ayırmadan etkilenmez.
- Veri: "Baz + fark" (kapasite, limitler, blokaj). Baz'ın satırları temel veridir; öteki senaryo yalnız Baz'dan farkını tutar. Kopyalamada
  kaynağın kendi satırları gelir (kaynak Baz ise hiçbiri: yeni senaryo onları Baz'dan okur). "Baz'dan ayır"da ve "Baz'ı izler: Hayır" ile açılan
  senaryoda tablonun `materialize` işlevi çağrılır: Baz'ın o anki değerleri senaryoya tam kopyalanır.

Yeni bir senaryo tablosu açan adım (7.5 Kapasite yönetimi, limitler, blokaj) tablosunu buraya ekler ve Veri tablosuysa `materialize`'ı bağlar;
senaryo servisine dokunmaz. Test, modelde `ScenarioDefinitionId` taşıyan her `param` tablosunun burada olduğunu doğrular.
"""
from collections.abc import Callable
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata

from . import resolve

SETTING, DATA = "Ayar", "Veri"
KEY = "ScenarioDefinitionId"


@dataclass(frozen=True)
class ScenarioTable:
    name: str            # param şemasındaki tablo
    kind: str            # Ayar | Veri
    # Veri tablosunda: Baz'ın o anki değerlerini senaryoya tam kopyalar (çözümleme katmanıyla birlikte 7.5'te bağlanır)
    materialize: Callable[[Session, int], None] | None = None

    @property
    def table(self) -> sa.Table:
        return metadata.tables[f"param.{self.name}"]


TABLES: tuple[ScenarioTable, ...] = (
    ScenarioTable("PlanningSetting", SETTING),
    ScenarioTable("ObjectiveDefinition", SETTING),
    ScenarioTable("TimeBucketDefinition", SETTING),
    ScenarioTable("WarningThreshold", SETTING),   # uyarı eşikleri (K-190): ayar, tam kopya
    ScenarioTable("PeggingCriterion", SETTING),   # pegging sıralama ölçütleri (K-201): ayar, tam kopya
    # Kapasite girişleri (K-185): fark yapısı ve çözümleme `app/params/resolve.py`'de
    *[ScenarioTable(name, DATA, resolve.materializer(name)) for name in resolve.FIELDS],
)
BY_NAME = {t.name: t for t in TABLES}


def model_tables() -> set[str]:
    """Modelde senaryo kimliği taşıyan `param` tabloları (kayıt defteriyle karşılaştırmak için)."""
    return {t.name for t in metadata.sorted_tables if t.schema == "param" and KEY in t.c}


def _copied_columns(table: sa.Table) -> list[sa.Column]:
    return [c for c in table.columns if c.name != KEY and not (c.primary_key and c.autoincrement is True)]


def copy_rows(session: Session, source_id: int, target_id: int, source_is_base: bool) -> dict[str, int]:
    """Kaynağın satırlarını hedefe kopyalar; Veri tablosunda kaynak Baz ise kopyalanmaz. Tablo → satır sayısı."""
    counts = {}
    for entry in TABLES:
        if entry.kind == DATA and source_is_base:
            counts[entry.name] = 0
            continue
        t = entry.table
        cols = _copied_columns(t)
        select = sa.select(sa.literal(target_id, sa.Integer), *cols).where(t.c[KEY] == source_id)
        counts[entry.name] = session.execute(sa.insert(t).from_select([KEY, *[c.name for c in cols]], select)).rowcount
    return counts


def delete_rows(session: Session, scenario_id: int) -> dict[str, int]:
    return {entry.name: session.execute(sa.delete(entry.table).where(entry.table.c[KEY] == scenario_id)).rowcount for entry in TABLES}


def materialize(session: Session, scenario_id: int) -> None:
    """Baz'dan ayrılan (ya da Baz'ı izlemeden açılan) senaryoda Veri tablolarının Baz değerleri tam kopyalanır."""
    for entry in TABLES:
        if entry.kind == DATA and entry.materialize is not None:
            entry.materialize(session, scenario_id)
