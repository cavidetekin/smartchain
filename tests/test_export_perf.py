"""Excel'e anlık aktarım performans hedefi (K-91): eşikteki satır sayısı (ExportSyncMaxRows, 10.000) ortanca 3 sn altında.

Satırlar bir işlem içinde üretilir, ölçülür ve işlem geri alınır (iz satırları dahil); veritabanında iz kalmaz.
Ölçüm sunucu tarafının tamamıdır: sayım, sorgu, grup ağacı, xlsx yazımı ve iz.
"""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.lists import MATERIALS
from app.api.lists.request import ExportRequest, FilterItem, SortItem
from app.api.repositories.export import DEFAULTS
from app.api.services import export as service

from test_lists_perf import GENERATE, median_ms

pytestmark = [pytest.mark.db, pytest.mark.perf]

ROWS = DEFAULTS["ExportSyncMaxRows"]
TARGET_MS = 3000


@pytest.fixture
def big_session(db_engine, test_users):
    conn = db_engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    try:
        v, loc = conn.execute(text("SELECT TOP 1 Id, LocationId FROM adm.DataVersion ORDER BY Id DESC")).one()
        conn.execute(GENERATE, {"v": v, "loc": loc, "rows": ROWS})
        yield session, test_users[0]
    finally:
        session.close()
        trans.rollback()
        conn.close()


RULES = [  # 10 kural (K-95): Excel hücresine zemin, yazı rengi, kalın, ikon
    {"id": f"k{i}", "field": f, "condition": c, "format": fmt} for i, (f, c, fmt) in enumerate([
        ("Name", {"op": "contains", "value": "çelik"}, {"fill": "#f4cfc4"}),
        ("Name", {"op": "starts_with", "value": "rul"}, {"color": "#1e2257", "bold": True}),
        ("MaterialGroup", {"op": "in", "values": ["Çubuk", "Levha"]}, {"fill": "#dce0f7"}),
        ("MaterialLevel", {"op": "equals", "value": "hammadde"}, {"icon": "dot"}),
        ("SafetyStock", {"op": "between", "min": 100, "max": 300}, {"fill": "#fbe7b5", "icon": "arrow_up"}),
        ("SafetyStock", {"op": "gt", "value": 400}, {"bold": True}),
        ("SafetyStock", {"op": "lt", "field_ref": "MaxStock"}, {"icon": "warning"}),
        ("UpdatedAt", {"op": "relative", "value": "this_week"}, {"color": "#333a94"}),
        ("Code", {"op": "contains", "value": "99"}, {"icon": "star"}),
        ("BaseUom", {"op": "equals", "value": "adet"}, {"fill": "#eef0fb"}),
    ])]


@pytest.mark.parametrize("group_by, rules", [([], []), (["MaterialLevel", "MaterialGroup"], []), ([], RULES)],
                         ids=["düz", "gruplu", "10 kural"])
def test_sync_export_under_target(big_session, group_by, rules):
    session, user = big_session
    req = ExportRequest(fields=list(MATERIALS.default_visible), group_by=group_by, rules=rules,
                        filters=[FilterItem(field="Code", op="starts_with", value="PERF-")],
                        sort=[SortItem(field="MaterialGroup"), SortItem(field="SafetyStock", dir="desc")])
    out = service.start(session, MATERIALS, user, req)
    assert "file" in out and len(out["file"]) > 100_000  # eşikte hâlâ anlık
    ms = median_ms(lambda: service.start(session, MATERIALS, user, req))
    print(f"\nExcel'e anlık aktarım ({ROWS} satır, {'gruplu' if group_by else ('10 kural' if rules else 'düz')}): ortanca {ms:.0f} ms")
    assert ms < TARGET_MS
