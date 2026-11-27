"""Veri versiyonlarına bağlı plan verisinin silinmesi: plan hesapları ve çıktıları, senaryolar, çalışmalar.

Sentetik verinin yeniden yüklenmesi (K-79) ve testler kullanır. Çağıran işlemi (transaction) yönetir.
"""
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

# silme sırası: bağlanan önce (pegging → hareket ve yük → karşılama, tedarik planı → talep; K-202)
OUTPUT_TABLES = ["PlanWarning", "Pegging", "CapacityLoad", "MaterialTransaction", "PlannedAllocationTransfer", "PlannedOvertime", "DemandFulfillment",
                 "PlannedSupply", "PlannedDemand", "PlanMetric"]


def _ids(conn: Connection, sql: str, **lists) -> list[int]:
    if any(not v for v in lists.values()):
        lists = {k: v or [-1] for k, v in lists.items()}
    stmt = text(sql).bindparams(*(bindparam(k, expanding=True) for k in lists))
    return [r[0] for r in conn.execute(stmt, lists)]


def _exec(conn: Connection, sql: str, **lists) -> None:
    if all(not v for v in lists.values()):
        return
    lists = {k: v or [-1] for k, v in lists.items()}
    conn.execute(text(sql).bindparams(*(bindparam(k, expanding=True) for k in lists)), lists)


def delete_plan_data(conn: Connection, data_version_ids: list[int]) -> None:
    """Bu veri versiyonlarıyla açılmış senaryo sonucu, çalışma ve plan hesaplarını çıktılarıyla siler."""
    if not data_version_ids:
        return
    dv = list(data_version_ids)
    scenarios = _ids(conn, "SELECT Id FROM planning.Scenario WHERE DataVersionId IN :dv", dv=dv)
    workspaces = _ids(conn, "SELECT Id FROM planning.Workspace WHERE ScenarioId IN :sc", sc=scenarios)
    runs = _ids(conn, "SELECT Id FROM planning.PlanRun WHERE DataVersionId IN :dv OR ScenarioId IN :sc "
                      "OR WorkspaceId IN :ws", dv=dv, sc=scenarios, ws=workspaces)
    _delete(conn, scenarios, workspaces, runs)


def delete_scenario_plans(conn: Connection, scenario_definition_id: int) -> int:
    """Bir senaryonun plan versiyonlarını (plan hesapları, çıktıları, senaryo sonuçları, çalışmaları) siler (K-177). Silinen plan hesabı sayısı."""
    sd = [scenario_definition_id]
    scenarios = _ids(conn, "SELECT Id FROM planning.Scenario WHERE ScenarioDefinitionId IN :sd", sd=sd)
    workspaces = _ids(conn, "SELECT Id FROM planning.Workspace WHERE ScenarioId IN :sc", sc=scenarios)
    runs = _ids(conn, "SELECT Id FROM planning.PlanRun WHERE ScenarioDefinitionId IN :sd OR ScenarioId IN :sc "
                      "OR WorkspaceId IN :ws", sd=sd, sc=scenarios, ws=workspaces)
    _delete(conn, scenarios, workspaces, runs)
    return len(runs)


def delete_runs(conn: Connection, run_ids: list[int]) -> None:
    """Plan hesaplarını çıktıları ve gece sonuçlarıyla siler (plan fikstürü yeniden yüklenirken, K-205)."""
    if not run_ids:
        return
    scenarios = _ids(conn, "SELECT Id FROM planning.Scenario WHERE PlanRunId IN :r OR Id IN (SELECT ScenarioId FROM planning.PlanRun WHERE Id IN :r)", r=list(run_ids))
    workspaces = _ids(conn, "SELECT Id FROM planning.Workspace WHERE ScenarioId IN :sc", sc=scenarios)
    _delete(conn, scenarios, workspaces, list(run_ids))


def _delete(conn: Connection, scenarios: list[int], workspaces: list[int], runs: list[int]) -> None:
    for t in OUTPUT_TABLES:
        _exec(conn, f"DELETE FROM planning.{t} WHERE PlanRunId IN :r", r=runs)
    _exec(conn, "DELETE FROM adm.SolverLog WHERE PlanRunId IN :r", r=runs)
    _exec(conn, "DELETE FROM planning.PlanVersion WHERE PlanRunId IN :r OR WorkspaceId IN :ws", r=runs, ws=workspaces)
    # Workspace ↔ PlanRun ↔ Scenario döngüsel bağlar önce çözülür.
    _exec(conn, "UPDATE planning.Workspace SET CurrentPlanRunId = NULL WHERE Id IN :ws OR CurrentPlanRunId IN :r",
          ws=workspaces, r=runs)
    _exec(conn, "UPDATE planning.Scenario SET PlanRunId = NULL WHERE Id IN :sc OR PlanRunId IN :r",
          sc=scenarios, r=runs)
    _exec(conn, "DELETE FROM planning.WorkspaceOverride WHERE WorkspaceId IN :ws", ws=workspaces)
    _exec(conn, "DELETE FROM planning.PlanRun WHERE Id IN :r", r=runs)
    _exec(conn, "DELETE FROM planning.Workspace WHERE Id IN :ws", ws=workspaces)
    _exec(conn, "DELETE FROM planning.Scenario WHERE Id IN :sc", sc=scenarios)
