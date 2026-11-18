"""Excel'e aktarım (K-91, K-93; fonksiyon 86, docs/08 "Dışa aktarım").

Ekranda ne görünüyorsa o aktarılır: aynı liste sözleşmesi (K-87) ve grup ağacı (K-90). Satır sayısı ExportSyncMaxRows'u
aşmıyorsa dosya hemen döner; aşıyorsa "Excel" kanalında iş olarak kuyruğa girer (motor servisi üretir).
Her aktarım AuditLog'a yazılır; iz yazılamazsa dosya verilmez.
"""
import base64
import binascii
import io
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app import __version__
from app.jobs import queue
from app.jobs.constants import CHANNEL_EXCEL, STATUS_DONE, TYPE_EXPORT
from app.jobs.settings import JobSettings
from ..errors import DB_UNAVAILABLE, AppError
from ..export import describe
from ..export import formats
from ..export.formats import CellFormat
from ..export.writer import XlsxWriter, write_chart_workbook
from ..lists import LISTS, ListDefinition
from ..lists.groups import build_tree
from ..lists.query import UNIT, Builder, ListQueryError
from ..lists import chart as chart_query
from ..lists.request import ChartExportLogRequest, ChartExportRequest, ExportRequest
from ..repositories import data_versions, export as repo, lists as list_repo, views as view_repo
from ..settings import get_settings
from . import lists as list_service

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
    rules: list
    rows: int
    file_name: str
    version: dict | None
    info: list[tuple[str, str]] = field(default_factory=list)
    image: bytes | None = None  # "Grafiği ekle" (K-179)


def export_path(job_id: int) -> Path:
    return Path(get_settings().export_dir) / f"{job_id}.xlsx"


def _now_local() -> datetime:
    return datetime.now()


BUCKETS = {"day": "Gün", "week": "Hafta", "month": "Ay", "quarter": "Çeyrek", "year": "Yıl"}
KINDS = {"xy": "Çubuk ve çizgi", "pie": "Pasta", "donut": "Halka", "scatter": "Dağılım"}
FNS = {"sum": "Toplam", "avg": "Ortalama", "min": "En düşük", "max": "En yüksek", "count": "Say", "distinct": "Benzersiz say"}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
IMAGE_MAX_BYTES = 1_500_000


