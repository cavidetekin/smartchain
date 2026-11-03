"""Yetki matrisinin görüntülenmesi ve Excel'i (fonksiyon 90, K-100): ekranda grup, Excel'de fonksiyon düzeyinde."""
import io
from datetime import datetime

from sqlalchemy.orm import Session

from app import __version__

from .. import permissions as perm
from ..export.writer import XlsxWriter
from ..repositories import export as export_repo
from . import auth
from .auth import CurrentUser

LEVEL_TEXT = {"full": "Tam", "owner": "Sahibi", "self": "Kendi", "read": "Salt okunur", "none": "Yok"}
LIST_NAME = "permissions"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _text_column(field: str, label: str) -> dict:
    return {"field": field, "label": label, "type": "text"}


def _group_name(no: int) -> str:
    return next(g.name for g in perm.GROUP_ROWS if g.first <= no <= g.last)


def export(session: Session | None, user: CurrentUser) -> tuple[bytes, str]:
    """(dosya, ad). İz yazılamazsa dosya verilmez (fonksiyon 87)."""
    session = auth._require(session)
    matrix = perm.matrix()
    now = datetime.now()
    name = f"smartchain_yetki-matrisi_{now:%Y-%m-%d_%H%M}.xlsx"
    columns = [{"field": "No", "label": "No", "type": "integer", "decimals": 0},
               _text_column("Function", "Fonksiyon"), _text_column("Group", "Grup"),
               *[_text_column(role, role) for role in matrix["roles"]]]
    buffer = io.BytesIO()
    writer = XlsxWriter(buffer, columns)
    writer.header()
    for f in matrix["functions"]:
        writer.data_row({"No": f["no"], "Function": f["name"], "Group": _group_name(f["no"]),
                         **{role: LEVEL_TEXT[level] for role, level in f["levels"].items()}})
    writer.info_sheet([("Liste", "Yetki matrisi"), ("Satırlar", str(len(matrix["functions"]))),
                       ("Dışa aktaran", user.full_name or user.user_name), ("Zaman", f"{now:%d.%m.%Y %H:%M}"),
                       ("Smartchain", __version__)])
    writer.save()

    def work():
        export_repo.write_audit(session, user.id, LIST_NAME, name, {"list": LIST_NAME, "rows": len(matrix["functions"])})
        session.commit()

    auth._db(work)
    return buffer.getvalue(), name
