// Veri ekranlarının ortak bileşeni (Ana veri 03, İşlem verisi 29; K-168, K-169): aktarılan veri, salt okunur. Sekmeler; çok tablolu sekmede tablo
// seçimi ortak tablonun araç çubuğunun başında açılır liste (kayıt sayılarıyla), tek tablolu sekmede yok (docs/12 "Bölüm ve tablo seçimi").
// Standart görünümde aktarılan bütün alanlar açık; sığmayan kolonlar için tablo kendi içinde yana kayar. İlk sekme varsayılan; son açılan
// sekme ve her sekmenin son tablosu kullanıcı başına hatırlanır.
// Detay kartı (K-171, K-173): satıra tıklamak seçer, ⋯ menüsündeki "Detay" kartı açar; kart açıkken başka satıra tıklamak kartı o kayda geçirir,
// ✕ ya da Esc kapatır. Kart açıkken birden çok satır seçilirse (çoklu seçim) kart seçili kayıtların hepsini tek listede gösterir. Sekmeler Geçmiş ve (ilişkisi olan ana veri tablolarında) İlişkili kayıtlar. Açık kart adreste (kayit, kart) ve tablo
// başına kullanıcı tercihinde.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { ApiError, getJson } from "../api/client";
import { formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { type DataScreenPrefs, userPrefs } from "../prefs";
import { useShell } from "../shell/ShellContext";
import { DataTable, type FieldHints, type RowMenuSpec } from "../table/DataTable";
import type { ListColumn, ListFilter, Row } from "../table/types";
import { UnsavedGuard } from "../table/useTableEdits";
import { Alert, ConfirmDialog, MasterDetail, OverflowTabs } from "../ui";
import { type MenuAction, MenuActions, MenuItem, RowPopMenu } from "../ui/PopMenu";
import { type CardTab, cardOfSlug, HISTORY_TAB, recordUrl, relationSlug, screenQuery, type TabDef, type TableDef } from "./dataScreenTabs";
import { type RecordCard, type RecordsCard, recordsApi } from "./recordsApi";
import { recordLabel, useManualValues } from "./useManualValues";

export type { TabDef, TableDef } from "./dataScreenTabs";

const T = tr.dataScreen;
const MT = tr.manualValues;

export interface DataCounts {
  data_version: number | null;
  /** Güncel veri versiyonundaki satır; veri yüklenmediyse null. */
  tabs: { key: string; tables: { list: string; label: string; count: number | null }[] }[];
}

/** Kolon genişlikleri: kod ve kısa alanlar dar, uzun başlıklı sayı alanları kesilmesin. */
const HINTS: FieldHints = {
  Code: { width: 9 }, MaterialCode: { width: 9 }, ComponentMaterialCode: { width: 9 }, ReferenceMaterialCode: { width: 9 },
  ReferenceProductionVersionCode: { width: 9 }, ResourceCode: { width: 8 }, ResourceGroupCode: { width: 9 }, SupplierCode: { width: 8 },
  ProjectGroupCode: { width: 9 }, CalendarCode: { width: 8 }, RouteCode: { width: 9 }, BOMCode: { width: 9 }, LocationCode: { width: 8 },
  CustomerCode: { width: 8 }, ProjectCode: { width: 8 }, WorkOrderCode: { width: 9 }, ProductionVersionCode: { width: 9 },
  BaseUom: { width: 7 }, ComponentUom: { width: 7 }, CapacityUnit: { width: 8 }, FromUom: { width: 6 }, ToUom: { width: 6 }, Uom: { width: 7 },
  OperationNo: { width: 7.5 }, SequenceNo: { width: 6 }, LineNo: { width: 6 }, Priority: { width: 6 }, Decimals: { width: 6 }, Quantity: { width: 9 },
  MaterialLevel: { width: 9 }, MaterialGroup: { width: 10 }, DefaultSupplyType: { width: 9 },
  WaitingTimeHours: { width: 11 }, TransferTimeHours: { width: 11 }, FixedLeadTimeDays: { width: 12 }, VariableLeadTimeDays: { width: 12 },
  MinimumOrderQuantity: { width: 13 },
};
/** Kart tablolarında hücre menüsü Detay · Kopyala (ek öğe yok, K-173). */
const NO_ITEMS = () => [];
const HISTORY_HINTS: FieldHints = { RecordLabel: { width: 10 }, At: { width: 10 }, DataVersion: { width: 5 }, FieldLabel: { width: 12 }, OldValue: { width: 12 }, NewValue: { width: 12 }, SourceText: { width: 22 } };

interface Card { id: string; tab: CardTab }

/** Satır menüsü (K-171): ilk seçenek "Detay"; sağ tıkta hücre seçenekleri (Kopyala, Manuel değeri kaldır) başta. */
function useDetailMenu(open: (row: Row) => void) {
  const [menu, setMenu] = useState<{ row: Row; anchor: HTMLElement; extra?: MenuAction[] } | null>(null);
  const rowMenu: RowMenuSpec = useMemo(() => ({
    label: (row: Row) => T.rowMenu(recordLabel(row)),
    onOpen: (row: Row, anchor: HTMLElement, extra?: MenuAction[]) => setMenu({ row, anchor, extra }),
  }), []);
  const element = menu ? (
    <RowPopMenu label={T.rowMenu(recordLabel(menu.row))} anchor={menu.anchor} onClose={() => setMenu(null)}>
      <MenuActions items={menu.extra} onDone={() => setMenu(null)} />
      <MenuItem label={T.detail} state={{ allowed: true }} onClick={() => { const row = menu.row; setMenu(null); open(row); }} />
    </RowPopMenu>
  ) : null;
  return { rowMenu, element };
}
interface Choice { tab: string; tables: Record<string, string>; card: Card | null }

function tableOf(tabs: TabDef[], choice: Choice): { tab: TabDef; table: TableDef } {
  const tab = tabs.find((t) => t.key === choice.tab) ?? tabs[0];
  return { tab, table: tab.tables.find((x) => x.list === choice.tables[tab.key]) ?? tab.tables[0] };
}

/** Adresten (yoksa tercihten) seçim: sekme, tablo, açık kart. */
function initial(saved: DataScreenPrefs, tabs: TabDef[], search: string): Choice {
  const params = new URLSearchParams(search);
  const fromUrl = tabs.find((t) => t.key === params.get("sekme"));
  const tab = fromUrl ?? tabs.find((t) => t.key === saved.tab) ?? tabs[0];
  const tables = { ...saved.tables };
  const table = tab.tables.find((x) => x.slug === params.get("tablo"));
  if (fromUrl && table) tables[tab.key] = table.list;
  const list = (tab.tables.find((x) => x.list === tables[tab.key]) ?? tab.tables[0]).list;
  const id = params.get("kayit");
  const card = fromUrl ? (id ? { id, tab: cardOfSlug(params.get("kart")) ?? HISTORY_TAB } : null) : saved.cards?.[list] ?? null;
  return { tab: tab.key, tables, card };
}

export function DataScreen({ id, title, sections, tabs, countsUrl }: {
  /** Hatırlanan seçimin anahtarı (ekran başına). */
  id: string;
  title: string;
  /** Sekme grubunun erişilebilir adı. */
  sections: string;
  tabs: TabDef[];
  countsUrl: string;
}) {
  const { userId } = useShell();
  const { search, pathname } = useLocation();
  const navigate = useNavigate();
  const prefs = userPrefs(userId);
  const [choice, setChoice] = useState<Choice>(() => initial(prefs.dataScreen(id), tabs, search));
  const [counts, setCounts] = useState<Map<string, number | null>>(new Map());
  const [columns, setColumns] = useState<ListColumn[] | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [pending, setPending] = useState<Choice | null>(null);  // kaydedilmemiş manuel değerle sekme ya da tablo değişiyor
  const [picked, setPicked] = useState<string[]>([]);  // çoklu seçim (K-171)

  useEffect(() => {
    const ctrl = new AbortController();
    getJson<DataCounts>(countsUrl, ctrl.signal)
      .then((r) => setCounts(new Map(r.tabs.flatMap((t) => t.tables.map((x) => [x.list, x.count] as const)))))
      .catch(() => { /* sayılar gelmezse seçimde yalnız adlar görünür */ });
    return () => ctrl.abort();
  }, [countsUrl]);

  const { tab, table } = tableOf(tabs, choice);
  const manual = useManualValues(table.list, columns, () => setReloadKey((n) => n + 1));  // manuel değer (K-170)
  const cardOf = (next: Omit<Choice, "card">): Card | null => prefs.dataScreen(id).cards?.[tableOf(tabs, { ...next, card: null }).table.list] ?? null;
  const choose = (next: Omit<Choice, "card">) => {
    const full = { ...next, card: cardOf(next) };  // tablo değişince o tablonun hatırlanan kartı
    if (manual.dirty) setPending(full);
    else setChoice(full);
  };

  // Adres ve hatırlanan seçim (kullanıcı başına). Adres dışarıdan değişince (geri tuşu, "Kayda git", ilişkili satırın rozeti) seçim adresten.
  const query = screenQuery(tab, table, choice.card);
  useEffect(() => {
    const saved = prefs.dataScreen(id);
    const cards = { ...(saved.cards ?? {}) };
    if (choice.card) cards[table.list] = choice.card;
    else delete cards[table.list];
    prefs.setDataScreen(id, { tab: choice.tab, tables: choice.tables, cards });
    if (search.replace(/^\?/, "") !== query) navigate(`${pathname}?${query}`, { replace: true });
  }, [query]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (search.replace(/^\?/, "") === query || !new URLSearchParams(search).get("sekme")) return;
    setChoice(initial(prefs.dataScreen(id), tabs, search));
  }, [search]);  // eslint-disable-line react-hooks/exhaustive-deps

  const label = (x: TableDef) => {
    const n = counts.get(x.list);
    return typeof n === "number" ? T.tableWithCount(x.label, formatNumber(n)) : x.label;
  };
  const picker = tab.tables.length > 1 ? (
    <select className="sc-input sc-select sc-viewbar-select" aria-label={T.table} value={table.list}
            onChange={(e) => choose({ ...choice, tables: { ...choice.tables, [tab.key]: e.target.value } })}>
      {tab.tables.map((x) => <option key={x.list} value={x.list}>{label(x)}</option>)}
    </select>
  ) : null;

  // Şeridin solu (K-173): ekranın sekmeleri (sığmayanlar "Diğer ▾") ve tablo seçimi
  const lead = (
    <>
      <OverflowTabs<string> label={sections} value={tab.key} onChange={(key) => choose({ ...choice, tab: key })}
                            options={tabs.map((t) => ({ value: t.key, label: t.label }))} />
      {picker}
    </>
  );

  // Detay kartı
  const card = choice.card;
  const setCard = useCallback((next: Card | null) => setChoice((c) => ({ ...c, card: next })), []);
  const openCard = useCallback((row: Row) => setChoice((c) => ({ ...c, card: { id: String(row.Id), tab: c.card?.tab ?? HISTORY_TAB } })), []);
  const detailMenu = useDetailMenu(openCard);
  const rowProps = useCallback((row: Row) => (card ? { onClick: () => openCard(row) } : {}), [card, openCard]);

  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{title}</h1>
      </header>
      {manual.paste && (
        <Alert tone={manual.paste.rejected ? "risk" : "info"} onClose={manual.closePaste} title={MT.pasteSummary(manual.paste.taken, manual.paste.rejected)}>
          {manual.paste.details.length > 0 && manual.paste.details.join(" ")}
        </Alert>
      )}
      <RecordCardLayout screen={id} list={table.list} card={card} many={card && picked.length > 1 ? picked : null} onCard={setCard} onClose={() => setCard(null)}
                        master={(
                          <DataTable key={table.list} list={table.list} fieldHints={HINTS} toolbarLead={lead} fitHeaders onColumns={setColumns} reloadKey={reloadKey}
                                     cellRender={manual.cellRender} cellWrap={manual.cellWrap} cellClass={manual.cellClass} toolbarActions={manual.editBar}
                                     cellEditing={manual.cellEditing} selectionMenu={manual.selectionMenu} onSelection={setPicked} rowMenu={detailMenu.rowMenu} rowProps={rowProps} cellMenu={manual.menuItems}
                                     selectedRowId={card ? (Number.isNaN(Number(card.id)) ? card.id : Number(card.id)) : undefined} />
                        )} />
      {detailMenu.element}
      <UnsavedGuard dirty={manual.dirty} />
      {pending && (
        <ConfirmDialog title={tr.table.unsavedTitle} message={tr.table.unsavedText} confirmLabel={tr.table.unsavedLeave} danger
                       onCancel={() => setPending(null)} onConfirm={() => { manual.discard(); setChoice(pending); setPending(null); }} />
      )}
    </section>
  );
}

