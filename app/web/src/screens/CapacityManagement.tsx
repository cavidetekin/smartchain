// Kapasite yönetimi (ekran 30, fonksiyon 24; K-185, K-187, K-188; docs/12 "Kapasite yönetimi"). Sekmeler: Kapasite özeti (dönem tablosu, K-184; salt
// okunur, girişlerden hesaplanır) · Kaynak grubu · Kaynak (aktarılan veri; ⋯ › Detay kartı açar) · Çalışma düzeni · Bakım ve duruşlar · Verimlilik ·
// Fabrika takvimi · Ek mesai limitleri (giriş tabloları, 7.9b). Kartlar ana–detay düzenindedir; kart sekmeleri ortak tablodur. Çoklu seçimde kart
// seçili kayıtların hepsini gösterir (K-171). Ekran senaryoya bağlıdır: senaryo değişince baştan yüklenir. Çalışma düzeni, Verimlilik ve Ek mesai
// limitleri'nde tablo seçimi Kayıtlar · Geçerlilik (7.9c, K-188): her girişin seçimi ayrı.
// Sekme durumu (K-188): her üst sekme bir kez açılır ve ekrandan çıkılana kadar durumunu korur (süzme, seçim, açık kart, kartın sekmesi, tablo
// seçimi); öteki sekmedeyken gizli durur. Bir sekmede kayıt değişince bütün sekmelerin tabloları yenilenir (`version`).
import { type ReactNode, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import { DataTable, type FieldHints } from "../table/DataTable";
import { useRowMenu } from "../table/rowMenu";
import type { ListFilter, Row } from "../table/types";
import { type DetailTab, MasterDetail, OverflowTabs } from "../ui";
import { EntryTable } from "./CapacityEntries";
import { TableChoice, type TableView, VALIDITY, ValidityView } from "./CapacityValidity";
import { HISTORY_HINTS } from "./DataScreen";
import { ENTRIES, type EntryKind, type Owner } from "./capacityModel";
import { useManyLocations, withLocation } from "./locationField";

const T = tr.capacity;
const NO_ITEMS = () => [];
const MASTER_HINTS: FieldHints = { LocationCode: { width: 6.5 } };   // Lokasyon kodu dar kolon (K-189)
type Tab = "ozet" | "grup" | "kaynak" | "calisma-duzeni" | "duruslar" | "verimlilik" | "takvim" | "ek-mesai";
const TABS: { value: Tab; label: string }[] = [
  { value: "ozet", label: T.tabs.summary }, { value: "grup", label: T.tabs.groups }, { value: "kaynak", label: T.tabs.resources },
  { value: "calisma-duzeni", label: T.tabs.workPatterns }, { value: "duruslar", label: T.tabs.downtime }, { value: "verimlilik", label: T.tabs.efficiency },
  { value: "takvim", label: T.tabs.calendar }, { value: "ek-mesai", label: T.tabs.overtime },
];
const ENTRY_OF: Partial<Record<Tab, EntryKind>> = { "calisma-duzeni": "work-patterns", duruslar: "downtime", verimlilik: "efficiency", takvim: "factory-calendar", "ek-mesai": "overtime-limits" };

// Kart sekmeleri: Kaynak grubunda dönem özeti, kaynakları ve dört giriş; Kaynakta dört giriş (Geçmiş yok, K-187); giriş kaydında Geçmiş
type CardTab = "donem" | "kaynaklar" | "gecmis" | EntryKind;
const OWNER_ENTRIES: EntryKind[] = ["work-patterns", "downtime", "efficiency", "overtime-limits"];
const tab = (value: CardTab, label: string): DetailTab<CardTab> => ({ value, label, count: 1 });
const GROUP_TABS = [tab("donem", T.card.period), tab("kaynaklar", T.card.resources), ...OWNER_ENTRIES.map((k) => tab(k, ENTRIES[k].title))];
const RESOURCE_TABS = OWNER_ENTRIES.map((k) => tab(k, ENTRIES[k].title));
const HISTORY_TABS = [tab("gecmis", T.card.history)];

/** Girişin tablo seçimi ve "Kayda git" ile seçili gösterilecek kayıt (her giriş için ayrı). */
type Views = Partial<Record<EntryKind, TableView>>;
type Focus = Partial<Record<EntryKind, { id: number; n: number }>>;
/** Sekmelerin ortak bağlamı: kayıt değişince artan sayaç ve değişikliği bildiren işlev. */
interface Shared { version: number; onChanged(): void }

/** Kartın kayıtları: açılan kayıt; üst tabloda satır seçiliyse (Ctrl, Shift ya da seçim kutusu) seçili kayıtların hepsi (K-171). Tek satır
 *  Ctrl ile seçildiyse kart o kaydı gösterir (kart ilk açılan kayıtta kalmaz, K-187). */
const idsOf = (card: Row | null, picked: string[]): number[] => (!card ? [] : picked.length ? picked.map(Number) : [card.Id]);

/** Girişin iki tablosu (Kayıtlar · Geçerlilik) için seçim ve "Kayda git" durumu. */
function useViews(initial: Views = {}) {
  const [views, setViews] = useState<Views>(initial);
  const [focus, setFocus] = useState<Focus>({});
  const setView = (kind: EntryKind, view: TableView) => setViews((cur) => ({ ...cur, [kind]: view }));
  /** Kayıtlar'a geçer ve kaydı seçili gösterir. */
  const goTo = (kind: EntryKind, id: number) => {
    setView(kind, "kayitlar");
    setFocus((cur) => ({ ...cur, [kind]: { id, n: (cur[kind]?.n ?? 0) + 1 } }));
  };
  return { views, focus, setView, goTo };
}

/** Kaynak grubu ve Kaynak sekmeleri: aktarılan veri (salt okunur); ⋯ › Detay alttaki kartı açar. */
function OwnerTab({ level, lead, shared }: { level: "group" | "resource"; lead: ReactNode; shared: Shared }) {
  const list = level === "group" ? "capacity-resource-groups" : "capacity-resources";
  const [card, setCard] = useState<{ row: Row; tab: CardTab } | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const manyLocations = useManyLocations();   // birden çok lokasyonda kart başlığı "lokasyon · kod" (K-194)
  const seen = useRef(new Map<number, string>());   // çizilen satırların kodu (dönem özeti kodla süzülür; seçili satırlar tıklandığı için çizilmiştir)
  const { views, focus, setView, goTo } = useViews();   // her girişin tablo seçimi ayrı (K-188)
  const tabs = level === "group" ? GROUP_TABS : RESOURCE_TABS;
  const open = (row: Row) => setCard((cur) => ({ row, tab: cur?.tab ?? tabs[0].value }));
  const menu = useRowMenu((row) => T.rowActions(String(row.Code ?? "")), (row) => [{ label: T.menu.detail, onClick: () => open(row) }]);
  const row = card?.row ?? null;
  const ids = idsOf(row, picked);
  const many = ids.length > 1;
  const key = ids.join(",");
  const owner: Owner | null = row && !many && ids[0] === row.Id ? { level, id: row.Id, code: String(row.Code ?? "") } : null;
  // Grup kartı: grubun kendisine ve kaynaklarına girilmiş kayıtlar; kaynak kartı: yalnız kaynağa girilmiş kayıtlar (çoklu seçimde herhangi biri)
  const filters: ListFilter[] = useMemo(() => (ids.length ? [{ field: "OwnerKeys", op: "contains", values: ids.map((i) => `,${level === "group" ? "g" : "r"}${i},`) }] : []),
    [key, level]);  // eslint-disable-line react-hooks/exhaustive-deps
  const memberFilters: ListFilter[] = useMemo(() => [{ field: "GroupKeys", op: "contains", values: ids.map((i) => `,${i},`) }], [key]);  // eslint-disable-line react-hooks/exhaustive-deps

  const renderBody = ({ tabs: strip, controls }: { tabs: ReactNode; controls: ReactNode }) => {
    if (!row || !card) return null;
    const at = `${card.tab}:${key}`;
    if (card.tab === "donem") {
      const groupCodes = ids.map((i) => (i === row.Id ? String(row.Code) : seen.current.get(i))).filter((c): c is string => Boolean(c));
      return <DataTable key={at} list="period-resource-group" compact cellMenu={NO_ITEMS} toolbarLead={strip} toolbarEnd={controls} reloadKey={shared.version}
                        baseFilters={[{ field: "ResourceGroupCode", op: "in", values: groupCodes.length ? groupCodes : ["—"] }]} />;
    }
    if (card.tab === "kaynaklar") {
      return <DataTable key={at} list="capacity-resources" baseFilters={memberFilters} compact cellMenu={NO_ITEMS} toolbarLead={strip} toolbarEnd={controls} />;
    }
    if (card.tab === "gecmis") return null;
    const kind = card.tab;
    const choice = VALIDITY[kind] ? <TableChoice value={views[kind] ?? "kayitlar"} onChange={(v) => setView(kind, v)} /> : null;
    const head = <>{strip}{choice}</>;
    if (choice && views[kind] === "gecerlilik") {
      return <ValidityView key={`v:${at}`} kind={kind} filters={filters} lead={head} end={controls} compact reloadKey={shared.version} onChanged={shared.onChanged}
                           onGoToRecord={(id) => goTo(kind, id)} />;
    }
    return <EntryTable key={at} spec={ENTRIES[kind]} filters={filters} owner={owner} lead={head} end={controls} compact reloadKey={shared.version}
                       onChanged={shared.onChanged} focus={focus[kind]} />;
  };

  return (
    <MasterDetail id={`capacity-${level}`} onClose={() => setCard(null)} hideTitle
                  master={(
                    <>
                      <DataTable list={list} toolbarLead={lead} fitHeaders fieldHints={MASTER_HINTS} cellMenu={NO_ITEMS} rowMenu={menu.rowMenu} selectedRowId={row?.Id ?? null} onSelection={setPicked}
                                 rowProps={(r) => { seen.current.set(r.Id, String(r.Code ?? "")); return card ? { onClick: () => open(r) } : {}; }} />
                      {menu.element}
                    </>
                  )}
                  detail={card && row ? { title: many ? T.manyRecords(formatNumber(ids.length)) : withLocation(manyLocations, row.LocationCode, String(row.Code ?? "")), tabsLabel: T.cardTabs, tabs, tab: card.tab,
                                          onTab: (t) => setCard({ row, tab: t }), renderBody } : null} />
  );
}

/** Giriş sekmesi: bütün kayıtlar (grup ve kaynak ayrımıyla); kartında Geçmiş (çoklu seçimde seçili kayıtların hepsi, başta Kayıt kolonu).
 *  Geçerliliği olan girişte sekmelerin yanında tablo seçimi (Kayıtlar · Geçerlilik). */
function EntryTab({ kind, lead, shared, initial }: { kind: EntryKind; lead: ReactNode; shared: Shared; initial: TableView }) {
  const { scenario } = useShell();
  const spec = ENTRIES[kind];
  const [card, setCard] = useState<Row | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const { views, focus, setView, goTo } = useViews({ [kind]: initial });
  const view = views[kind] ?? "kayitlar";
  const ids = idsOf(card, picked);
  const renderBody = ({ tabs: strip, controls }: { tabs: ReactNode; controls: ReactNode }) => (card ? (
    // Geçmiş: satırın kendi anahtarı ve izleyen senaryodaki değişikliklerin senaryolu anahtarı (docs/08)
    <DataTable key={`g:${ids.join(",")}`} list={ids.length > 1 ? "record-history-many" : "record-history"} compact cellMenu={NO_ITEMS} fieldHints={HISTORY_HINTS}
               baseFilters={[{ field: "TableName", op: "in", values: [spec.table] },
                             { field: "RecordKey", op: "in", values: ids.flatMap((i) => [String(i), `${i}@${scenario?.id ?? 0}`]) }]}
               toolbarLead={strip} toolbarEnd={controls} reloadKey={shared.version} />
  ) : null);
  const head = VALIDITY[kind] ? <>{lead}<TableChoice value={view} onChange={(v) => setView(kind, v)} /></> : lead;
  if (VALIDITY[kind] && view === "gecerlilik") {
    return <ValidityView kind={kind} lead={head} reloadKey={shared.version} onChanged={shared.onChanged} onGoToRecord={(id) => goTo(kind, id)} />;
  }
  return (
    <MasterDetail id={`capacity-${kind}`} onClose={() => setCard(null)} hideTitle
                  master={<EntryTable spec={spec} lead={head} onDetail={setCard} selectedRowId={card?.Id ?? null} reloadKey={shared.version} onChanged={shared.onChanged}
                                      onSelection={setPicked} focus={focus[kind]} />}
                  detail={card ? { title: ids.length > 1 ? T.manyRecords(formatNumber(ids.length)) : spec.title, tabsLabel: T.cardTabs, tabs: HISTORY_TABS, tab: "gecmis" as CardTab,
                                   onTab: () => undefined, renderBody } : null} />
  );
}

export function CapacityManagement() {
  // Seçili sekme adreste (`?sekme=`). useSearchParams kullanılmaz: derlemeye dış adres içeren bir uyarı metni sokar (internetsizlik testi)
  const location = useLocation();
  const navigate = useNavigate();
  const query = new URLSearchParams(location.search);
  const wanted = query.get("sekme");
  const current: Tab = TABS.some((t) => t.value === wanted) ? wanted as Tab : "ozet";
  const lead = <OverflowTabs<Tab> label={T.sections} value={current} options={TABS}
                                  onChange={(v) => navigate({ pathname: location.pathname, search: v === "ozet" ? "" : `?sekme=${v}` }, { replace: true })} />;
  // Açılan sekmeler (K-188): bir kez açılan sekme ekrandan çıkılana kadar durur; yalnız seçili olan görünür. Adresteki `tablo=gecerlilik`
  // yalnız sekmenin ilk açılışındaki tablo seçimini belirler.
  const opened = useRef<{ tab: Tab; view: TableView }[]>([]);
  if (!opened.current.some((o) => o.tab === current)) opened.current.push({ tab: current, view: query.get("tablo") === "gecerlilik" ? "gecerlilik" : "kayitlar" });
  const [version, setVersion] = useState(0);
  const shared: Shared = useMemo(() => ({ version, onChanged: () => setVersion((n) => n + 1) }), [version]);
  const body = (value: Tab, initial: TableView) => {
    const entry = ENTRY_OF[value];
    if (value === "ozet") return <DataTable list="period-resource-group" toolbarLead={lead} reloadKey={version} />;
    if (entry) return <EntryTab kind={entry} lead={lead} shared={shared} initial={initial} />;
    return <OwnerTab level={value === "grup" ? "group" : "resource"} lead={lead} shared={shared} />;
  };
  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{T.title}</h1>
      </header>
      {TABS.filter((t) => opened.current.some((o) => o.tab === t.value)).map((t) => (
        <div key={t.value} className="sc-tab-keep" style={{ display: t.value === current ? "contents" : "none" }}>
          {body(t.value, opened.current.find((o) => o.tab === t.value)!.view)}
        </div>
      ))}
    </section>
  );
}
