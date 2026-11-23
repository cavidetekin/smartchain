// Kapasite yönetimi (ekran 30, K-185, 7.9b): giriş tablolarının tanımı (liste, alanlar, seçenekler) ve yazma uçları.
// Okuma ortak liste uçlarından (`capacity-*`); yazma `/api/capacity/<giriş>` (docs/08 "Kapasite yönetimi").
import type { ComponentType } from "react";

import { sendJson } from "../api/client";
import { tr } from "../i18n/tr";
import type { Row } from "../table/types";

const T = tr.capacity;

export type EntryKind = "work-patterns" | "efficiency" | "overtime-limits" | "downtime" | "factory-calendar";
export type FieldKind = "date" | "number" | "day" | "choice" | "text";
export interface EntryField { name: string; label: string; kind: FieldKind; required?: boolean; decimals?: number; options?: readonly string[] }
export interface EntrySpec {
  kind: EntryKind | "supplier-limits" | "material-holds"; list: string; table: string; title: string; owner: boolean; start: string; fields: EntryField[];
  /** Kapasite yönetimi dışındaki giriş (K-191: tedarikçi limiti): uçlar, yetki, sahip ve pencere. Verilmezse kapasite girişinin davranışı. */
  adapter?: EntryAdapter;
}

/** Yazma uçları (senaryo istekle gider). */
export interface EntryApi {
  change(scenario: number, changes: { id: number; field: string; value: unknown }[]): Promise<Saved & { saved: number }>;
  remove(scenario: number, id: number): Promise<unknown>;
  invalidate(scenario: number, id: number): Promise<unknown>;
  validate(scenario: number, id: number): Promise<unknown>;
  restore(scenario: number, id: number): Promise<unknown>;
}
export interface EntryDialogProps {
  spec: EntrySpec; scenario: number;
  /** Düzenlenen satır; yoksa yeni kayıt. */
  row: Row | null;
  /** Yeni kayıtta dolu gelen sahip (karttan, satır menüsünden ya da zaman çubuğundan). */
  owner?: Owner | null;
  onClose(): void; onSaved(): void;
}
/** Giriş altyapısının sahipten bağımsız kullanımı (K-191): aynı tablo, menü, düzenleme ve pencere standardı; sahip ve uçlar burada tanımlanır. */
export interface EntryAdapter {
  api: EntryApi;
  /** Yazma yetkisinin fonksiyonu (kapasite girişlerinde 24). */
  writeFunction: number;
  /** Kaydın okunur adı (menü ve onay metinleri). shown: alanın tablodaki yazımı. */
  label(row: Row, shown: (field: string, row: Row) => string): string;
  /** Satırın sahibi: "Yeni kayıt" satır menüsünden açılınca dolu gelir. */
  ownerOf(row: Row): Owner | null;
  /** Alan bu satırda düzenlenir mi (aynı tabloda iki kayıt türü: türe uymayan hücre düzenlenmez). */
  canEdit?(field: string, row: Row): boolean;
  /** Kolon genişlikleri (rem). */
  hints?: Record<string, { width?: number; left?: boolean }>;
  Dialog: ComponentType<EntryDialogProps>;
}

/** Tablodaki gün yazımı (— : çalışılmıyor); pencerede üçüncü seçenek "Çalışılmıyor". */
export const DAY_OFF_CELL = "—";
export const DAY_CHOICES = ["Tam", "Yarım", "Çalışılmıyor"] as const;
export const DAY_VALUES = ["Çalışılmıyor", "Yarım gün"] as const;
export const DOWNTIME_TYPES = ["Planlı bakım", "Arıza", "Diğer"] as const;
export const DAYS = ["DayMon", "DayTue", "DayWed", "DayThu", "DayFri", "DaySat", "DaySun"] as const;
const DAY_LABELS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

const validity: EntryField[] = [{ name: "ValidFrom", label: T.start, kind: "date", required: true }, { name: "ValidTo", label: T.end, kind: "date" }];
const days: EntryField[] = DAYS.map((name, i) => ({ name, label: DAY_LABELS[i], kind: "day" as const, options: DAY_CHOICES }));

