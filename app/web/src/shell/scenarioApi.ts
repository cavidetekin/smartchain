// Senaryolar (K-177; docs/08 "Senaryolar"): seçili senaryo ve geçiş (herkes), yönetim işlemleri (Admin ve üstü), gece ayarı (Key user ve üstü).
import { getJson, sendJson } from "../api/client";
import type { ShellScenario } from "./ShellContext";

interface Raw { id: number; name: string; is_base: boolean; is_active: boolean }
export interface ScenarioOption { id: number; name: string; is_base: boolean }
export interface DeleteInfo { name: string; plan_versions: number; deletable: boolean; reason: string | null }

const shape = (r: Raw): ShellScenario => ({ id: r.id, name: r.name, isBase: r.is_base, isActive: r.is_active });

export const scenarioApi = {
  current: (signal?: AbortSignal) => getJson<Raw>("/api/scenarios/current", signal).then(shape),
  select: (id: number) => sendJson<Raw>("PUT", "/api/scenarios/current", { id }).then(shape),
  options: (signal?: AbortSignal) => getJson<{ scenarios: ScenarioOption[] }>("/api/scenarios/options", signal).then((r) => r.scenarios),
  create: (name: string, sourceId: number, followsBase: boolean) =>
    sendJson<Raw>("POST", "/api/scenarios", { name, source_id: sourceId, follows_base: followsBase }),
  rename: (id: number, name: string) => sendJson<Raw>("PUT", `/api/scenarios/${id}`, { name }),
  setActive: (id: number, active: boolean) => sendJson<Raw>("POST", `/api/scenarios/${id}/${active ? "activate" : "deactivate"}`),
  detach: (id: number) => sendJson<Raw>("POST", `/api/scenarios/${id}/detach`),
  deleteInfo: (id: number, signal?: AbortSignal) => getJson<DeleteInfo>(`/api/scenarios/${id}/delete-info`, signal),
  remove: (id: number) => sendJson<{ deleted: string; plan_versions: number }>("DELETE", `/api/scenarios/${id}`),
  saveNightly: (rows: { id: number; runs_nightly: boolean }[]) => sendJson<{ changed: number }>("PUT", "/api/scenarios/nightly", { rows }),
};
