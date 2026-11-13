// Manuel değer hücreleri (K-170, K-172, docs/12): "Manuel: Evet" kolonlarda hücre düzenleme standardı (düz metin, ✎, çift tıklama / Enter / F2 /
// yazmaya başlama), taslak lila ve düzenleme çubuğu (K-132), köşe işareti. Kaynak ipucu yalnız değer ERP'den olduğu gibi gelmiyorsa: "Manuel değer:
// değer · kişi · tarih" (alttaki değer güncellendiyse ikinci satır) ya da "Kural: ad". Tekil kaldırma hücre menüsünden (sağ tık) ya da Delete ile,
// toplu kaldırma seçili kayıtlarda. Excel'den yapıştırma: geçerli hücreler taslağa, alınmayanlar neden ve alan bazında sayıyla özetlenir.
// Kaydetme ya hep ya hiç.
import { type ReactNode, useCallback, useMemo, useState } from "react";

import { ApiError, emitNotice } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { formatDateTime } from "../format";
import { tr } from "../i18n/tr";
import { useFlowLock } from "../shell/FlowStatus";
import type { CellEditing, PasteCell } from "../table/cellEditing";
import { type CellClass, type CellMenuItem, type CellRender, type CellWrap, formatCell, type Selection } from "../table/DataTable";
import type { MenuAction } from "../ui/PopMenu";
import type { ListColumn, Row } from "../table/types";
import { EditBar, useTableEdits } from "../table/useTableEdits";
import { Tooltip } from "../ui";
import { type CellSource, type CellSources, type ManualChange, type ManualItem, manualValuesApi } from "./manualValuesApi";

const T = tr.manualValues;
/** Kaldırma taslağı: hücre Kaydet'e kadar alttaki değeri gösterir. */
export const REMOVE = "\u0000kaldır";
const BOOL = ["Evet", "Hayır"] as const;

const sources = (row: Row) => (row._sources ?? {}) as CellSources;
const lowerFirst = (s: string) => s.charAt(0).toLocaleLowerCase("tr") + s.slice(1);

/** Satırın okunur adı (hata ve yapıştırma listesi): kod, sipariş ve satır, iş emri…; yoksa kayıt no. */
export function recordLabel(row: Row): string {
  for (const key of ["Code", "OrderNo", "PurchaseOrderNo", "WorkOrderNo", "ConfirmationNo", "RouteCode", "MaterialCode", "ResourceCode"]) {
    const v = row[key];
    if (v !== null && v !== undefined && v !== "") return row.LineNo !== undefined && key.endsWith("OrderNo") ? `${String(v)} / ${String(row.LineNo)}` : String(v);
  }
  return `#${String(row.Id)}`;
}

/** Düzenleyicideki metin: sayıda binlik ayraç yok, ondalık virgül; tarih gg.aa.yyyy; Evet/Hayır. */
function editText(col: ListColumn, v: unknown, row: Row): string {
  if (v === null || v === undefined) return "";
  if (col.type === "bool") return v ? BOOL[0] : BOOL[1];
  if (col.type === "number" || col.type === "integer") return String(v).replace(".", ",");
  if (col.type === "date" || col.type === "datetime") return formatCell(col, v, row);
  return String(v);
}

/** Türkçe sayı metni (1.234,5 ya da 1234.5) sayıya; değilse null. */
function parseNumber(text: string): number | null {
  let t = text.trim().replace(/\s/g, "");
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  else if (/^-?\d{1,3}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, "");
  const n = Number(t);
  return t !== "" && Number.isFinite(n) ? n : null;
}

type ProblemKey = keyof typeof T.problems;

