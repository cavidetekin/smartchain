// Öncelik yönetimi (ekran 32, fonksiyon 25; K-195; docs/12 "Öncelik yönetimi"): müşteri, proje ve sipariş satırı için 1–5 öncelik grubu. Sekmeli:
// Müşteri · Proje · Sipariş (yalnız açık satırlar). Pencere yok: değer hücreye yazılır ya da listeden seçilir (1–5 ve boş); boşaltınca kalkar. Birden
// çok satır seçiliyken yazılan değer hepsine uygulanır (K-187); Excel'den yapıştırılır. Değişen hücre işaretli, Kaydet hepsini birlikte gönderir
// (K-132). "ERP önceliği" (ERP'den gelen değer) ve hesaplanan "Geçerli öncelik grubu", "Öncelik kaynağı" düzenlenmez; girilen "Öncelik grubu"yla ayrı
// kolonlardır. Senaryoda değişen hücre işaretlidir, ipucunda Baz'daki değer; satır menüsünde "Senaryo farkını kaldır". Kart: müşteri ve projede
// kaydın siparişleri ve tahminleri, siparişte müşterisi ve projesi; hepsinde Geçmiş. Ekran senaryoya bağlıdır.
import { type ReactNode, useCallback, useMemo, useRef, useState } from "react";
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
import type { ListFilter, Row } from "../table/types";
import { EditBar, UnsavedGuard, useTableEdits } from "../table/useTableEdits";
import { Alert, type DetailTab, MasterDetail, OverflowTabs, Tooltip } from "../ui";
import type { MenuAction } from "../ui/PopMenu";
import { HISTORY_HINTS } from "./DataScreen";

const T = tr.priorities;
const M = tr.modelConstraints;   // ortak yazılar: fark ipucu, kaydedilmedi bildirimi, satır menüsü
const NO_ITEMS = () => [];
const TABLE = "DemandPriority";
export const PG = "PriorityGroup";
export const GROUPS = ["1", "2", "3", "4", "5"] as const;
const CHOICES = ["", ...GROUPS];                        // hücre listesi: boş (değeri kaldırır) ve 1–5
type Tab = "musteri" | "proje" | "siparis";
type CardTab = "siparisler" | "tahminler" | "musteri" | "proje" | "gecmis";
interface LevelSpec {
  /** Liste, yazma ucundaki düzey, kaydın okunur adı, kartta siparişleri ve tahminleri süzen alan. */
  list: string; level: string; name(row: Row): string; codeField?: string;
  cards: DetailTab<CardTab>[];
}
const text = (v: unknown) => String(v ?? "");
const LEVELS: Record<Tab, LevelSpec> = {
  musteri: { list: "priority-customers", level: "customers", name: (r) => text(r.Code), codeField: "CustomerCode",
             cards: [{ value: "siparisler", label: T.cards.orders, count: 1 }, { value: "tahminler", label: T.cards.forecasts, count: 1 }, { value: "gecmis", label: M.history, count: 1 }] },
  proje: { list: "priority-projects", level: "projects", name: (r) => text(r.Code), codeField: "ProjectCode",
           cards: [{ value: "siparisler", label: T.cards.orders, count: 1 }, { value: "tahminler", label: T.cards.forecasts, count: 1 }, { value: "gecmis", label: M.history, count: 1 }] },
  siparis: { list: "priority-orders", level: "orders", name: (r) => `${text(r.OrderNo)} / ${text(r.LineNo)}`,
             cards: [{ value: "musteri", label: T.cards.customer, count: 1 }, { value: "proje", label: T.cards.project, count: 1 }, { value: "gecmis", label: M.history, count: 1 }] },
};
const TABS: { value: Tab; label: string }[] = [{ value: "musteri", label: T.tabs.customers }, { value: "proje", label: T.tabs.projects }, { value: "siparis", label: T.tabs.orders }];
// Kolon genişlikleri (rem): Sipariş sekmesinde on üç kolon dar tutulur (ana tablo ekrana sığsın; 1440 genişlikte kenar menü daraltılınca tamamı görünür)
const HINTS: FieldHints = { Code: { width: 8 }, Name: { width: 18 }, Priority: { width: 7.4 }, [PG]: { width: 9.6 }, Origin: { width: 7.2 }, LocationCode: { width: 5.5 }, OrderNo: { width: 6.3 },
                            LineNo: { width: 5 }, CustomerCode: { width: 5.6 }, ProjectCode: { width: 5.2 }, MaterialCode: { width: 6.6 }, RequestedDate: { width: 6.8 },
                            OpenQuantity: { width: 7 }, EffectivePriorityGroup: { width: 11.4 }, PrioritySource: { width: 8.8 } };
const lowerFirst = (s: string) => s.charAt(0).toLocaleLowerCase("tr") + s.slice(1);
const saved = (row: Row) => (row[PG] === null || row[PG] === undefined ? "" : String(row[PG]));