def decode_image(text: str | None) -> bytes | None:
    """Grafik görseli (PNG, base64; "data:" öneki olabilir): en çok 1,5 MB. Başka içerik kabul edilmez."""
    if not text:
        return None
    try:
        data = base64.b64decode(text.split(",", 1)[-1], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AppError("chart_image_invalid", "Grafik görseli okunamadı.", 422) from exc
    if not data.startswith(PNG_MAGIC):
        raise AppError("chart_image_invalid", "Grafik görseli okunamadı.", 422)
    if len(data) > IMAGE_MAX_BYTES:
        raise AppError("chart_image_too_large", "Grafik görseli en çok 1,5 MB olabilir.", 422)
    return data


def _source(version: dict | None) -> str:
    return (f"Veri versiyonu v{version['Id']} · {version['LocationCode']} · "
            f"{version['CreatedAt'].replace(tzinfo=timezone.utc).astimezone():%d.%m.%Y %H:%M}" if version else "Güncel kayıtlar")


def _file_name(defn: ListDefinition, version: dict | None, ext: str, part: str = "") -> str:
    version_part = f"veri-v{version['Id']}_" if version else ""
    return f"smartchain_{defn.file_slug or defn.name}_{part}{version_part}{_now_local():%Y-%m-%d_%H%M}.{ext}"


def _describe_selection(sel, labels: dict) -> str:
    """Bilgi sayfasındaki "Grafik seçimi" satırı (K-179): eksen, öğe sayısı ve inilen dönem."""
    axis = labels.get(sel.x.field, sel.x.field) + (f" ({BUCKETS[sel.x.bucket]})" if sel.x.bucket else "")
    parts = [f"{axis}: {len(sel.items)} öğe"] if sel.items else [axis]
    if sel.split and sel.items:
        parts.append(f"kırılım {labels.get(sel.split, sel.split)}")
    parts += [f"{BUCKETS[w.bucket]} {', '.join(f'{k:%d.%m.%Y}' for k in w.keys)}" for w in sel.within]
    return " · ".join(parts)


def _plan(session: Session, defn: ListDefinition, user_id: int, req: ExportRequest) -> Plan:
    # Rol kayıttan: arka plan işinde de işi başlatanın görebildiği satırlar (row_scope, K-101).
    b = list_service._builder(session, defn, repo.user_role(session, user_id), user_id, req)
    version = data_versions.read_current(session) if defn.versioned else None
    unknown = [f for f in req.fields if f not in b.columns]
    if unknown:
        raise ListQueryError([{"field": "fields", "problem": f"Bilinmeyen alan: {', '.join(unknown)}"}])
    fields = list(dict.fromkeys(req.fields))
    if req.scope.columns == "all":
        fields += [f for f, c in b.columns.items() if f not in fields and not c.get("related")]  # ilişkili alan yalnız açıksa (K-182)
    filters = req.filters if req.scope.rows == "filtered" else []
    group_by = req.group_by
    specs = b.aggregate_specs(fields, req.aggregates) if group_by else {}
    rules = [r for r in req.rules if r.enabled and r.field in fields]  # pasifler ve aktarılmayan kolonlar yok (K-95)
    if req.scope.rows == "filtered":  # grafik seçimi de "ekrandaki filtrelerle" kapsamındadır (K-179)
        list_service.apply_selection(session, b, req.chart_selection, user_id)
    b.where(filters)  # doğrulama (422)
    b.rule_columns(rules)
    rows = list_repo.fetch_count(session, b.filtered_query(filters) if filters or b.selection is not None else b.total_query())
    image = decode_image(req.chart_image)  # 422: iş kuyruğa girmeden
    file_name = _file_name(defn, version, "xlsx")
    labels = {f: c["label"] for f, c in b.columns.items()}
    columns = [b.columns[f] for f in fields]

    info = [
        ("Liste", defn.title or defn.name),
        ("Kaynak", _source(version)),
        ("Satırlar", f"{'Filtrelenmiş' if req.scope.rows == 'filtered' else 'Tümü (filtresiz)'} · {describe.tr_number(rows, 0)}"),
        ("Kolonlar", f"{'Görünen' if req.scope.columns == 'visible' else 'Tümü'} · {len(columns)}: "
                     + ", ".join(c["label"] for c in columns)),
        ("Filtreler", "; ".join(describe.describe_filter(f.model_dump(by_alias=True, exclude_none=True), labels.get(f.field, f.field),
                                                         b.columns.get(f.field, {}).get("decimals"),
                                                         b.columns.get(f.field, {}).get("percent", False))
                                for f in filters) or "yok"),
        *([("Grafik seçimi", _describe_selection(req.chart_selection, labels))] if b.selection is not None else []),
        ("Sıralama", describe.describe_sort([s.model_dump() for s in req.sort], labels) or "liste varsayılanı"),
        ("Gruplama", " › ".join(labels.get(g, g) for g in group_by) or "yok"),
        ("Ara toplamlar", describe.describe_aggregates({f: s.model_dump(exclude_none=True) for f, s in specs.items()}, labels) or "yok"),
        ("Koşullu biçim", "; ".join(describe.describe_rule(r.model_dump(mode="json", by_alias=True, exclude_none=True),
                                                           labels.get(r.field, r.field), labels,
                                                           b.columns.get(r.field, {}).get("decimals"),
                                                           b.columns.get(r.field, {}).get("percent", False))
                                    for r in rules) or "yok"),
        ("Dışa aktaran", repo.user_name(session, user_id) or f"#{user_id}"),
        ("Zaman", f"{_now_local():%d.%m.%Y %H:%M}"),
        ("Smartchain", __version__),
        ("Not", "Dosya sisteme geri yüklenemez; yükleme şablonu ayrıdır."),
    ]
    return Plan(defn, b, columns, fields, filters, group_by, specs, rules, rows, file_name, version, info, image)


def rule_formatter(rules: list) -> Callable | None:
    """Excel hücresine kural biçimi (K-95): satırın _r{i} değerlerinden o kolonun tutan kuralları; aynı özellikte
    üstteki kural kazanır (alttan üste birleştirilir, üstteki en son yazılır)."""
    by_field: dict[str, list[tuple[int, CellFormat]]] = {}
    for i, r in enumerate(rules):
        by_field.setdefault(r.field, []).append((i, formats.rule_format(r.format)))
    if not by_field:
        return None

    def cell_format(col: dict, row, _value) -> CellFormat | None:
        out = None
        for i, fmt in reversed(by_field.get(col["field"], [])):
            if row.get(f"_r{i}"):
                out = fmt if out is None else out.merged(fmt)
        return out
    return cell_format


def _norm(v):
    """Grup anahtarı karşılaştırması: metinde büyük/küçük harf duyarsız (grup sorgusuyla aynı), boş metin boş."""
    if v is None or v == "":
        return None
    return v.casefold() if isinstance(v, str) else list_service._json(v)


def write(session: Session, plan: Plan, req: ExportRequest, target, progress: Callable[[int], None] | None = None) -> int:
    """Dosyayı yazar; yazılan veri satırı sayısını döndürür."""
    b = plan.builder
    writer = XlsxWriter(target, plan.columns, req.widths, rule_formatter(plan.rules))
    writer.header()
    units = list_repo.read_unit_decimals(session) if plan.defn.unit_field or b.related_units else {}

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

    query = b.export_query(plan.fields, req.sort, plan.filters, plan.group_by, plan.rules)
    result = session.execute(query.execution_options(stream_results=True, yield_per=PROGRESS_EVERY))
    try:
        written = _write_rows(result, plan, writer, nodes, fns, group_cols, units, progress)
    finally:
        result.close()  # hata ya da yarıda kesilme olsa da imleç kapanır, bağlantı serbest kalır (docs/08)
    writer.info_sheet(plan.info)  # her dosyada (K-91)
    writer.image = plan.image     # "Grafiği ekle" (K-179): "Grafik" sayfası
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
        if plan.defn.value_format:  # ekranla aynı okunur biçim (K-108)
            row = {**row, **{f: fn(row[f]) for f, fn in plan.defn.value_format.items() if f in row}}
        if plan.defn.row_format:  # satıra bağlı okunur biçim (K-173)
            row = dict(row)
            plan.defn.row_format([row])
        related = plan.builder.related_units  # ilişkili miktar alanı hedef kaydın biriminin ondalığıyla (K-182)
        field_decimals = {f: units.get(row[u]) for f, u in related.items() if u in row} if related else None
        writer.data_row(row, unit, indent=len(plan.group_by), field_decimals=field_decimals)
        written += 1
        if progress and written % PROGRESS_EVERY == 0:
            progress(written)
    return written


def _details(plan: Plan, req: ExportRequest, rows: int, size: int, seconds: float, job_id: int | None) -> dict:
    return {"list": plan.defn.name, "title": plan.defn.title, "data_version": plan.version["Id"] if plan.version else None,
            "scope": req.scope.model_dump(), "columns": plan.fields, "filters": dict(plan.info).get("Filtreler"),
            "sort": [s.model_dump() for s in req.sort], "group_by": plan.group_by, "rows": rows, "size": size,
            "seconds": round(seconds, 2), "background": job_id is not None, "job_id": job_id, "chart_image": plan.image is not None}


def start(session: Session | None, defn: ListDefinition, user_id: int, req: ExportRequest) -> dict:
    """Anlık: {"file": bytes, "file_name"}; arka plan: {"job_id", "file_name", "rows"}."""
    if session is None:
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503)
    try:
        if not view_repo.user_exists(session, user_id):
            raise AppError("user_not_found", "Kullanıcı bulunamadı.", 404)
        settings = repo.read_settings(session)
        plan = _plan(session, defn, user_id, req)
        if plan.rows > settings["ExportMaxRows"]:
            raise AppError("export_too_large", f"En çok {describe.tr_number(settings['ExportMaxRows'], 0)} satır aktarılabilir; "
                                               f"bu seçimde {describe.tr_number(plan.rows, 0)} satır var.", 422)
        if plan.rows > settings["ExportSyncMaxRows"]:
            payload = {"list": defn.name, "user_id": user_id, "file_name": plan.file_name, "rows": plan.rows,
                       "request": req.model_dump(mode="json", by_alias=True)}
            job_id = queue.enqueue(session, TYPE_EXPORT, CHANNEL_EXCEL, user_id, payload,
                                   summary=f"{plan.defn.title} · {describe.tr_number(plan.rows, 0)} satır")
            return {"job_id": job_id, "file_name": plan.file_name, "rows": plan.rows}
        t0 = time.perf_counter()
        buf = io.BytesIO()
        rows = write(session, plan, req, buf)
        data = buf.getvalue()
        # iz yazılamazsa dosya verilmez (fonksiyon 86, K-108)
        repo.write_audit(session, user_id, defn.name, plan.file_name,
                         _details(plan, req, rows, len(data), time.perf_counter() - t0, None))
        session.commit()
        return {"file": data, "file_name": plan.file_name}
    except ListQueryError as exc:
        raise AppError("validation", "Girilen bilgiler geçersiz.", 422, exc.details) from exc
    except DBAPIError as exc:
        session.rollback()
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503) from exc


