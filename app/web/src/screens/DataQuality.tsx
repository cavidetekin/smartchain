// Veri kalitesi (ekran 05; fonksiyon 20, 21; K-174): yüklenmiş verideki takipli kural ve Smartchain kontrolü uyarıları. Tek şerit: solda sekmeler
// Yüksek · Normal · Yok sayılan, sağda tablo kontrolleri; kart ve panel yok. Satır menüsü: Detay · Kayda git · Kural oluştur · Yok say (Yok sayılan
// sekmesinde "Yok saymayı kaldır"); çoklu seçimde "Seçili n satır" grubunda Yok say. Detay kartı: Kayıt · Talep zinciri (yalnız Yüksek).
import { type HTMLAttributes, useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { ApiError, emitNotice, JOB_QUALITY, postJson } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can, forbiddenReason } from "../auth/permissions";
import { tr } from "../i18n/tr";
import { useJobRefresh } from "../shell/useJobRefresh";
import { DataTable, type FieldHints, type RowMenuSpec, type Selection } from "../table/DataTable";
import { listApi, type ListFilter, type Row } from "../table/types";
import { Alert, Badge, type BadgeTone, Dialog, MasterDetail, OverflowTabs, TextareaField } from "../ui";
import { type MenuAction, MenuActions, MenuItem, RowPopMenu } from "../ui/PopMenu";
import { onlyRecordUrl } from "./dataScreenTabs";

const T = tr.dataQuality;
const NEW = "Yeni";
const OPEN = "Açık";
const IGNORED = "Yok sayıldı";
const CARD_MAX = 100;  // çoklu seçimde kart en çok bu kadar uyarıyı birlikte gösterir
const QUALITY_JOBS = [JOB_QUALITY];

type Tab = "yuksek" | "normal" | "yok-sayilan";
// Yok sayılan sekmesi ayrı liste: Standart görünümünde Gerekçe açık, görünümleri sekmeye özgü (K-174)
const WARNINGS_LIST = "data-quality-warnings";
const IGNORED_LIST = "data-quality-ignored";
const TABS: { value: Tab; label: string }[] = [
  { value: "yuksek", label: T.tabs.high }, { value: "normal", label: T.tabs.normal }, { value: "yok-sayilan", label: T.tabs.ignored },
];
const FILTERS: Record<Tab, ListFilter[]> = {
  yuksek: [{ field: "Importance", op: "in", values: ["Yüksek"] }, { field: "State", op: "in", values: [NEW, OPEN] }],
  normal: [{ field: "Importance", op: "in", values: ["Normal"] }, { field: "State", op: "in", values: [NEW, OPEN] }],
  "yok-sayilan": [{ field: "State", op: "in", values: [IGNORED] }],
};
const STATE_TONE: Record<string, BadgeTone> = { [NEW]: "info", [OPEN]: "neutral", [IGNORED]: "muted" };
const HINTS: FieldHints = { State: { width: 7 }, EntityLabel: { width: 11 }, RecordLabel: { width: 13 }, RuleName: { width: 18 }, Message: { width: 22 },
                            FirstSeenAt: { width: 8 }, IgnoreReason: { width: 18 } };
const CHAIN_HINTS: FieldHints = { DemandLabel: { width: 11 }, DemandType: { width: 9 }, MaterialPath: { width: 26 }, DemandDate: { width: 8 }, OpenQuantity: { width: 8 } };

type CardTab = "kayit" | "talep-zinciri";
interface Card { id: string; tab: CardTab }
interface Warning { Id: number; EntityName: string; RecordKey: string; TargetList: string | null }

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : T.failed);
const asWarning = (r: Row): Warning => ({ Id: Number(r.Id), EntityName: String(r.EntityName), RecordKey: String(r.RecordKey), TargetList: r.TargetList ? String(r.TargetList) : null });

function IgnoreDialog({ ids, onClose, onDone }: { ids: string[]; onClose(): void; onDone(): void }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await postJson("/api/data-quality/ignore", { ids, reason: reason.trim() });
      emitNotice(T.ignored(ids.length));
      onDone();
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };
  return (
    <Dialog title={T.ignoreTitle(ids.length)} onClose={onClose} onSubmit={() => void save()} submitLabel={tr.table.editSave} busy={busy}
            submitDisabled={!reason.trim()}>
      {error && <Alert tone="error">{error}</Alert>}
      <TextareaField label={T.reason} required value={reason} onChange={setReason} maxLength={400} rows={3} />
    </Dialog>
  );
}

