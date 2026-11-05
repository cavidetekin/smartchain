"""Excel yükleme (ekran 02, fonksiyon 03, K-129).

Dosya bir kez okunur: geçerli satırlar kontrol sırasında stg'ye yazılır, parti "Ön kontrol"de olduğu için kimse okumaz. "Devam" partiyi
"Alındı" yapar, "Vazgeç" satırları ve dosyayı siler. Ölçüme göre küçük dosya istek içinde, büyük dosya "Excel ön kontrol" işinde
(motor servisi); ikisi de run_precheck'i çağırır.
"""
import io
import logging
import uuid
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from app.integration import contract, structural
from app.integration.reader import BadFile, Workbook, check_package, template_entity
from app.integration.template import write_template
from app.jobs import queue
from app.jobs.constants import ACTIVE_STATUSES, CHANNEL_EXCEL, STATUS_DONE, STATUS_QUEUED, TYPE_PRECHECK
from app.jobs.settings import JobSettings

from ..errors import AppError
from ..export.describe import tr_number
from ..repositories import audit, imports as repo, lists as lists_repo
from ..settings import get_settings
from . import auth
from .auth import CurrentUser

log = logging.getLogger("smartchain.imports")

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MODE_CHANGED, MODE_FULL = "Değişen", "Tam"
MODES = (MODE_CHANGED, MODE_FULL)
MODE_LABELS = {MODE_CHANGED: "Ekle / güncelle", MODE_FULL: "Tam"}  # pencerede görünen ad; iz bununla yazılır
OBJECT = "ImportBatch"
ACTION_UPLOAD, ACTION_REPORT = "Excel yükleme", "Hata raporu indirme"
CHUNK_ROWS = 5000
MAX_SAME_NOTES = 1000  # liste dışı değer: alan ve değer başına tek bilgi; ERP'nin değerleri her satırda bilgi yazdırmasın
MB = 1024 * 1024


def _entity(table: str) -> contract.Entity:
    found = contract.entity(table)
    if found is None:
        raise AppError("entity_not_found", "Tablo bulunamadı.", 404)
    return found


def _folder() -> Path:
    folder = Path(get_settings().import_dir)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _batch(session: Session, batch_id: int) -> dict:
    found = repo.get_batch(session, batch_id)
    if found is None or found["Method"] != repo.METHOD_EXCEL:
        raise AppError("import_not_found", "Yükleme bulunamadı.", 404)
    return found


def _owned(session: Session, batch_id: int, user: CurrentUser) -> dict:
    found = _batch(session, batch_id)
    if found["UploadedBy"] != user.id:
        raise AppError("import_not_owner", "Bu yüklemeyi yalnız yükleyen sürdürebilir.", 403)
    return found


def limits(session: Session | None, table: str, mode: str) -> dict[str, int]:
    """Dosya alınmadan: tablo ve mod geçerli mi, en büyük dosya boyutu."""
    session = auth._require(session)
    _entity(table)
    if mode not in MODES:
        raise AppError("validation", "Girilen bilgiler geçersiz.", 422, [{"field": "mode", "problem": "Tam ya da Değişen olmalı."}])
    return auth._db(lambda: repo.read_settings(session))


def too_large(max_mb: int) -> AppError:
    return AppError("import_too_large", f"Dosya çok büyük: en çok {max_mb} MB yüklenebilir.", 413)


def temp_path() -> Path:
    return _folder() / f"tmp-{uuid.uuid4().hex}.xlsx"  # openpyxl uzantıya bakar