/** Yapıştırılan değerin denetimi (sunucuyla aynı kalıp, K-172); boş değer burada geçer, zorunluluğu sunucu denetler. */
export function checkText(col: ListColumn, text: string): { text: string; problem: ProblemKey | null } {
  const t = text.trim();
  if (t === "") return { text: "", problem: null };
  if (col.type === "bool") {
    const w = t.toLocaleLowerCase("tr");
    if (["evet", "1", "true", "e"].includes(w)) return { text: BOOL[0], problem: null };
    if (["hayır", "hayir", "0", "false", "h"].includes(w)) return { text: BOOL[1], problem: null };
    return { text: t, problem: "bool" };
  }
  if (col.type === "number" || col.type === "integer") {
    const n = parseNumber(t);
    if (n === null) return { text: t, problem: col.type === "integer" ? "integer" : "number" };
    if (col.type === "integer" && !Number.isInteger(n)) return { text: t, problem: "integer" };
    return { text: t, problem: null };
  }
  if (col.type === "date" || col.type === "datetime") {
    const dotted = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(t);
    const iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(t);
    if (!dotted && !iso) return { text: t, problem: "date" };
    const [d, mo, y] = dotted ? [Number(dotted[1]), Number(dotted[2]), Number(dotted[3])] : [Number(iso![3]), Number(iso![2]), Number(iso![1])];
    const date = new Date(y, mo - 1, d);
    if (date.getFullYear() !== y || date.getMonth() !== mo - 1 || date.getDate() !== d) return { text: t, problem: "date" };
    return { text: t, problem: null };
  }
  if (col.values) {
    const hit = col.values.map(String).find((v) => v.toLocaleLowerCase("tr") === t.toLocaleLowerCase("tr"));
    return hit ? { text: hit, problem: null } : { text: t, problem: "list" };
  }
  return { text: t, problem: null };
}

/** Kaynak ipucu (K-172): yalnız manuel değer ve kural sonucu; ERP'den olduğu gibi gelen değerde yok. */
function sourceLines(col: ListColumn, cell: CellSource | undefined, row: Row): string[] {
  if (!cell) return [];
  const ruleName = cell.rule_name || (cell.rule_id ? T.ruleNo(cell.rule_id) : "");
  if (cell.source === "Kural") return [T.rule(ruleName)];
  const lines = [T.manual(formatCell(col, row[col.field], row) || T.empty, cell.by ?? "", cell.at ? formatDateTime(new Date(cell.at)) : "")];
  if (cell.changed) {
    const from = formatCell(col, cell.base, row) || T.empty;
    const to = formatCell(col, cell.underlying, row) || T.empty;
    lines.push(cell.underlying_source === "Kural" ? T.changedRule(ruleName, from, to) : T.changedErp(from, to));
  }
  return lines;
}

/** Yapıştırma özeti (K-172): alınan ve alınmayan hücre sayısı; alınmayanlar neden ve alan bazında sayıyla, hücreler tek tek değil. */
export interface PasteReport { taken: number; rejected: number; details: string[] }

export function pasteReport(taken: number, groups: Map<ProblemKey, { fields: string[]; cells: number }>, outside: number): PasteReport {
  const details = [...groups].map(([key, g]) => T.pasteGroup(T.pasteReasons[key], g.fields, g.cells));
  if (outside) details.push(T.pasteOutside(outside));
  return { taken, rejected: outside + [...groups.values()].reduce((n, g) => n + g.cells, 0), details };
}

