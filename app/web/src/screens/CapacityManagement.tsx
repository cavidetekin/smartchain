// Kapasite yönetimi (ekran 30, fonksiyon 24; K-185, K-187; docs/12 "Kapasite yönetimi"). Sekmeler: Kapasite özeti (dönem tablosu, K-184; salt
// okunur, girişlerden hesaplanır) · Kaynak grubu · Kaynak (aktarılan veri; ⋯ › Detay kartı açar) · Çalışma düzeni · Bakım ve duruşlar · Verimlilik ·
// Fabrika takvimi · Ek mesai limitleri (giriş tabloları, 7.9b). Kartlar ana–detay düzenindedir; kart sekmeleri ortak tablodur. Çoklu seçimde kart
// seçili kayıtların hepsini gösterir (K-171). Ekran senaryoya bağlıdır: senaryo değişince baştan yüklenir. Geçerlilik görünümü 7.9c'de.
import { type ReactNode, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import { DataTable } from "../table/DataTable";
import { useRowMenu } from "../table/rowMenu";
import type { ListFilter, Row } from "../table/types";
import { type DetailTab, MasterDetail, OverflowTabs } from "../ui";
import { EntryTable } from "./CapacityEntries";
import { HISTORY_HINTS } from "./DataScreen";
import { ENTRIES, type EntryKind, type Owner } from "./capacityModel";

const T = tr.capacity;
const NO_ITEMS = () => [];
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

/** Kartın kayıtları: açılan kayıt; üst tabloda satır seçiliyse (Ctrl, Shift ya da seçim kutusu) seçili kayıtların hepsi (K-171). Tek satır
 *  Ctrl ile seçildiyse kart o kaydı gösterir (kart ilk açılan kayıtta kalmaz, K-187). */
const idsOf = (card: Row | null, picked: string[]): number[] => (!card ? [] : picked.length ? picked.map(Number) : [card.Id]);

/** Kaynak grubu ve Kaynak sekmeleri: aktarılan veri (salt okunur); ⋯ › Detay alttaki kartı açar. */
function OwnerTab({ level, lead }: { level: "group" | "resource"; lead: ReactNode }) {
  const list = level === "group" ? "capacity-resource-groups" : "capacity-resources";
  const [card, setCard] = useState<{ row: Row; tab: CardTab } | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const seen = useRef(new Map<number, string>());   // çizilen satırların kodu (dönem özeti kodla süzülür; seçili satırlar tıklandığı için çizilmiştir)
  const [tick, setTick] = useState(0);
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
      return <DataTable key={at} list="period-resource-group" compact cellMenu={NO_ITEMS} toolbarLead={strip} toolbarEnd={controls} reloadKey={tick}
                        baseFilters={[{ field: "ResourceGroupCode", op: "in", values: groupCodes.length ? groupCodes : ["—"] }]} />;
    }
    if (card.tab === "kaynaklar") {
      return <DataTable key={at} list="capacity-resources" baseFilters={memberFilters} compact cellMenu={NO_ITEMS} toolbarLead={strip} toolbarEnd={controls} />;
    }
    if (card.tab === "gecmis") return null;
    return <EntryTable key={at} spec={ENTRIES[card.tab]} filters={filters} owner={owner} lead={strip} end={controls} compact onChanged={() => setTick((n) => n + 1)} />;
  };

  return (
    <MasterDetail id={`capacity-${level}`} onClose={() => setCard(null)} hideTitle
                  master={(
                    <>
                      <DataTable list={list} toolbarLead={lead} fitHeaders cellMenu={NO_ITEMS} rowMenu={menu.rowMenu} selectedRowId={row?.Id ?? null} onSelection={setPicked}
                                 rowProps={(r) => { seen.current.set(r.Id, String(r.Code ?? "")); return card ? { onClick: () => open(r) } : {}; }} />
                      {menu.element}
                    </>
                  )}
                  detail={card && row ? { title: many ? T.manyRecords(formatNumber(ids.length)) : String(row.Code ?? ""), tabsLabel: T.cardTabs, tabs, tab: card.tab,
                                          onTab: (t) => setCard({ row, tab: t }), renderBody } : null} />
  );
}

/** Giriş sekmesi: bütün kayıtlar (grup ve kaynak ayrımıyla); kartında Geçmiş (çoklu seçimde seçili kayıtların hepsi, başta Kayıt kolonu). */
function EntryTab({ kind, lead }: { kind: EntryKind; lead: ReactNode }) {
  const { scenario } = useShell();
  const spec = ENTRIES[kind];
  const [card, setCard] = useState<Row | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [tick, setTick] = useState(0);
  const ids = idsOf(card, picked);
  const renderBody = ({ tabs: strip, controls }: { tabs: ReactNode; controls: ReactNode }) => (card ? (
    // Geçmiş: satırın kendi anahtarı ve izleyen senaryodaki değişikliklerin senaryolu anahtarı (docs/08)
    <DataTable key={`g:${ids.join(",")}`} list={ids.length > 1 ? "record-history-many" : "record-history"} compact cellMenu={NO_ITEMS} fieldHints={HISTORY_HINTS}
               baseFilters={[{ field: "TableName", op: "in", values: [spec.table] },
                             { field: "RecordKey", op: "in", values: ids.flatMap((i) => [String(i), `${i}@${scenario?.id ?? 0}`]) }]}
               toolbarLead={strip} toolbarEnd={controls} reloadKey={tick} />
  ) : null);
  return (
    <MasterDetail id={`capacity-${kind}`} onClose={() => setCard(null)} hideTitle
                  master={<EntryTable spec={spec} lead={lead} onDetail={setCard} selectedRowId={card?.Id ?? null} onChanged={() => setTick((n) => n + 1)} onSelection={setPicked} />}
                  detail={card ? { title: ids.length > 1 ? T.manyRecords(formatNumber(ids.length)) : spec.title, tabsLabel: T.cardTabs, tabs: HISTORY_TABS, tab: "gecmis" as CardTab,
                                   onTab: () => undefined, renderBody } : null} />
  );
}

export function CapacityManagement() {
  // Seçili sekme adreste (`?sekme=`). useSearchParams kullanılmaz: derlemeye dış adres içeren bir uyarı metni sokar (internetsizlik testi)
  const location = useLocation();
  const navigate = useNavigate();
  const wanted = new URLSearchParams(location.search).get("sekme");
  const current: Tab = TABS.some((t) => t.value === wanted) ? wanted as Tab : "ozet";
  const lead = <OverflowTabs<Tab> label={T.sections} value={current} options={TABS}
                                  onChange={(v) => navigate({ pathname: location.pathname, search: v === "ozet" ? "" : `?sekme=${v}` }, { replace: true })} />;
  const entry = ENTRY_OF[current];
  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{T.title}</h1>
      </header>
      {current === "ozet" && <DataTable list="period-resource-group" toolbarLead={lead} />}
      {(current === "grup" || current === "kaynak") && <OwnerTab key={current} level={current === "grup" ? "group" : "resource"} lead={lead} />}
      {entry && <EntryTab key={entry} kind={entry} lead={lead} />}
    </section>
  );
}
