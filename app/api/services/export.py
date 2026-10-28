"""Excel'e aktarım (K-91, K-93; fonksiyon 86, docs/08 "Dışa aktarım").

Ekranda ne görünüyorsa o aktarılır: aynı liste sözleşmesi (K-87) ve grup ağacı (K-90). Satır sayısı ExportSyncMaxRows'u
aşmıyorsa dosya hemen döner; aşıyorsa "Dışa aktarım" kanalında iş olarak kuyruğa girer (motor servisi üretir).
Her aktarım AuditLog'a yazılır; iz yazılamazsa dosya verilmez.
"""
import io
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app import __version__
from app.jobs import queue
from app.jobs.constants import CHANNEL_EXPORT, STATUS_DONE, TYPE_EXPORT
from app.jobs.settings import JobSettings
from ..errors import AppError
from ..export import describe
from ..export.writer import XlsxWriter
from ..lists import LISTS, ListDefinition
from ..lists.groups import build_tree
from ..lists.query import UNIT, Builder, ListQueryError
from ..lists.request import ExportRequest
from ..repositories import data_versions, export as repo, lists as list_repo, views as view_repo
from ..settings import get_settings
from . import lists as list_service

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DB_DOWN = "Veritabanına bağlanılamıyor; dışa aktarım yapılamadı."
PROGRESS_EVERY = 5000


@dataclass
class Plan:
    """Kapsamdan çıkan aktarım: kolonlar, sorgu parçaları, satır sayısı, dosya adı, Bilgi sayfası."""
    defn: ListDefinition
    builder: Builder
    columns: list[dict]
    fields: list[str]
    filters: list
    group_by: list[str]
    specs: dict
    rows: int
    file_name: str
    version: dict
    info: list[tuple[str, str]] = field(default_factory=list)


def export_path(job_id: int) -> Path:
    return Path(get_settings().export_dir) / f"{job_id}.xlsx"


def _now_local() -> datetime:
    return datetime.now()


def _plan(session: Session, defn: ListDefinition, user_id: int, req: ExportRequest) -> Plan:
    b = list_service._builder(session, defn)
    version = data_versions.read_current(session)
    unknown = [f for f in req.fields if f not in b.columns]
    if unknown:
        raise ListQueryError([{"field": "fields", "problem": f"Bilinmeyen alan: {', '.join(unknown)}"}])
    fields = list(dict.fromkeys(req.fields))
    if req.scope.columns == "all":
        fields += [f for f in b.columns if f not in fields]
    filters = req.filters if req.scope.rows == "filtered" else []
    group_by = req.group_by
    specs = b.aggregate_specs(fields, req.aggregates) if group_by else {}
    b.where(filters)  # doğrulama (422)
    rows = list_repo.fetch_count(session, b.filtered_query(filters) if filters else b.total_query())
    stamp = _now_local().strftime("%Y-%m-%d_%H%M")
    file_name = f"smartchain_{defn.file_slug or defn.name}_veri-v{version['Id']}_{stamp}.xlsx"
    labels = {f: c["label"] for f, c in b.columns.items()}
    columns = [b.columns[f] for f in fields]

    info = [
        ("Liste", defn.title or defn.name),
        ("Kaynak", f"Veri versiyonu v{version['Id']} · {version['LocationCode']} · "
                   f"{version['CreatedAt'].replace(tzinfo=timezone.utc).astimezone():%d.%m.%Y %H:%M}"),
        ("Satırlar", f"{'Filtrelenmiş' if req.scope.rows == 'filtered' else 'Tümü (filtresiz)'} · {describe.tr_number(rows, 0)}"),
        ("Kolonlar", f"{'Görünen' if req.scope.columns == 'visible' else 'Tümü'} · {len(columns)}: "
                     + ", ".join(c["label"] for c in columns)),
        ("Filtreler", "; ".join(describe.describe_filter(f.model_dump(by_alias=True, exclude_none=True), labels.get(f.field, f.field),
                                                         b.columns.get(f.field, {}).get("decimals"))
                                for f in filters) or "yok"),
        ("Sıralama", describe.describe_sort([s.model_dump() for s in req.sort], labels) or "liste varsayılanı"),
        ("Gruplama", " › ".join(labels.get(g, g) for g in group_by) or "yok"),
        ("Ara toplamlar", describe.describe_aggregates({f: s.model_dump(exclude_none=True) for f, s in specs.items()}, labels) or "yok"),
        ("Dışa aktaran", repo.user_name(session, user_id) or f"#{user_id}"),
        ("Zaman", f"{_now_local():%d.%m.%Y %H:%M}"),
        ("Smartchain", __version__),
        ("Not", "Dosya sisteme geri yüklenemez; yükleme şablonu ayrıdır."),
    ]
    return Plan(defn, b, columns, fields, filters, group_by, specs, rows, file_name, version, info)


