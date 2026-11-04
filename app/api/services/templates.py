"""Excel şablonu indirme (ekran 02, fonksiyon 02, K-110). Dosya üretilir, iz aynı işlemde yazılır; iz yazılamazsa dosya verilmez."""
import io

from sqlalchemy.orm import Session

from app.integration import contract
from app.integration.template import write_template

from ..errors import AppError
from ..repositories import audit, lists as lists_repo
from . import auth
from .auth import CurrentUser

ACTION = "Şablon indirme"
OBJECT = "Template"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _entity(table: str) -> contract.Entity:
    found = contract.entity(table)
    if found is None:
        raise AppError("entity_not_found", "Tablo bulunamadı.", 404)
    return found


def info(session: Session | None, table: str) -> dict:
    """Şablon bilgisi penceresi."""
    session = auth._require(session)
    entity = _entity(table)

    def work():
        found = contract.fields(entity.table, lists_repo.read_labels(session, entity.table))
        return {"entity": entity.table, "name": entity.name, "version": entity.version, "file_name": entity.file_name,
                "field_count": len(found), "required": [f.label for f in found if f.required]}

    return auth._db(work)


def download(session: Session | None, user: CurrentUser, table: str) -> tuple[bytes, str]:
    """(dosya, ad)."""
    session = auth._require(session)
    entity = _entity(table)

    def work():
        buffer = io.BytesIO()
        found = write_template(buffer, entity, lists_repo.read_labels(session, entity.table))
        audit.write_audit(session, ACTION, user.id, OBJECT, entity.file_name,
                          {"entity_name": entity.name, "version": entity.version, "field_count": len(found)})
        session.commit()
        return buffer.getvalue()

    return auth._db(work), entity.file_name