# --- Grafiğin dışa aktarımı (K-179) -------------------------------------------------------------------------------

def _key_text(v: dict):
    """Eksen, kırılım ya da küçük grafik değeri: "Diğer", "(Boş)", Evet / Hayır ya da değerin kendisi."""
    if v["key"] == chart_query.OTHER and not isinstance(v["key"], bool):
        return "Diğer"
    if v["key"] is None:
        return "(Boş)"
    return v["label"] if v["label"] is not None else v["key"]


def _chart_table(b: Builder, req: ChartExportRequest, data: dict, labels: dict) -> tuple[list[str], list[list], list[str | None], list[str]]:
    """Toplanmış veri: satırlar yatay eksen (küçük grafik varsa başta onun kolonu), kolonlar seriler ve parçalar. Birimi karışık seri yazılmaz."""
    c = req.chart
    is_date = data["x"]["kind"] == "date"
    header = [labels.get(c.x.field, c.x.field) + (f" ({BUCKETS[c.x.bucket]})" if c.x.bucket else "")]
    number_formats: list[str | None] = [None]
    splits = data["split"]["values"] if data["split"] else [None]
    facets = data["facets"]["values"] if data.get("facets") else [None]
    cols, skipped = [], []
    for s, got in zip(c.series, data["series"]):
        name = FNS["count"] if s.fn == "count" else f"{labels.get(s.field, s.field)} · {FNS[s.fn]}"
        if got["mixed_units"] or got["data"] is None:
            skipped.append(name)
            continue
        decimals = 0 if s.fn in ("count", "distinct") else (b.columns[s.field].get("decimals") or 2) + (1 if s.fn == "avg" else 0)
        if s.fn not in ("count", "distinct") and b.columns[s.field]["type"] == "integer":
            decimals = 1 if s.fn == "avg" else 0
        for pi, p in enumerate(splits):
            cols.append((got["data"], pi))
            header.append(name if p is None else f"{_key_text(p)} · {name}" if len(c.series) > 1 else str(_key_text(p)))
            number_formats.append(formats.number_format(decimals))
    if facets != [None]:
        header.insert(0, labels.get(c.facet, c.facet))
        number_formats.insert(0, None)
    rows = []
    for fi, f in enumerate(facets):
        for xi, x in enumerate(data["x"]["values"]):
            key = x["key"]
            first = date.fromisoformat(key[:10]) if is_date and isinstance(key, str) and key != chart_query.OTHER else _key_text(x)
            row = [first if isinstance(first, (date, str)) else str(first)]
            for grid, pi in cols:
                row.append((grid[fi] if f is not None else grid)[pi][xi])
            rows.append(([str(_key_text(f))] if f is not None else []) + row)
    return header, rows, number_formats, skipped