def _norm(v):
    """Grup anahtarı karşılaştırması: metinde büyük/küçük harf duyarsız (grup sorgusuyla aynı), boş metin boş."""
    if v is None or v == "":
        return None
    return v.casefold() if isinstance(v, str) else list_service._json(v)


def write(session: Session, plan: Plan, req: ExportRequest, target, progress: Callable[[int], None] | None = None) -> int:
    """Dosyayı yazar; yazılan veri satırı sayısını döndürür."""
    b = plan.builder
    writer = XlsxWriter(target, plan.columns, req.widths)
    writer.header()
    units = list_repo.read_unit_decimals(session) if plan.defn.unit_field else {}

    nodes: dict[tuple, dict] = {}
    if plan.group_by:
        q, _ = b.groups_query(plan.group_by, plan.filters, req.sort, plan.specs, 10**7)
        tree = build_tree(list_repo.fetch_rows(session, q), len(plan.group_by), {f: s.fn for f, s in plan.specs.items()},
                          {f for f, s in plan.specs.items() if b.unit_relevant(f, s)}, list_service._json, units)

        def walk(items: list[dict]):
            for n in items:
                nodes[tuple(_norm(k) for k in n["key"])] = n
                walk(n.get("children", []))
        walk(tree["groups"])
    fns = {f: s.fn for f, s in plan.specs.items()}
    group_cols = {g: b.columns[g] for g in plan.group_by}

    query = b.export_query(plan.fields, req.sort, plan.filters, plan.group_by)
    result = session.execute(query.execution_options(stream_results=True, yield_per=PROGRESS_EVERY))
    try:
        written = _write_rows(result, plan, writer, nodes, fns, group_cols, units, progress)
    finally:
        result.close()  # hata ya da yarıda kesilme olsa da imleç kapanır, bağlantı serbest kalır (docs/08)
    writer.info_sheet(plan.info)  # her dosyada (K-91)
    writer.save()
    return written


def _write_rows(result, plan: Plan, writer: XlsxWriter, nodes: dict, fns: dict, group_cols: dict, units: dict,
                progress: Callable[[int], None] | None) -> int:
    current: tuple = ()
    written = 0
    for row in result.mappings():
        if plan.group_by:
            key = tuple(_norm(row[f"_g{i}"]) for i in range(len(plan.group_by)))
            same = 0
            while same < len(key) and same < len(current) and key[same] == current[same]:
                same += 1
            for depth in range(same, len(key)):
                node = nodes.get(key[: depth + 1], {"count": 0, "aggregates": {}, "unit_decimals": {}, "mixed_units": []})
                raw = row[f"_g{depth}"]
                col = group_cols[plan.group_by[depth]]
                label = "(Boş)" if raw is None or raw == "" else str(XlsxWriter.value(col, raw))
                if isinstance(XlsxWriter.value(col, raw), datetime):
                    label = f"{XlsxWriter.value(col, raw):%d.%m.%Y}"
                writer.group_row(label, depth, node["count"],
                                 {f: v for f, v in node["aggregates"].items() if f not in node.get("mixed_units", [])},
                                 fns, node.get("unit_decimals", {}), f"{describe.tr_number(node['count'], 0)} satır")
            current = key
        unit = units.get(row[UNIT]) if UNIT in row else None
        writer.data_row(row, unit, indent=len(plan.group_by))
        written += 1
        if progress and written % PROGRESS_EVERY == 0:
            progress(written)
    return written


def _details(plan: Plan, req: ExportRequest, rows: int, size: int, seconds: float, job_id: int | None) -> dict:
    return {"list": plan.defn.name, "title": plan.defn.title, "data_version": plan.version["Id"],
            "scope": req.scope.model_dump(), "columns": plan.fields, "filters": dict(plan.info).get("Filtreler"),
            "sort": [s.model_dump() for s in req.sort], "group_by": plan.group_by, "rows": rows, "size": size,
            "seconds": round(seconds, 2), "background": job_id is not None, "job_id": job_id}


