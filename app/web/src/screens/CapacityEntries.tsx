// Kapasite yönetimi · giriş tablosu (K-185, 7.9b; docs/12 "Kapasite yönetimi"): üst sekmelerde ve kartlarda aynı bileşen. Şeritte "Yeni kayıt";
// hücreler tabloda düzenlenir (K-132: değişen hücre işaretli, Kaydet hepsini birlikte gönderir); satır menüsü Detay · Düzenle · Yeni kayıt · Sil
// (izleyen senaryoda Baz satırında Geçersiz yap ve Senaryo farkını kaldır). Senaryoda değişen hücre işaretlidir; ipucunda Baz'daki değer.
// Bileşen sahipten bağımsızdır (K-191): Model kısıtları › Tedarikçi limiti aynı bileşeni `spec.adapter` ile kullanır (uçlar, yetki, sahip, pencere).
import { type ReactNode, useCallback, useMemo, useState } from "react";

import { ApiError, emitNotice } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import type { CellEditing } from "../table/cellEditing";
import { type CellClass, type CellRender, type CellWrap, DataTable, type FieldHints, formatCell, type RowProps } from "../table/DataTable";
import { useRowMenu } from "../table/rowMenu";
import type { ListColumn, ListFilter, Row } from "../table/types";
import { EditBar, UnsavedGuard, useTableEdits } from "../table/useTableEdits";
import { Button, ConfirmDialog, Tooltip } from "../ui";
import type { MenuAction } from "../ui/PopMenu";
import { CapacityEntryDialog } from "./CapacityEntryDialog";
import { baseText, boundCapacityApi, DAY_CHOICES, DAY_OFF_CELL, type EntryKind, type EntrySpec, ORIGIN_DIFF, ORIGIN_ERP, type Owner } from "./capacityModel";

const T = tr.capacity;
const NO_ITEMS = () => [];
const lowerFirst = (s: string) => s.charAt(0).toLocaleLowerCase("tr") + s.slice(1);
// Kolon genişlikleri (rem): giriş tablosu ekrana sığsın (çalışma düzeninde yedi gün kolonu dar)
const DAY_HINT = { width: 4.9, left: true };
const HINTS: FieldHints = {
  Level: { width: 4.8 }, LocationCode: { width: 6.5 }, Code: { width: 6.5 }, ValidFrom: { width: 7.2 }, ValidTo: { width: 7.2 }, StartDate: { width: 7.2 }, EndDate: { width: 7.2 },
  DailyCapacity: { width: 10.4 }, DailyLimit: { width: 9 }, EfficiencyPct: { width: 9.5 }, CapacityUnit: { width: 4.2 }, Origin: { width: 7 }, IsValid: { width: 5 },
  DowntimeType: { width: 9 }, Reason: { width: 18 }, Name: { width: 18 }, DayValue: { width: 9 },
  DayMon: DAY_HINT, DayTue: DAY_HINT, DayWed: DAY_HINT, DayThu: DAY_HINT, DayFri: DAY_HINT, DaySat: DAY_HINT, DaySun: DAY_HINT,
};

/** Satırın sahibi (Yeni kayıt satır menüsünden açılınca dolu gelir). */
const ownerOf = (row: Row): Owner | null => (typeof row.ResourceId === "number" ? { level: "resource", id: row.ResourceId, code: String(row.Code ?? "") }
  : typeof row.ResourceGroupId === "number" ? { level: "group", id: row.ResourceGroupId, code: String(row.Code ?? "") } : null);