def _inspect(wb: Workbook, entity: contract.Entity, labels) -> tuple[int | None, list[structural.Finding]]:
    """Dosya düzeyi kontrol: doğru tablo mu, zorunlu kolonlar var mı. Küçük dosyada istek içinde (parti oluşmaz), büyük dosyada işte (parti Hatalı)."""
    identity = wb.identity()
    other = template_entity(identity)
    if identity.table and (other is None or other.table != entity.table):
        raise AppError("import_wrong_entity", f"Bu dosya {entity.name} tablosu içermemektedir.", 422)
    findings = structural.check_columns(entity.table, wb.header(entity), labels)
    errors = [f for f in findings if f.severity == structural.ERROR]
    if errors:
        raise AppError("import_missing_columns", "Dosyanın kolonları şablona uymuyor. Şablonu yeniden indirin.", 422,
                       [{"field": f.field, "problem": f.message} for f in errors])
    notes = list(findings)
    if identity.table is None:
        notes.append(structural.Finding(structural.WARNING, "no_template_info", f"Dosyada şablon bilgisi yok; {entity.name} olarak okundu."))
    elif identity.version != entity.version:
        notes.append(structural.Finding(structural.WARNING, "old_template", f"Dosya şablon v{identity.version} ile hazırlanmış, güncel sürüm v{entity.version}. "
                                                                            "Şablonu yeniden indirmeniz önerilir."))
    return identity.version, notes


def _close_open_batches(session: Session, table: str, user_id: int) -> None:
    """Aynı tabloda tek açık ön kontrol (K-129)."""
    for old in repo.open_batches(session, table, user_id):
        _discard(session, old, repo.CANCELLED)


def start(session: Session | None, user: CurrentUser, table: str, mode: str, file_name: str, temp: Path) -> tuple[dict, int]:
    """Dosya diskte. (cevap, HTTP durumu): küçük dosya 200 özet, büyük dosya 202 parti ve iş.

    Dosyayı açmak metin tablosunu belleğe okur (200.000 satırda saniyeler, K-129): küçük dosya tek açılışla işlenir, büyük dosya istekte hiç açılmaz.
    """
    session = auth._require(session)
    entity = _entity(table)

    def small(settings: dict) -> tuple[dict, int]:
        labels = lists_repo.read_labels(session, entity.table)
        batch_id = None
        try:
            with Workbook(temp) as wb:
                version, notes = _inspect(wb, entity, labels)
                _close_open_batches(session, entity.table, user.id)
                batch_id = repo.create_batch(session, entity.table, mode, file_name, user.id, version)
                repo.insert_findings(session, batch_id, notes)
                session.commit()
                read, too_many = _read_rows(session, batch_id, entity, labels, settings, wb, None)
            _keep_file(session, batch_id, temp)
            _finish(session, batch_id, entity, read, too_many, settings)
        except BadFile as exc:
            raise AppError("import_bad_file", str(exc), 422) from exc
        except AppError:
            raise
        except Exception:
            session.rollback()
            log.exception("Ön kontrol %s düştü", batch_id)
            if batch_id is not None:
                _mark_incomplete(session, batch_id)
            raise AppError("import_failed", "Ön kontrol tamamlanamadı; dosyayı yeniden yükleyin.", 500) from None
        return summary_of(session, batch_id), 200

    def large() -> tuple[dict, int]:
        try:
            check_package(temp)
        except BadFile as exc:
            raise AppError("import_bad_file", str(exc), 422) from exc
        _close_open_batches(session, entity.table, user.id)
        batch_id = repo.create_batch(session, entity.table, mode, file_name, user.id, None)
        _keep_file(session, batch_id, temp)
        job_id = queue.enqueue(session, TYPE_PRECHECK, CHANNEL_EXCEL, user.id, {"batch_id": batch_id},
                               summary=f"{entity.name} · {file_name}"[:200])
        repo.set_batch(session, batch_id, JobId=job_id)
        session.commit()
        return {"batch_id": batch_id, "job_id": job_id}, 202

    def work():
        settings = repo.read_settings(session)
        return small(settings) if temp.stat().st_size <= settings["ImportSyncMaxMb"] * MB else large()

    try:
        return auth._db(work)
    finally:
        temp.unlink(missing_ok=True)


def _keep_file(session: Session, batch_id: int, temp: Path) -> None:
    path = _folder() / f"{batch_id}.xlsx"
    temp.replace(path)
    repo.set_batch(session, batch_id, FilePath=str(path))
    session.commit()


