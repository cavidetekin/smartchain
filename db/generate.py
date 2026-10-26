"""docs/02-veri-modeli.md ve docs/03-entegrasyon.md'den veritabanı modelini üretir.

Tek kaynak docs'tur (K-54). Bu betik:
  1. docs'taki tablo tanımlarını okur,
  2. db/models.py dosyasını (SQLAlchemy metadata) yazar,
  3. docs/07-veritabani.md tablo haritasını yazar.

Çalıştırma:  python db/generate.py            (models.py ve docs/07)
             python db/generate.py --initial  (ilk geçiş 0001; yalnız bir kez)
Ardından yeni geçiş:  alembic -c db/alembic.ini revision --autogenerate -m "..."
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

SCHEMA_OF_CLASS = {
    "Ana veri": "core",
    "İşlem verisi": "core",
    "Parametre": "param",
    "Plan": "planning",
    "Veri yönetimi": "adm",
    "Sistem": "adm",
}
SCHEMA_TITLE = {
    "stg": "Entegrasyon tabloları: ERP'nin dili, ilişkiler kodla (K-58)",
    "core": "Ana veri ve işlem verisi",
    "param": "Planlama parametreleri ve senaryo tanımları",
    "planning": "Senaryo, çalışma ve plan çıktıları",
    "adm": "Veri yönetimi ve sistem (SQL Server'da `sys` ayrılmış olduğu için `adm`)",
}

# Versiyonlu tablolarda her kayıtta bulunan ortak alanlar (K-40)
VERSION_COLS = [
    ("VersionFrom", "int", "Kaydın geçerli olduğu ilk veri versiyonu", True),
    ("VersionTo", "int", "Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş", False),
    ("ImportBatchId", "bigint", "Kaydı getiren yükleme partisi", False),
    ("BusinessKey", "nvarchar(200)", "İş anahtarı (kod ya da kodların birleşimi)", True),
    ("UpdatedAt", "datetime2", "Son değişiklik zamanı", True),
]
# Entegrasyon tablolarının standart alanları
STAGING_COLS = [
    ("StagingRowId", "bigint", "Satır kimliği", True),
    ("ImportBatchId", "bigint", "Yükleme partisi", True),
    ("RowStatus", "nvarchar(15)", "Yeni | Hatalı | Aktarıldı", True),
    ("ErrorText", "nvarchar(400)", "Hata açıklaması", False),
]

# Alan adı -> hedef tablo (ve kolon)
REF_TARGET = {
    "LocationId": "Location", "FromLocationId": "Location", "ToLocationId": "Location",
    "MaterialId": "Material", "ComponentMaterialId": "Material",
    "PlanRunId": "PlanRun", "CurrentPlanRunId": "PlanRun",
    "ResourceId": "Resource", "ParameterSetId": "ParameterSet", "ProjectId": "Project",
    "WorkOrderId": "WorkOrder", "ParentWorkOrderId": "WorkOrder", "SupplierId": "Supplier",
    "ResourceGroupId": "ResourceGroup", "WorkspaceId": "Workspace", "DataVersionId": "DataVersion",
    "CalendarId": "Calendar", "WorkerId": "Worker", "ScenarioId": "Scenario",
    "ImportBatchId": "ImportBatch", "DataRuleId": "DataRule", "CustomerId": "Customer",
    "CreatedBy": "AppUser", "RequestedBy": "AppUser", "PublishedBy": "AppUser",
    "OwnerUserId": "AppUser", "UserId": "AppUser", "CompetenceGroupId": "CompetenceGroup",
    "ShiftPlanId": "ShiftPlan", "ShiftId": "Shift", "ScenarioDefinitionId": "ScenarioDefinition",
    "SalesOrderLineId": "SalesOrderLine", "ProjectGroupId": "ProjectGroup",
    "ProductionVersionId": "ProductionVersion",
    "BaseUom": ("UnitOfMeasure", "Code"), "FromUom": ("UnitOfMeasure", "Code"),
    "ToUom": ("UnitOfMeasure", "Code"), "CapacityUnit": ("UnitOfMeasure", "Code"),
    "WarningCode": ("WarningDefinition", "Code"),
}

ADDITIONAL = re.compile(r"^Additional(Text|Number)1[–-](\d+)$")


def parse_rows(lines, start):
    """start: tablo başlık satırının indeksi. (kolonlar, satırlar, bitiş)."""
    split = lambda s: [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s.strip()[1:-1])]
    head = split(lines[start])
    rows, i = [], start + 2
    while i < len(lines) and lines[i].startswith("|"):
        cells = split(lines[i])
        rows.append(dict(zip(head, cells)))
        i += 1
    return head, rows, i


def read_tables(path: Path, field_header: str):
    lines = path.read_text(encoding="utf-8").splitlines()
    tables, i = [], 0
    while i < len(lines):
        if lines[i].startswith("### "):
            name = lines[i][4:].strip()
            meta, desc, j = None, [], i + 1
            while j < len(lines) and not lines[j].startswith("### ") and not lines[j].startswith("| ALAN"):
                t = lines[j].strip()
                if t.startswith("- ") and "· Faz" in t and "versiy" in t:
                    meta = t[2:]
                elif t.startswith("- "):
                    desc.append(t[2:])
                j += 1
            if j < len(lines) and lines[j].startswith("| ALAN") and field_header in lines[j]:
                head, rows, k = parse_rows(lines, j)
                tables.append(dict(name=name, meta=meta, desc=" ".join(desc), rows=rows))
                i = k
                continue
        i += 1
    return tables


def expand(rows, keymap):
    out = []
    for r in rows:
        name = r["ALAN"]
        if name.startswith("Ortak alanlar") or name.startswith("…"):
            continue
        m = ADDITIONAL.match(name)
        if m:
            for n in range(1, int(m.group(2)) + 1):
                rr = dict(r)
                rr["ALAN"] = f"Additional{m.group(1)}{n}"
                out.append(rr)
            continue
        out.append(r)
    return [
        dict(
            name=r["ALAN"], type=r["TIP"], key=r.get("ANAHTAR", ""), desc=r.get("AÇIKLAMA", ""),
            required=r.get(keymap["req"], "") == "E", default=r.get("VARSAYILAN", ""),
            source=r.get(keymap["src"], ""),
        )
        for r in out
    ]


def build_spec():
    core = read_tables(DOCS / "02-veri-modeli.md", "ANA KAYNAK")
    merged = {}
    for t in core:
        if t["name"].startswith("stg."):
            continue
        if t["name"] in merged:
            merged[t["name"]]["rows"] += t["rows"]
        else:
            merged[t["name"]] = t
    spec = []
    for t in merged.values():
        cls = t["meta"].split("·")[0].strip()
        spec.append(dict(
            name=t["name"], schema=SCHEMA_OF_CLASS[cls], cls=cls,
            versioned="versiyonlu" in t["meta"], desc=t["desc"],
            fields=expand(t["rows"], {"req": "ZOR.", "src": "ANA KAYNAK"}),
        ))
    stg = read_tables(DOCS / "03-entegrasyon.md", "YOKSA")
    smerged = {}
    for t in stg:
        if not t["name"].startswith("stg."):
            continue
        name = t["name"][len("stg."):]
        desc = t["desc"].split("  ·  ")[0]
        if name in smerged:
            smerged[name]["rows"] += t["rows"]
        else:
            smerged[name] = dict(name=name, desc=desc, rows=t["rows"])
    for t in smerged.values():
        spec.append(dict(
            name=t["name"], schema="stg", cls="Entegrasyon", versioned=False, desc=t["desc"],
            fields=expand(t["rows"], {"req": "ZOR.", "src": "KAYNAK"}),
        ))
    return spec


# ------------------------------------------------------------------ models.py

def sa_type(t: str) -> str:
    t = t.strip().lower()
    if t == "bigint": return "sa.BigInteger()"
    if t == "int": return "sa.Integer()"
    if t == "bit": return "sa.Boolean()"
    if t == "date": return "mssql.DATE()"
    if t == "time": return "mssql.TIME()"
    if t == "datetime2": return "mssql.DATETIME2()"
    if t == "nvarchar(max)": return "sa.UnicodeText()"
    if t == "varbinary(max)": return "sa.LargeBinary()"
    m = re.match(r"varbinary\((\d+)\)", t)
    if m: return f"mssql.VARBINARY({m.group(1)})"
    m = re.match(r"nvarchar\((\d+)\)", t)
    if m: return f"sa.Unicode({m.group(1)})"
    m = re.match(r"decimal\((\d+),(\d+)\)", t)
    if m: return f"sa.Numeric({m.group(1)}, {m.group(2)})"
    raise ValueError(f"bilinmeyen tip: {t}")


def default_sql(f) -> str | None:
    d = f["default"].strip()
    if not d:
        return None
    t = f["type"].lower()
    if t == "bit":
        return "1" if d in ("1", "E", "true") else "0"
    if t.startswith(("int", "bigint", "decimal")):
        return d.replace(",", ".") if re.match(r"^-?\d+([.,]\d+)?$", d) else None
    if t.startswith("nvarchar"):
        return "N'" + d.replace("'", "''") + "'"
    return None


def q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def render_models(spec) -> str:
    by_name = {(t["schema"], t["name"]): t for t in spec}
    core_names = {t["name"]: t for t in spec if t["schema"] != "stg"}
    out = [
        '"""Üretilmiş dosya: db/generate.py. Elle değiştirmeyin; önce docs, sonra generate (K-54)."""',
        "import sqlalchemy as sa",
        "from sqlalchemy.dialects import mssql",
        "",
        "metadata = sa.MetaData(naming_convention={",
        '    "pk": "PK_%(table_name)s",',
        '    "fk": "FK_%(table_name)s_%(column_0_name)s",',
        '    "uq": "UQ_%(table_name)s_%(column_0_name)s",',
        '    "ix": "IX_%(table_name)s_%(column_0_name)s",',
        '    "ck": "CK_%(table_name)s_%(constraint_name)s",',
        "})",
        "",
        "SCHEMAS = " + repr(list(SCHEMA_TITLE)),
        "",
    ]
    for t in spec:
        schema, name = t["schema"], t["name"]
        fields = list(t["fields"])
        cols, extra = [], []
        if schema == "stg":
            fields = [dict(name=n, type=ty, key="", desc=d, required=r, default="", source="Sistem")
                      for n, ty, d, r in STAGING_COLS] + [dict(f, required=False) for f in fields
                                                          if f["name"] not in ("ImportBatchId",)]
        elif t["versioned"]:
            have = {f["name"] for f in fields}
            fields += [dict(name=n, type=ty, key="", desc=d, required=r, default="", source="Sistem")
                       for n, ty, d, r in VERSION_COLS if n not in have]
        pk = [f["name"] for f in fields if "PK" in f["key"]]
        if schema == "stg":
            pk = ["StagingRowId"]
        if t["versioned"] and "VersionFrom" not in pk:
            pk = pk + ["VersionFrom"]
        uk = [f["name"] for f in fields if "UK" in f["key"]]
        for f in fields:
            args = [q(f["name"]), sa_type(f["type"])]
            kw = []
            target = REF_TARGET.get(f["name"]) if schema != "stg" else None
            if f["name"] == "ImportBatchId" and schema == "stg":
                target = "ImportBatch"
            if target and ("FK" in f["key"] or f["name"] in ("ImportBatchId",) or schema == "stg"):
                tname, tcol = (target, "Id") if isinstance(target, str) else target
                tt = core_names.get(tname)
                # Versiyonlu hedefe fiziksel FK yok: Id kayıt versiyonları boyunca sabittir,
                # tekil değildir; bütünlük aktarımda (kod→Id) sağlanır.
                if tt and not tt["versioned"] and not (tt["schema"] == schema == "stg"):
                    cyc = {"PlanRun", "Scenario", "Workspace"}
                    ua = ", use_alter=True" if name in cyc and tname in cyc else ""
                    args.append(f'sa.ForeignKey("{tt["schema"]}.{tname}.{tcol}"{ua})')
                elif tt:
                    kw.append("index=True")
            if f["name"] in pk:
                kw.append("primary_key=True")
                ident = (len(pk) == 1 and f["type"].lower() in ("int", "bigint") and not t["versioned"]
                         and f["name"] in ("Id", "StagingRowId"))
                kw.append(f"autoincrement={ident}")
            else:
                kw.append(f"nullable={not f['required']}")
            d = default_sql(f)
            if d is not None:
                kw.append(f"server_default=sa.text({q(d)})")
            if f["desc"]:
                kw.append(f"comment={q(f['desc'])}")
            cols.append(f"    sa.Column({', '.join(args + kw)}),")
        if uk:
            where = ', mssql_where=sa.text("VersionTo IS NULL")' if t["versioned"] else ""
            extra.append(f'    sa.Index("UX_{name}_{"_".join(uk)}", {", ".join(q(u) for u in uk)}, unique=True{where}),')
        out.append(f"{name if schema != 'stg' else 'stg_' + name} = sa.Table(")
        out.append(f"    {q(name)}, metadata,")
        out += cols + extra
        out.append(f"    schema={q(schema)},")
        if t["desc"]:
            out.append(f"    comment={q(t['desc'])},")
        out.append(")")
        out.append("")
    return "\n".join(out)


# ------------------------------------------------------------------ docs/07

def render_map(spec) -> str:
    L = [
        "# Veritabanı haritası",
        "",
        "Üretilmiş dosya: `db/generate.py`. Kaynak `docs/02-veri-modeli.md` ve `docs/03-entegrasyon.md`.",
        "",
        "## Kurallar",
        "",
        "- **Beş şema:** `stg` entegrasyon, `core` ana veri ve işlem verisi, `param` parametreler, `planning` plan çıktıları, `adm` veri yönetimi ve sistem.",
        "- **Aynı ad, iki katman:** `stg.Material` ERP'den geldiği haliyle (kodlarla), `core.Material` Smartchain'in tablosu (Id ile). Aktarım `stg`'den `core`'a yapılır (K-58).",
        "- **Versiyonlu tablolar:** `VersionFrom`, `VersionTo`, `ImportBatchId`, `BusinessKey`, `UpdatedAt` alanlarını taşır. Birincil anahtar `Id + VersionFrom`; `Id` bir kaydın bütün versiyonlarında aynıdır. Güncel kayıtta `VersionTo` boştur; tekillik (UK) yalnız güncel kayıtlarda aranır.",
        "- **İlişkiler:** Versiyonsuz tabloya giden ilişkiler veritabanında yabancı anahtarla (FK) korunur. Versiyonlu tabloya giden ilişkilerde FK yoktur, yalnız indeks vardır; bütünlüğü aktarım adımı (kod→Id) sağlar.",
        "- **Entegrasyon tablolarının standart alanları:** `StagingRowId`, `ImportBatchId`, `RowStatus` (Yeni, Hatalı, Aktarıldı), `ErrorText`. Bu tablolarda zorunluluk veritabanında değil, doğrulama adımında kontrol edilir.",
        "- **Açıklamalar:** Her tablo ve alanın Türkçe açıklaması veritabanına da yazılır; SQL Server Management Studio'da tablo ve kolon özelliklerinde görünür.",
        "",
    ]
    for s, title in SCHEMA_TITLE.items():
        ts = [t for t in spec if t["schema"] == s]
        L += [f"## `{s}` · {title} ({len(ts)} tablo)", "", "| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |", "|---|---|---|---|---|"]
        for t in ts:
            L.append(f"| `{s}.{t['name']}` | {t['desc'].replace('|', '/')} | {t['cls']} | {'evet' if t['versioned'] else ''} | {len(t['fields'])} |")
        L.append("")
    return "\n".join(L)


def write_initial_migration():
    """0001 geçişini metadata'dan yazar. Yalnız ilk kurulumda; sonraki geçişler autogenerate ile."""
    import importlib, sys
    from alembic.operations import ops
    from alembic.autogenerate import render_python_code
    sys.path.insert(0, str(ROOT / "db"))
    models = importlib.import_module("models")
    importlib.reload(models)
    tables = models.metadata.sorted_tables
    up = [ops.ExecuteSQLOp(f"CREATE SCHEMA [{s}]") for s in models.SCHEMAS]
    for t in tables:
        up.append(ops.CreateTableOp.from_table(t))
        up += [ops.CreateIndexOp.from_index(ix) for ix in sorted(t.indexes, key=lambda i: i.name)]
    alter = []
    for t in tables:
        for fk in t.foreign_key_constraints:
            if fk.use_alter:
                alter.append(ops.CreateForeignKeyOp.from_constraint(fk))
    up += alter
    down = [ops.DropConstraintOp(o.constraint_name, o.source_table, type_="foreignkey",
                                 schema=o.kw.get("source_schema")) for o in alter]
    down += [ops.DropTableOp.from_table(t) for t in reversed(tables)]
    down += [ops.ExecuteSQLOp(f"DROP SCHEMA [{s}]") for s in reversed(models.SCHEMAS)]
    body = (
        '"""0001 · İlk şema: stg, core, param, planning, adm (MDD 21 ve 26; K-58, K-59, K-61)\n\n'
        'Revision ID: 0001\nRevises:\nCreate Date: 2026-10-26\n"""\n'
        "from alembic import op\nimport sqlalchemy as sa\nfrom sqlalchemy.dialects import mssql\n\n"
        'revision = "0001"\ndown_revision = None\nbranch_labels = None\ndepends_on = None\n\n\n'
        f"def upgrade():\n{render_python_code(ops.UpgradeOps(ops=up))}\n\n\n"
        f"def downgrade():\n{render_python_code(ops.DowngradeOps(ops=down))}\n"
    )
    (ROOT / "db" / "migrations" / "versions" / "0001_ilk_sema.py").write_text(body, encoding="utf-8")


def main():
    spec = build_spec()
    (ROOT / "db" / "models.py").write_text(render_models(spec) + "\n", encoding="utf-8")
    (DOCS / "07-veritabani.md").write_text(render_map(spec) + "\n", encoding="utf-8")
    counts = {s: sum(1 for t in spec if t["schema"] == s) for s in SCHEMA_TITLE}
    print("tablolar:", counts, "toplam", len(spec))
    import sys
    if "--initial" in sys.argv:
        write_initial_migration()
        print("0001 geçişi yazıldı")


if __name__ == "__main__":
    main()
