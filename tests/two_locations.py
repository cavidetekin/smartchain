"""İkinci lokasyon kurulumu (K-194; yalnız Smartchain_test): testler ve görsel kontrol çok lokasyonlu durumu bununla kurar. Sentetik sete dokunmaz:
yalnız yeni satırlar ekler (ikinci lokasyon; birinci lokasyondakiyle aynı kodlu kaynak grubu ve kaynak, üyelikleri; istenirse aynı kodlu malzeme,
tedarikçi ve malzeme tedarikçisi) ve `destroy` ile hepsini siler."""
import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine

from db.models import metadata

CODE = "PYT-LOC-2"
KEY = "pytest-loc2"


def _clone(conn: Connection, name: str, where: dict, **over) -> int:
    """Var olan satırın kopyası yeni kimlikle (güncel versiyonda geçerli). Dönen: yeni kimlik."""
    t = metadata.tables[f"core.{name}"]
    row = dict(conn.execute(sa.select(t).where(*[t.c[k] == v for k, v in where.items()])).mappings().first())
    values = {**row, **over}
    if "VersionTo" in values:
        values["VersionTo"] = None
    if "BusinessKey" in t.c:
        values["BusinessKey"] = f"{KEY}|{name}|{over.get('Code', '')}|{values.get('MaterialId', '')}|{values.get('ResourceId', '')}"[:200]
    if t.c.Id.autoincrement is True:
        values.pop("Id")
        return conn.execute(sa.insert(t).values(values).returning(t.c.Id)).scalar_one()
    values["Id"] = conn.execute(sa.select(sa.func.coalesce(sa.func.max(t.c.Id), 0) + 1)).scalar()
    conn.execute(sa.insert(t).values(values))
    return values["Id"]


def build(engine: Engine, group: str = "ISL3", resource: str = "M3-01", material: str | None = None, supplier: str | None = None) -> dict:
    """İkinci lokasyonu kurar. Dönen: {location, first (birinci lokasyon), group, resource, member, material?, supplier?, pair?, rows: [(tablo, kimlik)]}."""
    out: dict = {"rows": []}

    def add(name: str, where: dict, **over) -> int:
        new = _clone(conn, name, where, **over)
        out["rows"].append((name, new))
        return new

    with engine.begin() as conn:
        first = conn.execute(sa.text("SELECT TOP 1 l.Id FROM core.Location l JOIN core.ResourceGroup g ON g.LocationId = l.Id AND g.VersionTo IS NULL AND g.Code = :g ORDER BY l.Id"),
                             {"g": group}).scalar_one()
        current = {"VersionTo": None}
        out["first"] = first
        out["location"] = add("Location", {"Id": first}, Code=CODE, Name="Pytest ikinci fabrika")
        loc = out["location"]
        g = conn.execute(sa.text("SELECT Id FROM core.ResourceGroup WHERE Code = :c AND LocationId = :l AND VersionTo IS NULL"), {"c": group, "l": first}).scalar_one()
        r = conn.execute(sa.text("SELECT Id FROM core.Resource WHERE Code = :c AND LocationId = :l AND VersionTo IS NULL"), {"c": resource, "l": first}).scalar_one()
        out["first_group"], out["first_resource"] = g, r
        out["group"] = add("ResourceGroup", {"Id": g, **current}, LocationId=loc, Code=group)
        out["resource"] = add("Resource", {"Id": r, **current}, LocationId=loc, Code=resource)
        out["member"] = add("ResourceGroupMember", {"ResourceGroupId": g, "ResourceId": r, **current}, LocationId=loc, ResourceGroupId=out["group"], ResourceId=out["resource"])
        if material and supplier:
            m = conn.execute(sa.text("SELECT Id FROM core.Material WHERE Code = :c AND LocationId = :l AND VersionTo IS NULL"), {"c": material, "l": first}).scalar_one()
            s = conn.execute(sa.text("SELECT Id FROM core.Supplier WHERE Code = :c AND VersionTo IS NULL"), {"c": supplier}).scalar_one()
            out["material"] = add("Material", {"Id": m, **current}, LocationId=loc, Code=material)
            out["supplier"] = s
            out["pair"] = add("MaterialSupplier", {"MaterialId": m, "SupplierId": s, **current}, LocationId=loc, MaterialId=out["material"])
    return out


def destroy(engine: Engine, built: dict | None = None) -> None:
    """Kurulumu siler (kimlik verilmezse iş anahtarı ve lokasyon koduyla: yarıda kalmış kurulumu da temizler)."""
    with engine.begin() as conn:
        loc = conn.execute(sa.text("SELECT Id FROM core.Location WHERE Code = :c"), {"c": CODE}).scalar()
        if loc is None:
            return
        for name in ("FactoryCalendar", "SupplierLimit", "MaterialHold"):
            conn.execute(sa.text(f"DELETE FROM param.[{name}] WHERE LocationId = :l"), {"l": loc})
        resources = [r[0] for r in conn.execute(sa.text("SELECT Id FROM core.Resource WHERE LocationId = :l"), {"l": loc})]
        groups = [r[0] for r in conn.execute(sa.text("SELECT Id FROM core.ResourceGroup WHERE LocationId = :l"), {"l": loc})]
        for table in ("WorkPattern", "ResourceEfficiency", "OvertimeLimit", "ResourceDowntime"):
            for column, ids in (("ResourceId", resources), ("ResourceGroupId", groups)):
                for i in ids:
                    conn.execute(sa.text(f"DELETE FROM param.[{table}] WHERE [{column}] = :i"), {"i": i})
        for i in resources:
            conn.execute(sa.text("DELETE FROM cache.ResourceCapacityDay WHERE ResourceId = :i"), {"i": i})
        for name in ("MaterialSupplier", "ResourceGroupMember", "Material", "Resource", "ResourceGroup"):
            conn.execute(sa.text(f"DELETE FROM core.[{name}] WHERE LocationId = :l"), {"l": loc})
        conn.execute(sa.text("DELETE FROM core.Location WHERE Id = :l"), {"l": loc})