export function EntryTable({ spec, filters, owner, lead, end, compact, onDetail, selectedRowId, onChanged, onSelection, reloadKey = 0, focus }: {
  spec: EntrySpec;
  /** Kartta süzme: grubun kendisi ve üyeleri ya da yalnız kaynak. */
  filters?: ListFilter[];
  /** Karttan açılan "Yeni kayıt"ın seviyesi ve kodu. */
  owner?: Owner | null;
  /** Şeridin solunda (sekmeler) ve en sağında (kartta Büyüt ve ✕). */
  lead?: ReactNode; end?: ReactNode; compact?: boolean;
  /** Satır menüsünde "Detay" (kartı açar); kartın içindeki tabloda yok. */
  onDetail?(row: Row): void;
  selectedRowId?: number | null;
  /** Kayıt değişti (özet ve öteki tablolar yenilensin). */
  onChanged?(): void;
  /** Çoklu seçim değişti (K-171: kart seçili kayıtların hepsini gösterir). */
  onSelection?(ids: string[]): void;
  reloadKey?: number;
  /** "Kayda git" (K-188): bu kayıt seçili gösterilir ve görünür alana getirilir. */
  focus?: { id: number; n: number };
}) {
  const { scenario } = useShell();
  const { me } = useAuth();
  const adapter = spec.adapter;
  const write = Boolean(me && can(me, adapter?.writeFunction ?? 24, "write"));
  const api = useMemo(() => adapter?.api ?? boundCapacityApi(spec.kind as EntryKind), [adapter, spec.kind]);
  const DialogView = adapter?.Dialog ?? CapacityEntryDialog;
  const hints = useMemo(() => (adapter?.hints ? { ...HINTS, ...adapter.hints } : HINTS), [adapter]);
  const sid = scenario?.id ?? 0;
  const edits = useTableEdits();
  const [columns, setColumns] = useState<ListColumn[]>([]);
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [dialog, setDialog] = useState<{ row: Row | null; owner: Owner | null } | null>(null);
  const [removing, setRemoving] = useState<Row | null>(null);
  const [tick, setTick] = useState(0);
  const byField = useMemo(() => new Map(columns.map((c) => [c.field, c])), [columns]);
  const fields = useMemo(() => new Map(spec.fields.map((f) => [f.name, f])), [spec]);
  const key = (row: Row) => String(row.Id);
  const cellKey = (row: Row, field: string) => `${row.Id}|${field}`;
  const shown = useCallback((field: string, row: Row) => { const col = byField.get(field); return col ? formatCell(col, row[field], row) : String(row[field] ?? ""); }, [byField]);
  const editable = (row: Row) => write && row.Origin !== ORIGIN_ERP;
  const label = (row: Row) => (adapter ? adapter.label(row, shown)
    : spec.owner ? `${String(row.Level ?? "")} ${String(row.Code ?? "")} · ${shown(spec.start, row)}` : String(row.Name ?? ""));

  const changed = () => { setTick((n) => n + 1); onChanged?.(); };
  const run = async (work: () => Promise<unknown>) => {
    try {
      await work();
      changed();
    } catch (e) {
      emitNotice(e instanceof ApiError ? (e.details[0]?.problem ?? e.message) : T.failed);
    }
  };

  const editing: CellEditing = useMemo(() => ({
    editableColumn: (col) => write && fields.has(col.field),
    canEdit: (col, row) => fields.has(col.field) && editable(row) && (adapter?.canEdit?.(col.field, row) ?? true),
    editor: (col, row) => {
      const f = fields.get(col.field)!;
      const text = edits.get(key(row), col.field, shown(col.field, row));
      return { kind: f.options ? "select" : "text", text: f.kind === "day" && text === DAY_OFF_CELL ? DAY_CHOICES[2] : text, options: f.options };
    },
    // gün hücresinde liste "Çalışılmıyor" der, hücre "—" yazar
    commit: (col, row, text) => edits.set(key(row), col.field, fields.get(col.field)?.kind === "day" && text === DAY_CHOICES[2] ? DAY_OFF_CELL : text, shown(col.field, row)),
    label: (col, row) => `${label(row)} · ${col.label}`,
  }), [write, fields, edits, shown, adapter]);  // eslint-disable-line react-hooks/exhaustive-deps

  const cellRender: CellRender = useMemo(() => Object.fromEntries(spec.fields.map((f) => [f.name, (_v: unknown, row: Row) =>
    edits.get(key(row), f.name, shown(f.name, row))])), [spec, edits, shown]);  // eslint-disable-line react-hooks/exhaustive-deps

  /** Senaryoda değişen alan mı (K-176): fark satırının `OverriddenFields`'ı. */
  const overridden = (row: Row, field: string) => typeof row.OverriddenFields === "string" && row.OverriddenFields.includes(`,${field},`);
  const cellClass: CellClass = useCallback((field, row) => {
    const classes = [];
    if (edits.changed(key(row), field)) classes.push("is-draft");
    if (problems[cellKey(row, field)]) classes.push("is-invalid");
    if (overridden(row, field)) classes.push("sc-cell-diff");
    return classes.join(" ") || undefined;
  }, [edits, problems]);

  const cellWrap: CellWrap = useCallback((field, row, content) => {
    const problem = problems[cellKey(row, field)];
    let tip: string | null = problem ?? null;
    const f = fields.get(field);
    if (!tip && f && overridden(row, field) && typeof row.BaseValues === "string") {
      try {
        const base = (JSON.parse(row.BaseValues) as Record<string, unknown>)[field];
        const col = byField.get(field);
        const text = f.kind === "day" || f.name === "DayValue" ? baseText(f, base) : base === null || base === undefined ? null : col ? formatCell(col, base, row) : String(base);
        tip = text === null || text === "" ? T.baseEmpty : T.baseValue(text);
      } catch { tip = null; }
    }
    if (!tip) return content;
    return <Tooltip content={tip}><span className="sc-cell-source"><span className="sc-cell-value">{content}</span></span></Tooltip>;
  }, [problems, fields, byField]);

  const rowProps: RowProps = useCallback((row) => ({
    ...(row.IsValid === false ? { className: "sc-row-invalid" } : {}),
    ...(onDetail && selectedRowId != null ? { onClick: () => onDetail(row) } : {}),   // kart açıkken satıra tıklamak kartı o satıra çevirir
  }), [onDetail, selectedRowId]);

  const save = async () => {
    const changes = Object.entries(edits.drafts).flatMap(([id, row]) => Object.entries(row).map(([field, value]) => ({ id: Number(id), field, value: value === "" ? null : value })));
    setSaving(true);
    setProblems({});
    try {
      const out = await api.change(sid, changes);
      edits.discard();
      for (const w of out.warnings ?? []) emitNotice(w);
      changed();
    } catch (e) {
      if (e instanceof ApiError && e.details.length) {
        setProblems(Object.fromEntries(e.details.map((d) => [`${String(d.id)}|${d.field}`, d.problem])));
        const d = e.details[0];
        emitNotice(e.details.length === 1 ? T.notSavedOne(d.record ?? "", fields.get(d.field)?.label ?? d.field, lowerFirst(d.problem)) : T.notSavedMany(e.details.length));
      } else {
        emitNotice(e instanceof ApiError ? e.message : T.failed);
      }
    } finally {
      setSaving(false);
    }
  };

  const menu = useRowMenu((row) => T.rowActions(label(row)), (row): MenuAction[] => {
    const items: MenuAction[] = [];
    if (onDetail) items.push({ label: T.menu.detail, onClick: () => onDetail(row) });
    if (!editable(row)) return items;
    items.push({ label: T.menu.edit, onClick: () => setDialog({ row, owner: null }) });
    items.push({ label: T.menu.add, onClick: () => setDialog({ row: null, owner: owner ?? (adapter ? adapter.ownerOf(row) : ownerOf(row)) }) });
    const inherited = !scenario?.isBase && row.Origin !== "Senaryo";   // izleyen senaryoda Baz'dan okunan satır: silinmez, geçersiz yapılır
    if (!inherited) items.push({ label: T.menu.remove, onClick: () => setRemoving(row) });
    else {
      items.push(row.IsValid === false ? { label: T.menu.validate, onClick: () => void run(() => api.validate(sid, row.Id)) }
        : { label: T.menu.invalidate, onClick: () => void run(() => api.invalidate(sid, row.Id)) });
      if (row.Origin === ORIGIN_DIFF) items.push({ label: T.menu.restore, onClick: () => void run(() => api.restore(sid, row.Id)) });
    }
    return items;
  });
  const hasMenu = Boolean(onDetail) || write;

  const toolbarLead = (
    <>
      {lead}
      {write && <Button size="sm" variant="primary" onClick={() => setDialog({ row: null, owner: owner ?? null })}>{T.newRecord}</Button>}
    </>
  );

  return (
    <>
      <DataTable list={spec.list} baseFilters={filters} toolbarLead={toolbarLead} toolbarEnd={end} compact={compact} fieldHints={hints} onColumns={setColumns}
                 reloadKey={reloadKey + tick} cellEditing={write ? editing : undefined} cellRender={cellRender} cellClass={cellClass} cellWrap={cellWrap}
                 rowProps={rowProps} cellMenu={NO_ITEMS} rowMenu={hasMenu ? menu.rowMenu : undefined} selectedRowId={selectedRowId ?? focus?.id ?? null} reveal={focus} onSelection={onSelection}
                 toolbarActions={<EditBar dirty={edits.dirty} busy={saving} onSave={() => void save()} onDiscard={() => { edits.discard(); setProblems({}); }} />} />
      {menu.element}
      <UnsavedGuard dirty={edits.dirty} />
      {dialog && (
        <DialogView spec={spec} scenario={sid} row={dialog.row} owner={dialog.owner} onClose={() => setDialog(null)}
                    onSaved={() => { setDialog(null); changed(); }} />
      )}
      {removing && (
        <ConfirmDialog title={T.removeTitle} message={T.removeText(label(removing))} confirmLabel={T.menu.remove} danger onCancel={() => setRemoving(null)}
                       onConfirm={() => { const row = removing; setRemoving(null); void run(() => api.remove(sid, row.Id)); }} />
      )}
    </>
  );
}
