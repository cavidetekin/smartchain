"""Senaryolar listesi (ekran 07, fonksiyon 27; K-177), liste sözleşmesiyle. Sürümsüz.

Kolonlar: Gece sırası, Senaryo, Model, Baz'ı izler, Gece çalışsın, Süre bütçesi (sn), Son çalışma, Aktif. Model senaryonun `ModelType`
parametresidir (yoksa LP); süre bütçesi aktif hedeflerin sürelerinin toplamı; son çalışma senaryonun son plan hesabı (plan versiyonu). Varsayılan
sıralama: gece çalışanlar gece sırasıyla, sonra ötekiler ada göre.
"""
import sqlalchemy as sa

from db.models import metadata

from .definition import ListDefinition

S = metadata.tables["param.ScenarioDefinition"]
SETTING = metadata.tables["param.PlanningSetting"]
OBJECTIVE = metadata.tables["param.ObjectiveDefinition"]
RUN = metadata.tables["planning.PlanRun"]
YES, NO = "Evet", "Hayır"


def _yes_no(col) -> sa.ColumnElement:
    return sa.case((col == sa.true(), sa.literal(YES, sa.Unicode(5))), (col == sa.false(), sa.literal(NO, sa.Unicode(5))), else_=sa.null())


_model = sa.select(SETTING.c.Value).where(SETTING.c.ScenarioDefinitionId == S.c.Id, SETTING.c.SettingKey == "ModelType").scalar_subquery()
_budget = (sa.select(sa.func.sum(OBJECTIVE.c.TimeBudgetSeconds))
           .where(OBJECTIVE.c.ScenarioDefinitionId == S.c.Id, OBJECTIVE.c.IsActive == sa.true()).scalar_subquery())
# Son plan hesabı: iki ayrı tek seviyeli alt sorgu (iç içe yazılınca senaryo bağı kopuyor, her senaryoya en son plan hesabı geliyordu)
def _last(col) -> sa.ScalarSelect:
    return sa.select(col).where(RUN.c.ScenarioDefinitionId == S.c.Id).order_by(RUN.c.Id.desc()).limit(1).scalar_subquery()


_last_at = _last(sa.func.coalesce(RUN.c.EndedAt, RUN.c.StartedAt))
_last_status = _last(RUN.c.Status)
_active = sa.func.coalesce(S.c.IsActive, sa.true())

_source = sa.select(
    S.c.Id, S.c.Name, S.c.NightlyPriority,
    sa.cast(sa.func.coalesce(S.c.IsBase, sa.false()), sa.Boolean).label("IsBase"),
    sa.func.coalesce(_model, sa.literal("LP", sa.Unicode(5))).label("ModelType"),
    sa.case((S.c.IsBase == sa.true(), sa.null()), else_=_yes_no(sa.func.coalesce(S.c.FollowsBase, sa.false()))).label("FollowsBase"),
    sa.cast(sa.func.coalesce(S.c.RunsNightly, sa.false()), sa.Boolean).label("RunsNightly"),
    sa.cast(_budget, sa.Integer).label("BudgetSeconds"),
    _last_at.label("LastRunAt"), _last_status.label("LastRunStatus"),
    _yes_no(_active).label("ActiveLabel"),
    sa.cast(_active, sa.Boolean).label("IsActive"),
    # gece çalışanlar sırasıyla önce, sonra ötekiler
    sa.case((S.c.RunsNightly == sa.true(), sa.func.coalesce(S.c.NightlyPriority, 100000)), else_=1000000).label("NightOrder"),
).subquery("scenarios")

SCENARIOS = ListDefinition(
    name="scenarios", table="param.ScenarioDefinition", title="Senaryolar", file_slug="senaryolar", function=27, versioned=False,
    source=_source,
    fields=("NightlyPriority", "Name", "ModelType", "FollowsBase", "RunsNightly", "BudgetSeconds", "LastRunAt", "ActiveLabel", "NightOrder"),
    default_visible=("NightlyPriority", "Name", "ModelType", "FollowsBase", "RunsNightly", "BudgetSeconds", "LastRunAt", "ActiveLabel"),
    default_sort=(("NightOrder", "asc"), ("Name", "asc")),
    labels={"NightlyPriority": "Gece sırası", "Name": "Senaryo", "ModelType": "Model", "FollowsBase": "Baz'ı izler", "RunsNightly": "Gece çalışsın",
            "BudgetSeconds": "Süre bütçesi (sn)", "LastRunAt": "Son çalışma", "ActiveLabel": "Aktif", "NightOrder": "Liste sırası"},
    values={"ModelType": ["LP", "MILP"], "FollowsBase": [YES, NO], "ActiveLabel": [YES, NO]},
    key_fields=("Name", "IsBase", "IsActive", "RunsNightly", "FollowsBase", "NightlyPriority", "LastRunStatus"),
)