export function useManualValues(list: string, columns: ListColumn[] | null, onSaved: () => void) {
  const me = useAuth().me!;
  const canEdit = can(me, 12, "write");
  const canRemove = can(me, 13, "write");
  const flowLock = useFlowLock();
  const edits = useTableEdits();
  const [saving, setSaving] = useState(false);
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [paste, setPaste] = useState<PasteReport | null>(null);
  const byField = useMemo(() => new Map((columns ?? []).map((c) => [c.field, c])), [columns]);
  /** Tabloda manuel alan var mı: yoksa hücre imleci, ✎ ve seçim kutuları da yok (K-172). */
  const hasManual = useMemo(() => (columns ?? []).some((c) => c.manual), [columns]);
  const cellKey = (row: Row, field: string) => `${String(row.Id)}|${field}`;

  const savedText = (col: ListColumn, row: Row) => editText(col, row[col.field], row);
  const draft = (row: Row, field: string) => edits.get<unknown>(String(row.Id), field, undefined);

  const removable = (row: Row, field: string) => canRemove && sources(row)[field]?.source === "Manuel" && draft(row, field) !== REMOVE;
  const removeCell = (row: Row, field: string) => edits.set(String(row.Id), field, REMOVE, undefined);

  const cellEditing: CellEditing | undefined = useMemo(() => {
    if (!canEdit || !hasManual) return undefined;
    return {
      editableColumn: (col) => Boolean(col.manual),
      canEdit: (col) => Boolean(col.manual),
      editor: (col, row) => {
        const d = draft(row, col.field);
        const text = d === undefined || d === REMOVE ? savedText(col, row) : String(d);
        if (col.type === "bool") return { kind: "select", text, options: ["", ...BOOL] };
        if (col.values && col.type === "text") return { kind: "select", text, options: ["", ...col.values.map(String)] };
        return { kind: "text", text, placeholder: col.type === "date" ? T.datePlaceholder : undefined };
      },
      commit: (col, row, text) => edits.set(String(row.Id), col.field, text, savedText(col, row)),
      label: (col) => T.cellLabel(col.label),
      clear: (col, row) => {
        if (!removable(row, col.field)) return false;
        removeCell(row, col.field);
        return true;
      },
      paste: (cells: PasteCell[]) => {
        const groups = new Map<ProblemKey, { fields: string[]; cells: number }>();
        const reject = (key: ProblemKey, col: ListColumn) => {
          const g = groups.get(key) ?? { fields: [], cells: 0 };
          if (!g.fields.includes(col.label)) g.fields.push(col.label);
          g.cells += 1;
          groups.set(key, g);
        };
        let taken = 0;
        let outside = 0;
        for (const c of cells) {
          if (!c.col || !c.row) {
            outside += 1;
            continue;
          }
          if (!c.col.manual) {
            reject("notManual", c.col);
            continue;
          }
          const checked = checkText(c.col, c.text);
          if (checked.problem) {
            reject(checked.problem, c.col);
            continue;
          }
          edits.set(String(c.row.Id), c.col.field, checked.text, savedText(c.col, c.row));
          taken += 1;
        }
        setPaste(pasteReport(taken, groups, outside));
      },
    };
  }, [canEdit, canRemove, hasManual, edits]);  // eslint-disable-line react-hooks/exhaustive-deps

  const cellRender: CellRender = useMemo(() => Object.fromEntries((columns ?? []).filter((c) => c.manual).map((col) => [col.field, (value: unknown, row: Row) => {
    const d = draft(row, col.field);
    if (d === REMOVE) return <span className="sc-cell-removed">{formatCell(col, sources(row)[col.field]?.underlying, row)}</span>;
    if (d !== undefined) return String(d);
    return formatCell(col, value, row);
  }])), [columns, edits]);  // eslint-disable-line react-hooks/exhaustive-deps

  // Kaynak ipucu yalnız manuel değer, kural sonucu ya da geçersiz taslakta. Sağ tık hücre menüsü ortak tablonun hücresinde (menuItems, K-173).
  const cellWrap: CellWrap = useCallback((field: string, row: Row, content: ReactNode) => {
    const col = byField.get(field);
    if (!col) return content;
    const problem = problems[cellKey(row, field)];
    const lines = problem ? [problem] : sourceLines(col, sources(row)[field], row);
    if (!lines.length) return content;
    return (
      <Tooltip content={lines.map((line) => <div key={line}>{line}</div>)}>
        <span className="sc-cell-source">
          <span className="sc-cell-value">{content}</span>
        </span>
      </Tooltip>
    );
  }, [byField, problems, canRemove, edits]);  // eslint-disable-line react-hooks/exhaustive-deps

  const cellClass: CellClass = useCallback((field: string, row: Row) => {
    const cell = sources(row)[field];
    const classes = [];
    if (cell?.source === "Manuel") classes.push(cell.changed ? "sc-cell-manual is-changed" : "sc-cell-manual");
    if (edits.changed(String(row.Id), field)) classes.push("is-draft");
    if (problems[cellKey(row, field)]) classes.push("is-invalid");
    return classes.join(" ") || undefined;
  }, [problems, edits]);

  // Toplu kaldırma (K-170, K-171): çoklu seçimde seçili satıra sağ tık → "Seçili n satır · Manuel değerleri kaldır"; seçili kayıtların bütün
  // manuel değerleri taslağa (Kaydet ile yazılır). Yalnız manuel alanı olan tabloda ve kaldırma yetkisinde.
  const removeRows = async (selection: Selection) => {
    const rows = await selection.rows();
    const cells = rows.flatMap((r) => Object.entries(sources(r)).filter(([f, c]) => c.source === "Manuel" && draft(r, f) !== REMOVE).map(([f]) => [r, f] as const));
    if (!cells.length) {
      emitNotice(T.removePickedNone);
      return;
    }
    for (const [r, f] of cells) removeCell(r, f);
  };
  const selectionMenu = useCallback((selection: Selection): MenuAction[] => (canRemove && hasManual
    ? [{ label: T.removePicked, onClick: () => void removeRows(selection) }] : []), [canRemove, hasManual, edits]);  // eslint-disable-line react-hooks/exhaustive-deps

  const save = async () => {
    const changes: ManualChange[] = [];
    const removes: ManualItem[] = [];
    for (const [id, fields] of Object.entries(edits.drafts)) {
      for (const [field, value] of Object.entries(fields)) {
        if (value === REMOVE) {
          removes.push({ id, field });
          continue;
        }
        const col = byField.get(field);
        const text = String(value);
        changes.push({ id, field, value: col?.type === "bool" ? (text === "" ? null : text === BOOL[0]) : text === "" ? null : text });
      }
    }
    setSaving(true);
    setProblems({});
    try {
      if (changes.length) await manualValuesApi.save(list, changes);
      if (removes.length) await manualValuesApi.remove(list, removes);
      edits.discard();
      setPaste(null);
      emitNotice(T.saved(changes.length, removes.length));
      onSaved();
    } catch (e) {
      if (e instanceof ApiError && e.details.length) {
        setProblems(Object.fromEntries(e.details.map((d) => [`${String(d.id)}|${d.field}`, d.problem])));
        const d = e.details[0];
        emitNotice(e.details.length === 1 ? T.notSavedOne(d.record ?? "", byField.get(d.field)?.label ?? d.field, lowerFirst(d.problem)) : T.notSavedMany(e.details.length));
      } else {
        emitNotice(e instanceof ApiError ? e.message : T.failed);
      }
    } finally {
      setSaving(false);
    }
  };

  const discard = () => {
    edits.discard();
    setProblems({});
    setPaste(null);
  };

  const editBar = canEdit || canRemove
    ? <EditBar dirty={edits.dirty} busy={saving} onSave={() => void save()} onDiscard={discard} disabledReason={flowLock} />
    : null;

  // Ortak tablonun hücre menüsüne (sağ tık, K-173) ek öğe: manuel değerli hücrede kaldırma taslağı
  const menuItems = useCallback((col: ListColumn, row: Row): CellMenuItem[] => (removable(row, col.field)
    ? [{ label: T.removeOne, onClick: () => removeCell(row, col.field) }] : []), [canRemove, edits]);  // eslint-disable-line react-hooks/exhaustive-deps

  return { cellEditing, cellRender, cellWrap, cellClass, selectionMenu, editBar, menuItems, paste, closePaste: () => setPaste(null), dirty: edits.dirty, discard };
}