def start(session: Session | None, defn: ListDefinition, user_id: int, req: ExportRequest) -> dict:
    """Anlık: {"file": bytes, "file_name"}; arka plan: {"job_id", "file_name", "rows"}."""
    if session is None:
        raise AppError("database_unavailable", DB_DOWN, 503)
    try:
        if not view_repo.user_exists(session, user_id):
            raise AppError("user_not_found", "Kullanıcı bulunamadı.", 404)
        settings = repo.read_settings(session)
        plan = _plan(session, defn, user_id, req)
        if plan.rows > settings["ExportMaxRows"]:
            raise AppError("export_too_large", f"{describe.tr_number(plan.rows, 0)} satır, bir aktarımın sınırı olan "
                                               f"{describe.tr_number(settings['ExportMaxRows'], 0)} satırı aşıyor; "
                                               "filtreyi daraltın.", 422)
        if plan.rows > settings["ExportSyncMaxRows"]:
            payload = {"list": defn.name, "user_id": user_id, "file_name": plan.file_name, "rows": plan.rows,
                       "request": req.model_dump(mode="json", by_alias=True)}
            job_id = queue.enqueue(session, TYPE_EXPORT, CHANNEL_EXPORT, user_id, payload)
            return {"job_id": job_id, "file_name": plan.file_name, "rows": plan.rows}
        t0 = time.perf_counter()
        buf = io.BytesIO()
        rows = write(session, plan, req, buf)
        data = buf.getvalue()
        try:  # iz yazılamazsa dosya verilmez (fonksiyon 86)
            repo.write_audit(session, user_id, defn.name, plan.file_name,
                             _details(plan, req, rows, len(data), time.perf_counter() - t0, None))
            session.commit()
        except DBAPIError as exc:
            session.rollback()
            raise AppError("export_trace_failed", "Dışa aktarım ize yazılamadı; dosya verilmedi.", 503) from exc
        return {"file": data, "file_name": plan.file_name}
    except ListQueryError as exc:
        raise AppError("validation", "Gönderilen veri geçersiz.", 422, exc.details) from exc
    except DBAPIError as exc:
        session.rollback()
        raise AppError("database_unavailable", DB_DOWN, 503) from exc


def run_job(session: Session, job_id: int, attempt: int, payload: dict, progress: Callable[[str], None]) -> dict:
    """Motor servisinin dışa aktarım işi (K-93): dosyayı EXPORT_DIR/<iş>.xlsx'e yazar, izi ve iş bitişini tek işlemde yazar."""
    defn = next(d for d in LISTS if d.name == payload["list"])
    req = ExportRequest.model_validate(payload["request"])
    plan = _plan(session, defn, payload["user_id"], req)
    plan.file_name = payload["file_name"]
    path = export_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    t0 = time.perf_counter()
    total = plan.rows

    def step(n: int):
        progress(f"{describe.tr_number(n, 0)} / {describe.tr_number(total, 0)} satır")

    try:
        rows = write(session, plan, req, str(tmp), step)
        tmp.replace(path)
        size = path.stat().st_size
        repo.write_audit(session, payload["user_id"], defn.name, plan.file_name,
                         _details(plan, req, rows, size, time.perf_counter() - t0, job_id))
        if not queue.finish(session, job_id, attempt, progress=f"Hazır · {_size_text(size)}", commit=False):
            session.rollback()
            path.unlink(missing_ok=True)
            return {}
        session.commit()
        return {"file_name": plan.file_name, "size": size, "rows": rows}
    except Exception:
        session.rollback()
        tmp.unlink(missing_ok=True)
        path.unlink(missing_ok=True)
        raise


def _size_text(size: int) -> str:
    return f"{describe.tr_number(size / 1024 / 1024, 1)} MB" if size >= 1024 * 1024 else f"{describe.tr_number(size / 1024, 0)} KB"


def download(session: Session | None, job_id: int, user_id: int) -> tuple[Path, str]:
    """Arka planda hazırlanan dosya: yalnız sahibine, iş bittiyse ve süresi geçmediyse."""
    if session is None:
        raise AppError("database_unavailable", DB_DOWN, 503)
    job = queue.get_job(session, job_id, JobSettings())
    if job is None or job["JobType"] != TYPE_EXPORT:
        raise AppError("export_not_found", "Dışa aktarım bulunamadı.", 404)
    if job["RequestedBy"] != user_id:
        raise AppError("export_not_owner", "Bu dosyayı yalnız aktarımı başlatan indirebilir.", 403)
    if job["Status"] != STATUS_DONE:
        raise AppError("export_not_ready", "Dosya henüz hazır değil.", 409)
    hours = repo.read_settings(session)["ExportFileHours"]
    path = export_path(job_id)
    ended = job["EndedAt"]
    if ended is None or ended + timedelta(hours=hours) < queue.db_now(session) or not path.exists():
        raise AppError("export_expired", f"Dosyanın indirme süresi ({hours} saat) geçti; aktarımı yeniden başlatın.", 410)
    return path, json.loads(job["Payload"] or "{}").get("file_name", path.name)
