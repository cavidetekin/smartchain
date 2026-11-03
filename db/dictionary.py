"""Veri sözlüğünün kurulumu (K-104): core ve param alanları adm.FieldDefinition'a, docs/02'den üretilen modelden.

Geçiş çalıştırır (0013), bu yüzden uygulamayı import etmez; model parametre gelir. Var olan satırda yalnız docs'tan gelen
StandardLabel ve Description güncellenir: System owner'ın değerleri ezilmez. Kaynağı "Sistem" olan kolonlar (Id, sürüm kolonları) sözlüğe girmez.
"""
import re

import sqlalchemy as sa

SYSTEM_SOURCE = "Sistem"
ADDITIONAL = re.compile(r"Additional(Text|Number)(\d+)$")
ADDITIONAL_TITLE = {"Text": "Ek metin alanı", "Number": "Ek sayı alanı"}
DOCS_COLUMNS = ("StandardLabel", "Description")
LABEL_LENGTH = 100
DESCRIPTION_LENGTH = 200
DECISION_NUMBER = re.compile(r"\s*\(K-\d+\)")


def is_additional(field: str) -> bool:
    return ADDITIONAL.match(field) is not None


def standard_label(column_name: str, label: str | None) -> str:
    """docs'tan gelen etiket; ek alanda "Ek metin alanı 1", etiketi olmayan alanda alanın adı."""
    found = ADDITIONAL.match(column_name)
    if found:
        return f"{ADDITIONAL_TITLE[found.group(1)]} {found.group(2)}"
    return (label or column_name)[:LABEL_LENGTH]


def description(column_name: str, comment: str | None) -> str | None:
    """docs/02 AÇIKLAMA: karar numarası ekranda görünmez; ek alanda ';' sonrası teknik not alınmaz."""
    text = DECISION_NUMBER.sub("", comment or "")
    if is_additional(column_name):
        text = text.split(";", 1)[0]
    return text.strip()[:DESCRIPTION_LENGTH] or None


def fields(metadata: sa.MetaData) -> list[dict]:
    """Sözlüğe girecek alanlar, docs'taki varsayılanlarıyla."""
    out = []
    for table in metadata.tables.values():
        field_class = table.info.get("field_class")
        if table.schema not in ("core", "param") or not field_class:
            continue
        for col in table.columns:
            if col.info.get("source", SYSTEM_SOURCE) == SYSTEM_SOURCE:
                continue
            out.append({
                "TableName": table.name, "FieldName": col.name, "FieldClass": field_class,
                "EditableInWorkspace": bool(col.info.get("workspace")), "ValuePriority": "ERP ezer", "ManualOverrides": True,
                "DefaultValue": col.info.get("default") or None, "IsRequired": not col.nullable,
                "StandardLabel": standard_label(col.name, col.info.get("label")),
                "Description": description(col.name, col.comment),
            })
    return out


def sync(conn: sa.Connection, metadata: sa.MetaData) -> dict[str, int]:
    """Eksik alanları ekler, var olanların docs'tan gelen kolonlarını günceller. Tekrar çalıştırmak güvenlidir.

    Geçişler modelin son hâliyle çalışır: temiz kurulumda eski geçiş sırasında kolonu henüz açılmamış alan atlanır.
    """
    fd = metadata.tables["adm.FieldDefinition"]
    present = {c["name"] for c in sa.inspect(conn).get_columns(fd.name, schema=fd.schema)}
    tracked = [name for name in DOCS_COLUMNS if name in present]
    known = {(r.TableName, r.FieldName): r for r in conn.execute(sa.select(fd.c.TableName, fd.c.FieldName, *[fd.c[n] for n in tracked]))}
    added = updated = 0
    for row in fields(metadata):
        key = (row["TableName"], row["FieldName"])
        if key not in known:
            conn.execute(sa.insert(fd).values({k: v for k, v in row.items() if k in present}))
            added += 1
        elif any(getattr(known[key], n) != row[n] for n in tracked):
            conn.execute(sa.update(fd).where(fd.c.TableName == key[0], fd.c.FieldName == key[1])
                         .values({n: row[n] for n in tracked}))
            updated += 1
    return {"added": added, "updated": updated}