/** Detay kartı: Kayıt (kaydın kendi listesi o kayıtla süzülmüş) · Talep zinciri (yalnız Yüksek sekmesinde). */
function CardBody({ warnings, tab, tabs, controls, reloadKey }: {
  warnings: Warning[]; tab: CardTab; tabs: React.ReactNode; controls: React.ReactNode; reloadKey: number;
}) {
  const ids = warnings.map((w) => String(w.Id));
  const idsKey = ids.join(",");
  const [chain, setChain] = useState<{ key: string; truncated: boolean; error: string | null } | null>(null);
  useEffect(() => {
    if (tab !== "talep-zinciri" || !ids.length) return undefined;
    let alive = true;
    void (async () => {
      let truncated = false;
      try {
        for (const id of ids) {
          const r = await postJson<{ count: number; truncated: boolean }>(`/api/data-quality/${id}/demand-chain`, {});
          truncated ||= r.truncated;
        }
        if (alive) setChain({ key: idsKey, truncated, error: null });
      } catch (e) {
        if (alive) setChain({ key: idsKey, truncated: false, error: errorText(e) });
      }
    })();
    return () => { alive = false; };
  }, [tab, idsKey, reloadKey]);  // eslint-disable-line react-hooks/exhaustive-deps

  const bare = (content: React.ReactNode) => (
    <>
      <div className="sc-table-toolbar sc-table-toolbar--compact">
        <div className="sc-table-toolbar-main">{tabs}</div>
        <div className="sc-table-tools">{controls}</div>
      </div>
      {content}
    </>
  );
  if (tab === "talep-zinciri") {
    const ready = chain && chain.key === idsKey;
    if (!ready) return bare(<p className="sc-muted">{T.loading}</p>);
    if (chain.error) return bare(<Alert tone="error">{chain.error}</Alert>);
    return (
      <div className="sc-card-body">
        {chain.truncated && <Alert tone="info">{T.pathLimit}</Alert>}
        <DataTable key={`c:${idsKey}:${reloadKey}`} list="data-quality-demand-chain" baseFilters={[{ field: "WarningId", op: "in", values: ids }]}
                   fieldHints={CHAIN_HINTS} compact toolbarLead={tabs} toolbarEnd={controls} />
      </div>
    );
  }
  const lists = new Set(warnings.map((w) => w.TargetList));
  const target = warnings[0]?.TargetList;
  if (lists.size > 1) return bare(<p className="sc-muted">{T.mixedTables}</p>);
  if (!target) return bare(<p className="sc-muted">{T.noRecordList}</p>);
  return (
    <div className="sc-card-body">
      <DataTable key={`k:${target}:${idsKey}`} list={target} baseFilters={[{ field: "Id", op: "in", values: warnings.map((w) => w.RecordKey) }]}
                 compact toolbarLead={tabs} toolbarEnd={controls} />
    </div>
  );
}