def _points_table(b: Builder, req: ChartExportRequest, data: dict, labels: dict) -> tuple[list[str], list[list], list[str | None]]:
    """Dağılımın gösterilen noktaları: kayıt adı, iki değer ve (varsa) renk değeri."""
    p = req.points
    name = data.get("label_field")
    header = [labels.get(name, "Kayıt") if name else "Kayıt", labels.get(p.x, p.x), labels.get(p.y, p.y)] + ([labels.get(p.color, p.color)] if p.color else [])
    colors = [str(_key_text(v)) for v in data["colors"]["values"]] if data["colors"] else []
    rows = [[r[3], r[0], r[1]] + ([colors[r[2]] if r[2] < len(colors) else "Diğer"] if p.color else []) for r in data["points"]]
    dec = lambda f: formats.number_format(0 if b.columns[f]["type"] == "integer" else b.columns[f].get("decimals") or 2)  # noqa: E731
    return header, rows, [None, dec(p.x), dec(p.y)] + ([None] if p.color else [])


def _chart_context(session: Session, defn: ListDefinition, user_id: int, req=None):
    if not view_repo.user_exists(session, user_id):
        raise AppError("user_not_found", "Kullanıcı bulunamadı.", 404)
    role = repo.user_role(session, user_id)
    b = list_service._builder(session, defn, role, user_id, req)
    version = data_versions.read_current(session) if defn.versioned else None
    return role, b, version