def run_precheck(session: Session, batch_id: int, progress: Callable[[str], None] | None = None) -> bool:
    """İşin gövdesi: aç, dosyayı kontrol et, oku, yaz. Baştan her şeyi sildiği için yeniden deneme güvenlidir. False: parti artık açık değil (vazgeçildi)."""
    batch = repo.get_batch(session, batch_id)
    if batch is None:
        return False
    if batch["Status"] != repo.PENDING:
        if batch["Status"] == repo.CANCELLED:  # iş çalışırken vazgeçildi: temizlik işin
            _clean(session, batch_id)
            session.commit()
        return False
    entity = _entity(batch["EntityName"])
    labels = lists_repo.read_labels(session, entity.table)
    settings = repo.read_settings(session)
    repo.clear_batch_rows(session, entity.table, batch_id)
    repo.set_batch(session, batch_id, RowCount=None, ErrorCount=None)
    session.commit()
    if progress:  # açılış metin tablosunu okur, 200.000 satırda on saniyelerce ilerleme yazılmaz
        progress("Dosya açılıyor")
    try:
        with Workbook(Path(batch["FilePath"])) as wb:
            version, notes = _inspect(wb, entity, labels)
            repo.set_batch(session, batch_id, TemplateVersion=version)
            repo.insert_findings(session, batch_id, notes)
            session.commit()
            read, too_many = _read_rows(session, batch_id, entity, labels, settings, wb, progress)
    except (BadFile, AppError) as exc:  # küçük dosyada 422 olan durumlar: işte parti Hatalı olur, nedeni pencerede yazar
        message = exc.message if isinstance(exc, AppError) else str(exc)
        details = exc.details if isinstance(exc, AppError) else []
        items = [structural.Finding(structural.ERROR, "bad_file", message)]
        items += [structural.Finding(structural.ERROR, "missing_column", d["problem"], field=d.get("field")) for d in details or []]
        repo.insert_findings(session, batch_id, items)
        repo.set_batch(session, batch_id, RowCount=0, ErrorCount=0, Status=repo.FAILED)
        session.commit()
        return True
    return _finish(session, batch_id, entity, read, too_many, settings)


def _read_rows(session: Session, batch_id: int, entity: contract.Entity, labels, settings: dict, wb: Workbook,
               progress: Callable[[str], None] | None) -> tuple[int, bool]:
    """Satırları akıtır: geçerliler ham veriye, sorunlar bulguya, 5.000'lik parçalarla. (okunan, sınır aşıldı mı)."""
    checker = structural.RowChecker(entity.table, labels)
    read = 0
    valid: list[tuple[int, dict]] = []
    found: list[structural.Finding] = []
    noted: set[tuple[str | None, str | None]] = set()

    def keep(finding: structural.Finding) -> bool:
        """Hata hep kalır; bilgi, alan ve değer başına ilk satırla."""
        if finding.severity == structural.ERROR:
            return True
        key = (finding.field, finding.value)
        if key in noted or len(noted) >= MAX_SAME_NOTES:
            return False
        noted.add(key)
        return True

    def flush() -> bool:
        """Parçayı yazar. Vazgeçilmişse False."""
        repo.insert_rows(session, entity.table, checker.fields, batch_id, valid)
        repo.insert_findings(session, batch_id, found)
        session.commit()
        valid.clear()
        found.clear()
        if progress:
            progress(f"{tr_number(read, 0)} satır")
        return repo.status_of(session, batch_id) == repo.PENDING

    too_many = False
    for number, raw in wb.rows(entity, wb.identity().first_row):
        if read >= settings["ImportMaxRows"]:
            too_many = True
            break
        read += 1
        row, findings = checker.check(number, raw)
        if row is not None:
            valid.append((number, row))
        found.extend(f for f in findings if keep(f))
        if read % CHUNK_ROWS == 0 and not flush():
            return read, False
    flush()
    return read, too_many