export const ENTRIES: Record<EntryKind, EntrySpec> = {
  "work-patterns": { kind: "work-patterns", list: "capacity-work-patterns", table: "WorkPattern", title: T.tabs.workPatterns, owner: true, start: "ValidFrom",
                     fields: [...validity, { name: "DailyCapacity", label: T.dailyCapacity, kind: "number", required: true, decimals: 2 }, ...days] },
  efficiency: { kind: "efficiency", list: "capacity-efficiency", table: "ResourceEfficiency", title: T.tabs.efficiency, owner: true, start: "ValidFrom",
                fields: [...validity, { name: "EfficiencyPct", label: T.efficiency, kind: "number", required: true, decimals: 2 }] },
  "overtime-limits": { kind: "overtime-limits", list: "capacity-overtime-limits", table: "OvertimeLimit", title: T.tabs.overtime, owner: true, start: "ValidFrom",
                       fields: [...validity, { name: "DailyLimit", label: T.dailyLimit, kind: "number", required: true, decimals: 2 }] },
  downtime: { kind: "downtime", list: "capacity-downtime", table: "ResourceDowntime", title: T.tabs.downtime, owner: true, start: "StartDate",
              fields: [{ name: "StartDate", label: T.start, kind: "date", required: true }, { name: "EndDate", label: T.end, kind: "date", required: true },
                       { name: "DowntimeType", label: T.downtimeType, kind: "choice", required: true, options: DOWNTIME_TYPES }, { name: "Reason", label: T.reason, kind: "text" }] },
  "factory-calendar": { kind: "factory-calendar", list: "capacity-factory-calendar", table: "FactoryCalendar", title: T.tabs.calendar, owner: false, start: "StartDate",
                        fields: [{ name: "StartDate", label: T.start, kind: "date", required: true }, { name: "EndDate", label: T.end, kind: "date" },
                                 { name: "Name", label: T.name, kind: "text", required: true }, { name: "DayValue", label: T.dayValue, kind: "choice", required: true, options: DAY_VALUES }] },
};

export const ORIGIN_ERP = "ERP";
export const ORIGIN_DIFF = "Senaryo farkı";
export const ORIGIN_OWN = "Senaryo";

/** Kayıt gruba mı kaynağa mı girilir; kartta "Yeni kayıt" bunu dolu getirir. Tedarikçi limitinde sahip tedarikçidir (lokasyonu ve varsa malzemesiyle);
 *  malzeme blokajında malzeme (lokasyonuyla). */
export interface Owner { level: "group" | "resource" | "supplier" | "material"; id: number; code: string; locationId?: number; materialId?: number | null }

const url = (kind: EntryKind, scenario: number, tail = "") => `/api/capacity/${kind}${tail}?scenario_id=${scenario}`;

export interface Saved { warnings?: string[] }
/** Kapasite girişinin uçları, girişe bağlanmış (ortak bileşenler `EntryApi` ile çalışır). */
export const boundCapacityApi = (kind: EntryKind): EntryApi => ({
  change: (scenario, changes) => capacityApi.change(kind, scenario, changes),
  remove: (scenario, id) => capacityApi.remove(kind, scenario, id),
  invalidate: (scenario, id) => capacityApi.invalidate(kind, scenario, id),
  validate: (scenario, id) => capacityApi.validate(kind, scenario, id),
  restore: (scenario, id) => capacityApi.restore(kind, scenario, id),
});

export const capacityApi = {
  create: (kind: EntryKind, scenario: number, values: Record<string, unknown>) => sendJson<Saved & { id: number }>("POST", url(kind, scenario), { values }),
  change: (kind: EntryKind, scenario: number, changes: { id: number; field: string; value: unknown }[]) =>
    sendJson<Saved & { saved: number }>("PUT", url(kind, scenario), { changes }),
  remove: (kind: EntryKind, scenario: number, id: number) => sendJson<unknown>("DELETE", url(kind, scenario, `/${id}`)),
  invalidate: (kind: EntryKind, scenario: number, id: number) => sendJson<unknown>("POST", url(kind, scenario, `/${id}/invalidate`)),
  validate: (kind: EntryKind, scenario: number, id: number) => sendJson<unknown>("POST", url(kind, scenario, `/${id}/validate`)),
  restore: (kind: EntryKind, scenario: number, id: number) => sendJson<unknown>("POST", url(kind, scenario, `/${id}/restore`)),
};

/** Farkı olan satırda Baz'daki değerin okunur yazımı (ipucu, K-176): gün ve çalışma sayıdan yazıya. */
export function baseText(field: EntryField, value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (field.kind === "day") return value === 1 ? "Tam" : value === 0.5 ? "Yarım" : "—";
  if (field.name === "DayValue") return value === 0 ? DAY_VALUES[0] : DAY_VALUES[1];
  return String(value);
}

export const isoDate = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export function parseIso(text: unknown): Date | null {
  if (typeof text !== "string" || text.length < 10) return null;
  const [y, m, d] = text.slice(0, 10).split("-").map(Number);
  return Number.isFinite(y) && Number.isFinite(m) && Number.isFinite(d) ? new Date(y, m - 1, d) : null;
}