/** Ana tablo ve detay kartı (ana–detay düzeni, K-161): kartın şeridi tablo standardında; sekmeler tek sıra (Geçmiş ve ilişkiler, sayısız, boş ilişki
 *  pasif), sağda tablo düğmeleri, Büyüt ve ✕; kaydın kodu ve adı gösterilmez (K-171, K-173). */
function RecordCardLayout({ screen, list, card, many, onCard, onClose, master }: {
  screen: string; list: string; card: Card | null;
  /** Çoklu seçimde seçili kayıtlar (K-171): kart hepsini tek listede gösterir. */
  many: string[] | null;
  onCard(card: Card): void; onClose(): void; master: React.ReactNode;
}) {
  const navigate = useNavigate();
  const [record, setRecord] = useState<{ key: string; data: RecordCard | RecordsCard | null; error: string | null } | null>(null);
  const manyKey = many ? many.join(",") : "";
  const key = card ? `${list}|${many ? `*${manyKey}` : card.id}` : null;

  useEffect(() => {
    if (!card || !key) return undefined;
    const ctrl = new AbortController();
    const read = many ? recordsApi.many(list, many, ctrl.signal) : recordsApi.read(list, card.id, ctrl.signal);
    read.then((data) => setRecord({ key, data, error: null }))
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setRecord({ key, data: null, error: e instanceof ApiError && e.status === 404 ? T.notFound : e instanceof Error ? e.message : T.notFound });
      });
    return () => ctrl.abort();
  }, [key]);  // eslint-disable-line react-hooks/exhaustive-deps

  // İlişkili satırın Detay'ı o kaydın kartını açar (ekranın sekmesi ve tablosu değişir)
  const relMenu = useDetailMenu((row) => { const url = rel ? recordUrl(rel.list, row.Id) : null; if (url) navigate(url); });
  const current = record && record.key === key ? record : null;
  const data = current?.data ?? null;
  const relations = (data?.relations ?? []).map((r) => ({ ...r, slug: relationSlug(r.label) }));
  const tabs = [{ value: HISTORY_TAB, label: T.history, count: 1 },
                ...relations.map((r) => ({ value: r.slug, label: r.label, count: r.count }))];  // boş ilişki de seçilir: boş tablo (K-171)
  const rel = relations.find((r) => r.slug === card?.tab);
  const tab: CardTab = rel ? rel.slug : HISTORY_TAB;
  const single = data && "id" in data ? data : null;
  const recordIds = data ? ("ids" in data ? data.ids : [data.id]) : [];
  const historyFilters: ListFilter[] = data ? [{ field: "TableName", op: "in", values: [data.table] }, { field: "RecordKey", op: "in", values: recordIds.length ? recordIds : ["0"] }] : [];
  const historyList = recordIds.length > 1 ? "record-history-many" : "record-history";  // birden çok kayıtta başta Kayıt kolonu (K-171)

  // Kartın şeridi tablo standardında (K-173): solda sekmeler, sağda tablo düğmeleri, Büyüt ve ✕; kaydın kodu ve adı gösterilmez
  const renderBody = ({ tabs: tabStrip, controls }: { tabs: React.ReactNode; controls: React.ReactNode }) => {
    let content: React.ReactNode;
    if (data && rel) {
      content = (
        <DataTable key={`r:${key}:${rel.key}`} list={rel.list} baseFilters={rel.filters} fieldHints={HINTS} cellMenu={NO_ITEMS} compact
                   toolbarLead={tabStrip} toolbarEnd={controls}
                   rowMenu={relMenu.rowMenu} />
      );
    } else if (data) {
      content = <DataTable key={`h:${key}`} list={historyList} baseFilters={historyFilters} fieldHints={HISTORY_HINTS} cellMenu={NO_ITEMS} compact
                           toolbarLead={tabStrip} toolbarEnd={controls} />;
    } else {
      content = (
        <>
          <div className="sc-table-toolbar sc-table-toolbar--compact">
            <div className="sc-table-toolbar-main">{tabStrip}</div>
            <div className="sc-table-tools">{controls}</div>
          </div>
          {current?.error ? <Alert tone="error">{current.error}</Alert> : <p className="sc-muted">{T.loading}</p>}
        </>
      );
    }
    return (
      <div className="sc-card-body">
        {single && !single.current && <Alert tone="risk">{T.closed(single.closed_version)}</Alert>}
        {content}
        {relMenu.element}
      </div>
    );
  };

  return (
    <MasterDetail id={`${screen}-card`} master={master} onClose={onClose} hideTitle
                  detail={card ? {
                    title: many ? T.manyRecords(formatNumber(many.length)) : single?.label ?? card.id, tabsLabel: T.cardTabs, tabs, tab, onTab: (t) => onCard({ ...card, tab: t }), renderBody,
                  } : null} />
  );
}
