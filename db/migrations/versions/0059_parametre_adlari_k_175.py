"""0059 · Parametre değerlerinin yeni adları (K-175, 7.1 demo bulguları): kayıtlı değerler taşınır

"Yumuşak hedef" → "Esnek hedef" (güvenlik stoğu), "Yalnız erteleme önerisi" → "Yalnız öteleme önerisi" (açık iş emirleri); fix periyot değer ve
birim olur: `FixPeriodDays` anahtarı `FixPeriod` olur, birim (`FixPeriodUnit`) yoksa Gün yazılır. Yalnız `param.PlanningSetting` satırları değişir;
şema değişmez. 0058'i yeni katalogla alan kurulumda yapacak iş kalmaz.

Revision ID: 0059
Revises: 0058
Create Date: 2026-11-16
"""
from alembic import op

revision = '0059'
down_revision = '0058'
branch_labels = None
depends_on = None

T = 'param.PlanningSetting'
VALUES = (("SafetyStockMode", "Yumuşak hedef", "Esnek hedef"), ("OpenWorkOrders", "Yalnız erteleme önerisi", "Yalnız öteleme önerisi"))


def _rename(key, old, new):
    op.execute(f"UPDATE {T} SET Value = N'{new}' WHERE SettingKey = N'{key}' AND Value = N'{old}'")


def upgrade():
    for key, old, new in VALUES:
        _rename(key, old, new)
    # fix periyot: gün sayısı değer olur, birimi Gün
    op.execute(f"DELETE o FROM {T} o WHERE o.SettingKey = N'FixPeriodDays' AND EXISTS (SELECT 1 FROM {T} n WHERE n.ScenarioDefinitionId = o.ScenarioDefinitionId "
               "AND n.SettingKey = N'FixPeriod')")
    op.execute(f"UPDATE {T} SET SettingKey = N'FixPeriod' WHERE SettingKey = N'FixPeriodDays'")
    op.execute(f"INSERT INTO {T} (ScenarioDefinitionId, SettingKey, Value) SELECT s.ScenarioDefinitionId, N'FixPeriodUnit', N'Gün' FROM {T} s "
               f"WHERE s.SettingKey = N'FixPeriod' AND NOT EXISTS (SELECT 1 FROM {T} u WHERE u.ScenarioDefinitionId = s.ScenarioDefinitionId "
               "AND u.SettingKey = N'FixPeriodUnit')")


def downgrade():
    op.execute(f"DELETE FROM {T} WHERE SettingKey = N'FixPeriodUnit'")
    op.execute(f"UPDATE {T} SET SettingKey = N'FixPeriodDays' WHERE SettingKey = N'FixPeriod'")
    for key, old, new in VALUES:
        _rename(key, new, old)