def start_chart(session: Session | None, defn: ListDefinition, user_id: int, req: ChartExportRequest) -> dict:
    """Grafiğin verisi Excel'e (K-179): {"file": bytes, "file_name"}. Toplanmış veri küçüktür; hep anlık. İz yazılamazsa dosya verilmez."""
    if session is None:
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503)
    scatter = req.kind == "scatter"
    if (req.points if scatter else req.chart) is None:
        raise AppError("validation", "Girilen bilgiler geçersiz.", 422, [{"field": "points" if scatter else "chart", "problem": "Grafik isteği verilmeli"}])
    try:
        role, b, version = _chart_context(session, defn, user_id, req)
        image = decode_image(req.image)
        labels = {f: c["label"] for f, c in b.columns.items()}
        t0 = time.perf_counter()
        skipped: list[str] = []
        if scatter:
            data = list_service.points(session, defn, req.points, role, user_id)
            header, rows, number_formats = _points_table(b, req, data, labels)
            filters = req.points.filters
            what = [("Yatay eksen", labels.get(req.points.x, req.points.x)), ("Dikey eksen", labels.get(req.points.y, req.points.y)),
                    ("Renk kırılımı", labels.get(req.points.color, req.points.color) if req.points.color else "yok"),
                    ("Noktalar", f"{describe.tr_number(data['rows'], 0)} kayıttan {describe.tr_number(data['shown'], 0)} nokta")]
        else:
            c = req.chart
            data = list_service.chart(session, defn, c, role, user_id)
            header, rows, number_formats, skipped = _chart_table(b, req, data, labels)
            filters = c.filters
            what = [("Yatay eksen", header[1 if c.facet else 0]), ("Kırılım", labels.get(c.split, c.split) if c.split else "yok"),
                    ("Küçük grafikler", labels.get(c.facet, c.facet) if c.facet else "yok"),
                    ("Seriler", ", ".join(FNS["count"] if s.fn == "count" else f"{labels.get(s.field, s.field)} · {FNS[s.fn]}" for s in c.series)),
                    *([("Çizilmeyen seriler", ", ".join(skipped) + " (birimler karışık)")] if skipped else []),
                    ("Satırlar", describe.tr_number(data["rows"], 0))]
        info = [
            ("Liste", defn.title or defn.name),
            ("Kaynak", _source(version)),
            ("Grafik", KINDS[req.kind] + (f" · {req.title}" if req.title else "")),
            *what,
            ("Filtreler", "; ".join(describe.describe_filter(f.model_dump(by_alias=True, exclude_none=True), labels.get(f.field, f.field),
                                                             b.columns.get(f.field, {}).get("decimals"),
                                                             b.columns.get(f.field, {}).get("percent", False))
                                    for f in filters) or "yok"),
            ("Dışa aktaran", repo.user_name(session, user_id) or f"#{user_id}"),
            ("Zaman", f"{_now_local():%d.%m.%Y %H:%M}"),
            ("Smartchain", __version__),
            ("Not", "Dosya sisteme geri yüklenemez; yükleme şablonu ayrıdır."),
        ]
        file_name = _file_name(defn, version, "xlsx", "grafik_")
        buf = io.BytesIO()
        written = write_chart_workbook(buf, header, rows, number_formats, info, image)
        content = buf.getvalue()
        repo.write_audit(session, user_id, defn.name, file_name, {
            "list": defn.name, "title": defn.title, "data_version": version["Id"] if version else None, "chart": KINDS[req.kind], "format": "xlsx",
            "filters": dict(info)["Filtreler"], "rows": written, "size": len(content), "seconds": round(time.perf_counter() - t0, 2),
            "background": False, "job_id": None, "chart_image": image is not None})
        session.commit()
        return {"file": content, "file_name": file_name}
    except ListQueryError as exc:
        raise AppError("validation", "Girilen bilgiler geçersiz.", 422, exc.details) from exc
    except DBAPIError as exc:
        session.rollback()
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503) from exc


def log_chart_image(session: Session | None, defn: ListDefinition, user_id: int, req: ChartExportLogRequest) -> dict:
    """Görsel (PNG) tarayıcıda üretilir; burada yalnız iz yazılır ve dosya adı verilir (K-179). İz yazılamazsa ad dönmez, dosya inmez."""
    if session is None:
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503)
    try:
        _, _, version = _chart_context(session, defn, user_id)
        file_name = _file_name(defn, version, "png", "grafik_")
        repo.write_audit(session, user_id, defn.name, file_name, {
            "list": defn.name, "title": defn.title, "data_version": version["Id"] if version else None, "chart": KINDS[req.kind], "format": "png",
            "background": False, "job_id": None})
        session.commit()
        return {"file_name": file_name}
    except DBAPIError as exc:
        session.rollback()
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503) from exc


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
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503)
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
        raise AppError("export_expired", f"Dosyanın indirme süresi ({hours} saat) doldu.", 410)
    return path, json.loads(job["Payload"] or "{}").get("file_name", path.name)
