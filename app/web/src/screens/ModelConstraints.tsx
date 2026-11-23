// Model kısıtları (ekran 31, fonksiyon 103; K-189; docs/12 "Model kısıtları"): kaynak grubunun kısıtsız kapasite çarpanı ve hedef doluluğu. Sekmeli:
// "Kaynak grubu", "Tedarikçi limiti" (K-191; `SupplierLimits.tsx`) ve "Malzeme blokajı" (K-193; `MaterialHolds.tsx`); yeni sekme TABS'e eklenir. Her kaynak grubu bir satırdır; "Yeni kayıt" ve pencere yok: değer hücreye yazılır,
// silmek için hücre boşaltılır (K-132: değişen hücre işaretli, Kaydet hepsini birlikte gönderir). Senaryoda değişen hücre işaretlidir, ipucunda Baz'daki
// değer; değeri senaryodan gelen satırın menüsünde "Senaryo farkını kaldır" (sunucunun `CanRestore` alanı). Giriş kısıtlanmaz: değer kritik olmayan
// gruba da girilir (motor yalnız kritik grubunkini okur). ⋯ › Detay: kartta Geçmiş. Ekran senaryoya bağlıdır.
import { type ReactNode, useCallback, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { ApiError, emitNotice, sendJson } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import type { CellEditing } from "../table/cellEditing";
import { type CellClass, type CellRender, type CellWrap, DataTable, type FieldHints } from "../table/DataTable";
import { useRowMenu } from "../table/rowMenu";
import type { Row } from "../table/types";
import { EditBar, UnsavedGuard, useTableEdits } from "../table/useTableEdits";
import { type DetailTab, MasterDetail, OverflowTabs, Tooltip } from "../ui";
import type { MenuAction } from "../ui/PopMenu";
import { HISTORY_HINTS } from "./DataScreen";
import { MaterialHoldsTab } from "./MaterialHolds";
import { SupplierLimitsTab } from "./SupplierLimits";

const T = tr.modelConstraints;
const NO_ITEMS = () => [];
const LIST = "model-constraints-resource-groups";
const TABLE = "ResourceGroupConstraint";
export const FACTOR = "UnconstrainedCapacityFactor", TARGET = "TargetUtilizationPct";
const VALUE_FIELDS = [FACTOR, TARGET];
const FIELD_LABEL: Record<string, string> = { [FACTOR]: T.factor, [TARGET]: T.target };
type Tab = "kaynak-grubu" | "tedarikci-limiti" | "malzeme-blokaji";
const TABS: { value: Tab; label: string }[] = [{ value: "kaynak-grubu", label: T.tabs.groups }, { value: "tedarikci-limiti", label: T.tabs.suppliers },
                                                 { value: "malzeme-blokaji", label: T.tabs.holds }];
const HISTORY_TABS: DetailTab<"gecmis">[] = [{ value: "gecmis", label: T.history, count: 1 }];
const HINTS: FieldHints = { LocationCode: { width: 7 }, Code: { width: 9 }, Name: { width: 18 }, IsCritical: { width: 5.5 }, CapacityUnit: { width: 8 }, [FACTOR]: { width: 13 }, [TARGET]: { width: 11 },
                            Origin: { width: 8 } };
const lowerFirst = (s: string) => s.charAt(0).toLocaleLowerCase("tr") + s.slice(1);
const url = (scenario: number, tail = "") => `/api/model-constraints/resource-groups${tail}?scenario_id=${scenario}`;

/** Yazım: çarpan iki ondalık ("1,50"); hedef doluluk "%85" (gereksiz ondalık yazılmaz). edit: düzenleyicideki sayı ("85"). */
export function constraintText(field: string, value: unknown, edit = false): string {
  if (value === null || value === undefined || value === "") return "";
  const n = Number(value);
  if (field !== TARGET) return formatNumber(n, 2);
  const text = formatNumber(n, Number.isInteger(n) ? 0 : Number.isInteger(n * 10) ? 1 : 2);
  return edit ? text : `%${text}`;
}

function GroupsTab({ lead }: { lead: ReactNode }) {
  const { scenario } = useShell();
  const { me } = useAuth();
  const write = Boolean(me && can(me, 103, "write"));
  const sid = scenario?.id ?? 0;
  const edits = useTableEdits();
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [tick, setTick] = useState(0);
  const [card, setCard] = useState<Row | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const key = (row: Row) => String(row.Id);
  const cellKey = (row: Row, field: string) => `${row.Id}|${field}`;
  const label = (row: Row) => T.record(String(row.Code ?? ""));
  const overridden = (row: Row, field: string) => typeof row.OverriddenFields === "string" && row.OverriddenFields.includes(`,${field},`);

  const editing: CellEditing = useMemo(() => ({
    editableColumn: (col) => write && VALUE_FIELDS.includes(col.field),
    canEdit: (col) => write && VALUE_FIELDS.includes(col.field),   // bütün gruplarda (kritik olmayan dahil)
    editor: (col, row) => ({ kind: "text", text: edits.get(key(row), col.field, constraintText(col.field, row[col.field], true)) }),
    commit: (col, row, text) => edits.set(key(row), col.field, text.trim().replace(/^%/, ""), constraintText(col.field, row[col.field], true)),
    label: (col, row) => `${label(row)} · ${col.label}`,
  }), [write, edits]);  // eslint-disable-line react-hooks/exhaustive-deps

  // Hücre: taslak varsa yazılan değer (hedef dolulukta başında "%"), yoksa kayıtlı değerin yazımı
  const cellRender: CellRender = useMemo(() => Object.fromEntries(VALUE_FIELDS.map((field) => [field, (_v: unknown, row: Row) => {
    if (!edits.changed(key(row), field)) return constraintText(field, row[field]);
    const draft = edits.get(key(row), field, "");
    return draft && field === TARGET ? `%${draft}` : draft;
  }])), [edits]);

  const cellClass: CellClass = useCallback((field, row) => {
    if (!VALUE_FIELDS.includes(field)) return undefined;
    const classes = [];
    if (edits.changed(key(row), field)) classes.push("is-draft");
    if (problems[cellKey(row, field)]) classes.push("is-invalid");
    if (overridden(row, field)) classes.push("sc-cell-diff");
    return classes.join(" ") || undefined;
  }, [edits, problems]);

  const cellWrap: CellWrap = useCallback((field, row, content) => {
    if (!VALUE_FIELDS.includes(field)) return content;
    let tip: string | null = problems[cellKey(row, field)] ?? null;
    if (!tip && overridden(row, field) && typeof row.BaseValues === "string") {
      try {
        const text = constraintText(field, (JSON.parse(row.BaseValues) as Record<string, unknown>)[field]);
        tip = text ? T.baseValue(text) : T.baseEmpty;
      } catch { tip = null; }
    }
    if (!tip) return content;
    return <Tooltip content={tip}><span className="sc-cell-source"><span className="sc-cell-value">{content}</span></span></Tooltip>;
  }, [problems]);

  const save = async () => {
    const changes = Object.entries(edits.drafts).flatMap(([id, row]) => Object.entries(row).map(([field, value]) => ({ id: Number(id), field, value: value === "" ? null : value })));
    setSaving(true);
    setProblems({});
    try {
      await sendJson<{ saved: number }>("PUT", url(sid), { changes });
      edits.discard();
      setTick((n) => n + 1);
    } catch (e) {
      if (e instanceof ApiError && e.details.length) {
        setProblems(Object.fromEntries(e.details.map((d) => [`${String(d.id)}|${d.field}`, d.problem])));
        const d = e.details[0];
        emitNotice(e.details.length === 1 ? T.notSavedOne(d.record ?? "", FIELD_LABEL[d.field] ?? d.field, lowerFirst(d.problem)) : T.notSavedMany(e.details.length));
      } else {
        emitNotice(e instanceof ApiError ? e.message : T.failed);
      }
    } finally {
      setSaving(false);
    }
  };
  const restore = async (row: Row) => {
    try {
      await sendJson<unknown>("POST", url(sid, `/${row.Id}/restore`));
      setTick((n) => n + 1);
    } catch (e) {
      emitNotice(e instanceof ApiError ? e.message : T.failed);
    }
  };

  const menu = useRowMenu((row) => T.rowActions(String(row.Code ?? "")), (row): MenuAction[] => [
    { label: T.menu.detail, onClick: () => setCard(row) },
    ...(write && row.CanRestore === true ? [{ label: T.menu.restore, onClick: () => void restore(row) }] : []),
  ]);

  // Kart: Geçmiş kaynak grubu kimliğiyle (Baz) ve izleyen senaryodaki değişikliklerin senaryolu anahtarıyla; çoklu seçimde seçili grupların hepsi (K-171)
  const ids = !card ? [] : picked.length ? picked.map(Number) : [card.Id];
  const renderBody = ({ tabs: strip, controls }: { tabs: ReactNode; controls: ReactNode }) => (card ? (
    <DataTable key={`g:${ids.join(",")}`} list={ids.length > 1 ? "record-history-many" : "record-history"} compact cellMenu={NO_ITEMS} fieldHints={HISTORY_HINTS}
               baseFilters={[{ field: "TableName", op: "in", values: [TABLE] }, { field: "RecordKey", op: "in", values: ids.flatMap((i) => [String(i), `${i}@${sid}`]) }]}
               toolbarLead={strip} toolbarEnd={controls} reloadKey={tick} />
  ) : null);

  return (
    <MasterDetail id="model-constraints-groups" onClose={() => setCard(null)} hideTitle
                  master={(
                    <>
                      <DataTable list={LIST} toolbarLead={lead} fieldHints={HINTS} reloadKey={tick} cellMenu={NO_ITEMS} rowMenu={menu.rowMenu}
                                 cellEditing={write ? editing : undefined} cellRender={cellRender} cellClass={cellClass} cellWrap={cellWrap}
                                 selectedRowId={card?.Id ?? null} onSelection={setPicked} rowProps={(r) => (card ? { onClick: () => setCard(r) } : {})}
                                 toolbarActions={<EditBar dirty={edits.dirty} busy={saving} onSave={() => void save()} onDiscard={() => { edits.discard(); setProblems({}); }} />} />
                      {menu.element}
                      <UnsavedGuard dirty={edits.dirty} />
                    </>
                  )}
                  detail={card ? { title: ids.length > 1 ? T.manyRecords(formatNumber(ids.length)) : String(card.Code ?? ""), tabsLabel: T.cardTabs, tabs: HISTORY_TABS, tab: "gecmis" as const,
                                   onTab: () => undefined, renderBody } : null} />
  );
}

export function ModelConstraints() {
  // Seçili sekme adreste (`?sekme=`); useSearchParams kullanılmaz (internetsizlik testi, bkz. Kapasite yönetimi)
  const location = useLocation();
  const navigate = useNavigate();
  const wanted = new URLSearchParams(location.search).get("sekme");
  const current: Tab = TABS.some((t) => t.value === wanted) ? wanted as Tab : TABS[0].value;
  const lead = <OverflowTabs<Tab> label={T.sections} value={current} options={TABS}
                                  onChange={(v) => navigate({ pathname: location.pathname, search: v === TABS[0].value ? "" : `?sekme=${v}` }, { replace: true })} />;
  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{T.title}</h1>
      </header>
      {current === "kaynak-grubu" && <GroupsTab lead={lead} />}
      {current === "tedarikci-limiti" && <SupplierLimitsTab lead={lead} />}
      {current === "malzeme-blokaji" && <MaterialHoldsTab lead={lead} />}
    </section>
  );
}
