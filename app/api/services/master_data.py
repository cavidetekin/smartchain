"""Ana veri (ekran 03, fonksiyon 10) ve İşlem verisi (ekran 29, fonksiyon 102) ekranları (K-168, K-169): sekmeler, tablolar ve kayıt sayıları.
Satırlar ortak liste uçlarından gelir."""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..lists.master_data import BY_NAME, MASTER_TABS, NAMES, TRANSACTION_TABS
from ..lists.query import Builder
from ..repositories import data_versions
from .lists import _run, today

TABS = {"master": MASTER_TABS, "transaction": TRANSACTION_TABS}


def counts(session: Session | None, screen: str) -> dict:
    """Sekme sırasıyla tablolar: liste adı, tablo seçimindeki ad ve güncel veri versiyonundaki satır sayısı (veri yoksa sayı yok)."""
    def work():
        current = data_versions.read_current(session)
        tabs = []
        for key, names in TABS[screen]:
            tables = []
            for name in names:
                defn = BY_NAME[name]
                count = None
                if current is not None or not defn.versioned:
                    b = Builder(defn, {}, current["Id"] if current else None, today())
                    count = session.execute(sa.select(sa.func.count()).select_from(b.table).where(b.base_clause())).scalar_one()
                tables.append({"list": name, "label": NAMES[defn.table_name], "count": count})
            tabs.append({"key": key, "tables": tables})
        return {"data_version": current["Id"] if current else None, "tabs": tabs}
    return _run(session, work)