export function DataQuality() {
  const me = useAuth().me!;
  const navigate = useNavigate();
  const { search, pathname } = useLocation();
  const params = new URLSearchParams(search);
  const tab: Tab = TABS.find((t) => t.value === params.get("sekme"))?.value ?? "yuksek";
  const ignoredTab = tab === "yok-sayilan";
  const canAct = can(me, 21, "write");
  const actReason = canAct ? null : forbiddenReason(21, "write");
  const canRules = can(me, 16, "write");
  const [reloadKey, setReloadKey] = useState(0);
  const [menu, setMenu] = useState<{ row: Row; anchor: HTMLElement; extra?: MenuAction[] } | null>(null);
  const [ignoring, setIgnoring] = useState<string[] | null>(null);
  const [card, setCard] = useState<Card | null>(null);
  const [cardRows, setCardRows] = useState<Warning[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const refresh = useCallback(() => setReloadKey((k) => k + 1), []);
  useJobRefresh(QUALITY_JOBS, refresh);  // kontrol bitince liste tazelenir

  const choose = (next: Tab) => {
    setCard(null);
    navigate(`${pathname}?${new URLSearchParams({ sekme: next }).toString()}`, { replace: true });
  };

  // Kartın uyarıları: tek uyarı ya da (kart açıkken) çoklu seçim
  const cardIds = card ? (picked.length > 1 ? picked.slice(0, CARD_MAX) : [card.id]) : [];
  const cardKey = cardIds.join(",");
  useEffect(() => {
    if (!cardIds.length) {
      setCardRows([]);
      return undefined;
    }
    const ctrl = new AbortController();
    listApi("data-quality-warnings").query({ fields: ["State"], sort: [], filters: [{ field: "Id", op: "in", values: cardIds }], offset: 0, limit: CARD_MAX }, ctrl.signal)
      .then((r) => setCardRows(r.rows.map(asWarning))).catch(() => undefined);
    return () => ctrl.abort();
  }, [cardKey, reloadKey]);  // eslint-disable-line react-hooks/exhaustive-deps

  const unignore = async (ids: string[]) => {
    try {
      await postJson("/api/data-quality/unignore", { ids });
      emitNotice(T.unignored(ids.length));
      refresh();
    } catch (e) {
      emitNotice(errorText(e));
    }
  };
  const openCard = (row: Row) => setCard((c) => ({ id: String(row.Id), tab: c?.tab === "talep-zinciri" && !ignoredTab && tab === "yuksek" ? "talep-zinciri" : "kayit" }));
  const goRecord = (row: Row) => {
    const url = row.TargetList ? onlyRecordUrl(String(row.TargetList), String(row.RecordKey)) : null;
    if (url) navigate(url);
  };
  const createRule = (row: Row) => navigate(`/veri/veri-kurallari?${new URLSearchParams({ tablo: String(row.EntityName), alan: String(row.FixField), yeni: "1" }).toString()}`);
  const ruleState = (row: Row) => (!canRules ? { allowed: false, reason: forbiddenReason(16, "write") }
    : row.FixField ? { allowed: true } : { allowed: false, reason: T.noFixField });
  const actState = actReason ? { allowed: false, reason: actReason } : { allowed: true };

  const rowMenu: RowMenuSpec = useMemo(() => ({
    label: (row: Row) => T.rowMenu(String(row.RecordLabel)),
    onOpen: (row: Row, anchor: HTMLElement, extra?: MenuAction[]) => setMenu({ row, anchor, extra }),
  }), []);
  const selectionMenu = useCallback((sel: Selection): MenuAction[] => [
    ignoredTab ? { label: T.unignore, state: actState, onClick: () => void unignore(sel.ids) } : { label: T.ignore, state: actState, onClick: () => setIgnoring(sel.ids) },
  ], [ignoredTab, actReason]);  // eslint-disable-line react-hooks/exhaustive-deps
  const cellRender = useMemo(() => ({
    State: (value: unknown) => (value ? <Badge tone={STATE_TONE[String(value)] ?? "neutral"}>{String(value)}</Badge> : null),
  }), []);
  const rowProps = useCallback((row: Row): HTMLAttributes<HTMLTableRowElement> => (card ? { onClick: () => openCard(row) } : {}), [card, tab]);  // eslint-disable-line react-hooks/exhaustive-deps

  const cardTabs = [{ value: "kayit" as CardTab, label: T.cardRecord, count: 1 },
                    ...(tab === "yuksek" ? [{ value: "talep-zinciri" as CardTab, label: T.cardChain, count: 1 }] : [])];
  const cardTab: CardTab = card && cardTabs.some((t) => t.value === card.tab) ? card.tab : "kayit";
  const title = picked.length > 1 && card ? T.manyWarnings(Math.min(picked.length, CARD_MAX)) : T.cardTitle;

  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{T.title}</h1>
      </header>
      {card && picked.length > CARD_MAX && <Alert tone="info">{T.cardMax(CARD_MAX)}</Alert>}
      <MasterDetail<CardTab>
        id="data-quality-card"
        master={(
          <DataTable key={tab} list={ignoredTab ? IGNORED_LIST : WARNINGS_LIST} baseFilters={FILTERS[tab]} fieldHints={HINTS} cellRender={cellRender} reloadKey={reloadKey}
                     rowMenu={rowMenu} rowProps={rowProps} selectionMenu={selectionMenu} onSelection={setPicked}
                     selectedRowId={card ? Number(card.id) : undefined}
                     toolbarLead={<OverflowTabs<Tab> label={T.tabsLabel} value={tab} onChange={choose} options={TABS} />} />
        )}
        onClose={() => setCard(null)} hideTitle
        detail={card ? {
          title, tabsLabel: T.cardTabs, tabs: cardTabs, tab: cardTab, onTab: (t) => setCard({ ...card, tab: t }),
          renderBody: ({ tabs, controls }) => <CardBody warnings={cardRows} tab={cardTab} tabs={tabs} controls={controls} reloadKey={reloadKey} />,
        } : null} />
      {menu && (
        <RowPopMenu label={T.rowMenu(String(menu.row.RecordLabel))} anchor={menu.anchor} onClose={() => setMenu(null)}>
          <MenuActions items={menu.extra} onDone={() => setMenu(null)} />
          <MenuItem label={tr.table.detailItem} state={{ allowed: true }} onClick={() => { openCard(menu.row); setMenu(null); }} />
          <MenuItem label={T.goRecord} state={menu.row.TargetList ? { allowed: true } : { allowed: false, reason: T.noRecordList }}
                    onClick={() => { goRecord(menu.row); setMenu(null); }} />
          <MenuItem label={T.createRule} state={ruleState(menu.row)} onClick={() => { createRule(menu.row); setMenu(null); }} />
          {ignoredTab
            ? <MenuItem label={T.unignore} state={actState} onClick={() => { void unignore([String(menu.row.Id)]); setMenu(null); }} />
            : <MenuItem label={T.ignore} state={actState} onClick={() => { setIgnoring([String(menu.row.Id)]); setMenu(null); }} />}
        </RowPopMenu>
      )}
      {ignoring && <IgnoreDialog ids={ignoring} onClose={() => setIgnoring(null)} onDone={() => { setIgnoring(null); refresh(); }} />}
    </section>
  );
}