def _finish(session: Session, batch_id: int, entity: contract.Entity, read: int, too_many: bool, settings: dict) -> bool:
    """Dosya kapandıktan sonra: vazgeçildiyse temizlik, sınır, tekrar eden anahtar, sayılar."""
    if repo.status_of(session, batch_id) != repo.PENDING:  # çalışırken vazgeçildi
        _clean(session, batch_id)
        session.commit()
        return False
    if too_many:
        repo.clear_batch_rows(session, entity.table, batch_id, findings=False)
        repo.insert_findings(session, batch_id, [structural.Finding(structural.ERROR, "too_many_rows", f"Dosyada en çok {tr_number(settings['ImportMaxRows'], 0)} satır olabilir.")])
        repo.set_batch(session, batch_id, RowCount=read, ErrorCount=read, Status=repo.FAILED)
        session.commit()
        return True
    repo.insert_findings(session, batch_id, repo.remove_duplicates(session, entity.table, batch_id))
    errors = repo.counts(session, batch_id)["errors"]
    repo.set_batch(session, batch_id, RowCount=read, ErrorCount=errors, **({"Status": repo.FAILED} if read == 0 or errors >= read else {}))
    session.commit()
    return True


def _unlink(path_text: str | None) -> None:
    if path_text:
        try:
            Path(path_text).unlink(missing_ok=True)
        except OSError:  # başka süreç açık tutuyor olabilir; temizliği 5.4
            log.warning("Dosya silinemedi: %s", path_text)


def _clean(session: Session, batch_id: int) -> None:
    batch = repo.get_batch(session, batch_id)
    repo.clear_batch_rows(session, batch["EntityName"], batch_id, findings=False)
    _unlink(batch["FilePath"])


def _discard(session: Session, batch: dict, status: str) -> None:
    """Parti kapanır; satırlar ve dosya gider. Çalışan iş sonraki parçada durumu görür ve kendi temizler."""
    repo.set_batch(session, batch["Id"], Status=status)
    job = queue.get_job(session, batch["JobId"], JobSettings()) if batch["JobId"] else None
    if job is not None and job["Status"] == STATUS_QUEUED:
        queue.cancel(session, job["Id"], None, batch["UploadedBy"], commit=False)
    if job is None or job["Status"] not in ACTIVE_STATUSES or job["Status"] == STATUS_QUEUED:
        _clean(session, batch["Id"])


def _mark_incomplete(session: Session, batch_id: int) -> None:
    batch = repo.get_batch(session, batch_id)
    if batch is None or batch["Status"] != repo.PENDING:
        return
    repo.set_batch(session, batch_id, Status=repo.INCOMPLETE)
    repo.clear_batch_rows(session, batch["EntityName"], batch_id, findings=False)
    session.commit()


def run_job(session: Session, job_id: int, attempt: int, payload: dict, progress: Callable[[str], None]) -> bool:
    """Motor servisinin ön kontrol işi. Düşerse iş Hata, parti Tamamlanmadı (çağıran)."""
    run_precheck(session, payload["batch_id"], progress)
    batch = repo.get_batch(session, payload["batch_id"])
    return queue.finish(session, job_id, attempt, progress=f"{tr_number(batch['RowCount'] or 0, 0)} satır okundu")


def fail_job(session: Session, payload: dict) -> None:
    session.rollback()
    _mark_incomplete(session, payload["batch_id"])


def summary_of(session: Session, batch_id: int) -> dict:
    batch = _batch(session, batch_id)
    entity = _entity(batch["EntityName"])
    job = queue.get_job(session, batch["JobId"], JobSettings()) if batch["JobId"] else None
    if job is not None and batch["Status"] == repo.PENDING and batch["RowCount"] is None and job["Status"] not in ACTIVE_STATUSES and job["Status"] != STATUS_DONE:
        _mark_incomplete(session, batch_id)  # süreç düştü, iş Hata ya da İptal oldu
        batch = _batch(session, batch_id)
    counted = repo.counts(session, batch_id)
    read = batch["RowCount"]
    errors = batch["ErrorCount"] if batch["ErrorCount"] is not None else counted["errors"]
    checked = read is not None
    version = batch["TemplateVersion"]
    return {
        "batch_id": batch_id, "entity": entity.table, "name": entity.name, "file_name": batch["FileName"], "mode": batch["LoadType"],
        "status": batch["Status"], "checked": checked, "template_version": version, "current_version": entity.version,
        "read": read, "errors": errors if checked else None, "valid": max(read - errors, 0) if checked else None, "notes": counted["notes"] if checked else None,
        "file_findings": repo.file_findings(session, batch_id), "uploaded_by": batch["UploadedBy"],
        "job": {"id": job["Id"], "status": job["Status"], "progress": job["Progress"]} if job else None,
    }