function LevelTab({ tab, lead }: { tab: Tab; lead: ReactNode }) {
  const spec = LEVELS[tab];
  const { scenario } = useShell();
  const { me } = useAuth();
  const write = Boolean(me && can(me, 25, "write"));
  const sid = scenario?.id ?? 0;
  const edits = useTableEdits();
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [tick, setTick] = useState(0);
  const [card, setCard] = useState<{ row: Row; tab: CardTab } | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [paste, setPaste] = useState<{ taken: number; rejected: number; details: string[] } | null>(null);
  const seen = useRef(new Map<number, Row>());   // çizilen satırlar (kart seçili kayıtların kodlarıyla süzer)
  const key = (row: Row) => String(row.Id);
  const url = (tail = "") => `/api/priorities/${spec.level}${tail}?scenario_id=${sid}`;
  const overridden = (row: Row) => typeof row.OverriddenFields === "string" && row.OverriddenFields.includes(`,${PG},`);
  const open = (row: Row) => setCard((cur) => ({ row, tab: cur?.tab ?? spec.cards[0].value }));

  const editing: CellEditing = useMemo(() => ({
    editableColumn: (col) => write && col.field === PG,
    canEdit: (col) => write && col.field === PG,
    editor: (_col, row) => ({ kind: "select", text: edits.get(key(row), PG, saved(row)), options: CHOICES }),
    commit: (_col, row, value) => edits.set(key(row), PG, value.trim(), saved(row)),
    label: (col, row) => `${spec.name(row)} · ${col.label}`,
    clear: (col, row) => { if (col.field !== PG) return false; edits.set(key(row), PG, "", saved(row)); return true; },   // Delete: değeri kaldırır
    // Excel'den yapıştırma (K-172 kuralı): yalnız Öncelik grubu kolonuna düşen, 1–5 ya da boş olan hücreler taslağa girer; alınmayanlar tablonun
    // üstünde özetlenir (1–5 dışı değer, düzenlenmeyen alan, tablonun dışı)
    paste: (cells) => {
      let taken = 0, bad = 0, outside = 0;
      const locked = new Map<string, number>();
      for (const c of cells) {
        const value = c.text.trim();
        if (!c.row || !c.col) outside += 1;
        else if (c.col.field !== PG) locked.set(c.col.label, (locked.get(c.col.label) ?? 0) + 1);
        else if (value !== "" && !(GROUPS as readonly string[]).includes(value)) bad += 1;
        else { edits.set(key(c.row), PG, value, saved(c.row)); taken += 1; }
      }
      const lockedCells = [...locked.values()].reduce((n, v) => n + v, 0);
      setPaste({ taken, rejected: bad + outside + lockedCells,
                 details: [...(bad ? [T.pasteNotGroup(bad)] : []), ...(lockedCells ? [T.pasteNotEditable([...locked.keys()], lockedCells)] : []),
                           ...(outside ? [tr.manualValues.pasteOutside(outside)] : [])] });
    },
  }), [write, edits, spec]);  // eslint-disable-line react-hooks/exhaustive-deps

  const cellRender: CellRender = useMemo(() => ({ [PG]: (_v: unknown, row: Row) => edits.get(key(row), PG, saved(row)) }), [edits]);
  const cellClass: CellClass = useCallback((field, row) => {
    if (field !== PG) return undefined;
    const classes = [];
    if (edits.changed(key(row), PG)) classes.push("is-draft");
    if (problems[key(row)]) classes.push("is-invalid");
    if (overridden(row)) classes.push("sc-cell-diff");
    return classes.join(" ") || undefined;
  }, [edits, problems]);
  const cellWrap: CellWrap = useCallback((field, row, content) => {
    if (field !== PG) return content;
    let tip: string | null = problems[key(row)] ?? null;
    if (!tip && overridden(row) && typeof row.BaseValues === "string") {
      try {
        const base = (JSON.parse(row.BaseValues) as Record<string, unknown>)[PG];
        tip = base === null || base === undefined ? M.baseEmpty : M.baseValue(String(base));
      } catch { tip = null; }
    }
    if (!tip) return content;
    return <Tooltip content={tip}><span className="sc-cell-source"><span className="sc-cell-value">{content}</span></span></Tooltip>;
  }, [problems]);

  const save = async () => {
    // sayı gibi yazılan taslak sayı olarak gider; öteki metin olduğu gibi (sunucu nedenini söyler)
    const changes = Object.entries(edits.drafts).map(([id, row]) => {
      const draft = String(row[PG] ?? "");
      return { id: Number(id), field: PG, value: draft === "" ? null : /^\d+$/.test(draft) ? Number(draft) : draft };
    });
    setSaving(true);
    setProblems({});
    try {
      await sendJson<{ saved: number }>("PUT", url(), { changes });
      edits.discard();
      setTick((n) => n + 1);
    } catch (e) {
      if (e instanceof ApiError && e.details.length) {
        setProblems(Object.fromEntries(e.details.map((d) => [String(d.id), d.problem])));
        const d = e.details[0];
        emitNotice(e.details.length === 1 ? M.notSavedOne(d.record ?? "", T.group, lowerFirst(d.problem)) : M.notSavedMany(e.details.length));
      } else {
        emitNotice(e instanceof ApiError ? e.message : M.failed);
      }
    } finally {
      setSaving(false);
    }
  };
  const restore = async (row: Row) => {
    try {
      await sendJson<unknown>("POST", url(`/${row.Id}/restore`));
      setTick((n) => n + 1);
    } catch (e) {
      emitNotice(e instanceof ApiError ? e.message : M.failed);
    }
  };

  const menu = useRowMenu((row) => M.rowActions(spec.name(row)), (row): MenuAction[] => [
    { label: M.menu.detail, onClick: () => open(row) },
    ...(write && row.CanRestore === true ? [{ label: M.menu.restore, onClick: () => void restore(row) }] : []),
  ]);

  // Kart: seçili kayıtlar (çoklu seçimde hepsi, K-171)
  const row = card?.row ?? null;
  const ids = !row ? [] : picked.length ? picked.map(Number) : [row.Id];
  const rowsOf = ids.map((i) => (row && i === row.Id ? row : seen.current.get(i))).filter((r): r is Row => Boolean(r));
  const at = `${card?.tab ?? ""}:${ids.join(",")}`;
  const renderBody = ({ tabs: strip, controls }: { tabs: ReactNode; controls: ReactNode }) => {
    if (!row || !card) return null;
    const common = { compact: true, cellMenu: NO_ITEMS, toolbarLead: strip, toolbarEnd: controls, reloadKey: tick, fieldHints: HINTS };
    if (card.tab === "gecmis") {
      return <DataTable key={`g:${at}`} list={ids.length > 1 ? "record-history-many" : "record-history"} {...common} fieldHints={HISTORY_HINTS}
                        baseFilters={[{ field: "TableName", op: "in", values: [TABLE] },
                                      { field: "RecordKey", op: "in", values: ids.flatMap((i) => [`${spec.level}:${i}`, `${spec.level}:${i}@${sid}`]) }]} />;
    }
    if (card.tab === "siparisler" || card.tab === "tahminler") {   // müşterinin ya da projenin açık siparişleri ve tahminleri (koduyla)
      const codes = rowsOf.map((r) => text(r.Code));
      const filters: ListFilter[] = [{ field: spec.codeField!, op: "in", values: codes.length ? codes : ["—"] }];
      return <DataTable key={at} list={card.tab === "siparisler" ? "priority-orders" : "priority-forecasts"} baseFilters={filters} {...common} />;
    }
    // siparişin müşterisi ve projesi (kendi ERP önceliği ve öncelik gruplarıyla)
    const field = card.tab === "musteri" ? "CustomerId" : "ProjectId";
    const owners = [...new Set(rowsOf.map((r) => r[field]).filter((v): v is number => typeof v === "number"))].map(String);
    return <DataTable key={at} list={card.tab === "musteri" ? "priority-customers" : "priority-projects"} {...common}
                      baseFilters={[{ field: "Id", op: "in", values: owners.length ? owners : ["0"] }]} />;
  };

  return (
    <MasterDetail id={`priorities-${tab}`} onClose={() => setCard(null)} hideTitle
                  master={(
                    <>
                      {paste && (
                        <Alert tone={paste.rejected ? "risk" : "info"} onClose={() => setPaste(null)} title={tr.manualValues.pasteSummary(paste.taken, paste.rejected)}>
                          {paste.details.length > 0 && paste.details.join(" ")}
                        </Alert>
                      )}
                      <DataTable list={spec.list} toolbarLead={lead} fieldHints={HINTS} reloadKey={tick} cellMenu={NO_ITEMS} rowMenu={menu.rowMenu}
                                 cellEditing={write ? editing : undefined} cellRender={cellRender} cellClass={cellClass} cellWrap={cellWrap}
                                 selectedRowId={row?.Id ?? null} onSelection={setPicked}
                                 rowProps={(r) => { seen.current.set(r.Id, r); return card ? { onClick: () => open(r) } : {}; }}
                                 toolbarActions={<EditBar dirty={edits.dirty} busy={saving} onSave={() => void save()} onDiscard={() => { edits.discard(); setProblems({}); }} />} />
                      {menu.element}
                      <UnsavedGuard dirty={edits.dirty} />
                    </>
                  )}
                  detail={card && row ? { title: ids.length > 1 ? M.manyRecords(formatNumber(ids.length)) : spec.name(row), tabsLabel: M.cardTabs, tabs: spec.cards, tab: card.tab,
                                          onTab: (t) => setCard({ row, tab: t }), renderBody } : null} />
  );
}

export function PriorityManagement() {
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
      <LevelTab key={current} tab={current} lead={lead} />
    </section>
  );
}