def summary(session: Session | None, batch_id: int) -> dict:
    session = auth._require(session)
    return auth._db(lambda: summary_of(session, batch_id))


def pending(session: Session | None, user: CurrentUser, table: str) -> dict | None:
    session = auth._require(session)
    entity = _entity(table)

    def work():
        found = repo.open_batches(session, entity.table, user.id)
        return summary_of(session, found[0]["Id"]) if found else None

    return auth._db(work)


def continue_batch(session: Session | None, user: CurrentUser, batch_id: int) -> dict:
    """Parti "Alındı"; iz aynı işlemde, yazılamazsa geri alınır (K-108)."""
    session = auth._require(session)

    def work():
        batch = _owned(session, batch_id, user)
        if batch["Status"] != repo.PENDING or batch["RowCount"] is None or batch["RowCount"] - (batch["ErrorCount"] or 0) <= 0:
            raise AppError("import_not_pending", "Bu yükleme sürdürülemez.", 409)
        entity = _entity(batch["EntityName"])
        repo.set_batch(session, batch_id, Status=repo.RECEIVED)
        audit.write_audit(session, ACTION_UPLOAD, user.id, OBJECT, batch["FileName"],
                          {"entity_name": entity.name, "mode": MODE_LABELS.get(batch["LoadType"], batch["LoadType"]), "rows": batch["RowCount"], "valid": batch["RowCount"] - (batch["ErrorCount"] or 0),
                           "errors": batch["ErrorCount"] or 0, "template_version": batch["TemplateVersion"]})
        session.commit()
        return summary_of(session, batch_id)

    return auth._db(work)


def cancel(session: Session | None, user: CurrentUser, batch_id: int) -> dict:
    session = auth._require(session)

    def work():
        batch = _owned(session, batch_id, user)
        if batch["Status"] not in (repo.PENDING, repo.FAILED):
            raise AppError("import_not_pending", "Bu yükleme sürdürülemez.", 409)
        _discard(session, batch, repo.CANCELLED)
        session.commit()
        return summary_of(session, batch_id)

    return auth._db(work)


def error_report(session: Session | None, user: CurrentUser, batch_id: int) -> tuple[bytes, str]:
    """Hatalı satırlar, dosyadaki özgün değerlerle, sonda "Hata" kolonu; şablon düzeninde, düzeltilip yeniden yüklenebilir."""
    session = auth._require(session)

    def work():
        batch = _batch(session, batch_id)
        entity = _entity(batch["EntityName"])
        path = Path(batch["FilePath"]) if batch["FilePath"] else None
        if path is None or not path.exists():
            raise AppError("import_file_gone", "Dosya artık yok; yeniden yükleyin.", 410)
        errors = repo.error_messages(session, batch_id)
        rows = []
        with Workbook(path) as wb:
            for number, raw in wb.rows(entity, wb.identity().first_row):
                if number in errors:
                    rows.append({**raw, contract.ERROR_COLUMN: " · ".join(errors[number])})
        buffer = io.BytesIO()
        write_template(buffer, entity, lists_repo.read_labels(session, entity.table), rows=rows, extra_column=contract.ERROR_COLUMN)
        name = f"smartchain_{entity.slug}_hata-raporu_{batch_id}.xlsx"
        audit.write_audit(session, ACTION_REPORT, user.id, OBJECT, name, {"entity_name": entity.name, "rows": len(rows), "file_name": batch["FileName"]})
        session.commit()
        return buffer.getvalue(), name

    return auth._db(work)

