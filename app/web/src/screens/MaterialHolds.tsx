// Model kısıtları › Malzeme blokajı (ekran 31 üçüncü sekme, fonksiyon 99; K-193; docs/12 "Model kısıtları"): malzeme için belli tarihlerde yeni
// tedarik planı (üretim, satın alma ya da ikisi) çıkarılmaz. Kapasite yönetimi'nin giriş bileşenleriyle kurulur (aynı tablo, menü, tablo içi
// düzenleme, senaryo farkı işaretleri, Geçerlilik zaman çubuğu); sahip (lokasyon ve malzeme) burada tanımlanır (`EntryAdapter`, `ValidityCustom`).
// Pencere 7.9b standardıyla: malzeme aramalı seçim, tür parçalı seçim (malzemenin tedarik biçimine uymayan seçenek pasif), tür ve oran boş açılır,
// zorunlu alan boşken Kaydet pasif. Geçerlilik dönem bazındadır: tablo satırı malzeme × tedarik biçimi × plan dönemi; zaman çubuğunda dönemin iki
// satırı tek dilimde birleşir, renk kapalı olan tedarik biçimine göredir (Üretim amber, Satın alma nane, ikisi mercan; açık kalan dönem çerçeveli).
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { ApiError, emitNotice, getJson, sendJson } from "../api/client";
import { formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import { DataTable } from "../table/DataTable";
import type { Row } from "../table/types";
import { Alert, DateField, type DetailTab, Dialog, MasterDetail, NumberField, SearchSelect, Segment, TextField } from "../ui";
import { EntryTable } from "./CapacityEntries";
import { type SpanInfo, TableChoice, type TableView, type ValidityCustom, ValidityView } from "./CapacityValidity";
import { type EntryDialogProps, type EntrySpec, isoDate, type Owner, parseIso, type Saved } from "./capacityModel";
import { HISTORY_HINTS } from "./DataScreen";

const T = tr.modelConstraints.hold;
const C = tr.capacity;
const NO_ITEMS = () => [];
export const PRODUCTION = "Üretim", PURCHASE = "Satın alma", BOTH = "Üretim ve satın alma", CLOSED = "Kapalı";
export const TYPES = [PRODUCTION, PURCHASE, BOTH] as const;
const TABLE = "MaterialHold";
const BASE = "/api/model-constraints/material-holds";
const url = (scenario: number, tail = "") => `${BASE}${tail}?scenario_id=${scenario}`;
const HISTORY_TABS: DetailTab<"gecmis">[] = [{ value: "gecmis", label: tr.modelConstraints.history, count: 1 }];
const trDate = (iso: string) => { const [y, m, d] = iso.slice(0, 10).split("-"); return `${d}.${m}.${y}`; };
/** Yüzde yazımı: "%50", "%53,3" (gereksiz ondalık yazılmaz). */
const percent = (v: unknown, decimals = 1) => { const n = Number(v); return `%${formatNumber(n, Number.isInteger(n) ? 0 : decimals)}`; };
const ownerOf = (row: Row): Owner => ({ level: "material", id: Number(row.MaterialId), code: String(row.MaterialCode ?? ""), locationId: Number(row.LocationId) });

const api = {
  create: (scenario: number, values: Record<string, unknown>) => sendJson<Saved & { id: number }>("POST", url(scenario), { values }),
  change: (scenario: number, changes: { id: number; field: string; value: unknown }[]) => sendJson<Saved & { saved: number }>("PUT", url(scenario), { changes }),
  remove: (scenario: number, id: number) => sendJson<unknown>("DELETE", url(scenario, `/${id}`)),
  invalidate: (scenario: number, id: number) => sendJson<unknown>("POST", url(scenario, `/${id}/invalidate`)),
  validate: (scenario: number, id: number) => sendJson<unknown>("POST", url(scenario, `/${id}/validate`)),
  restore: (scenario: number, id: number) => sendJson<unknown>("POST", url(scenario, `/${id}/restore`)),
};

interface MaterialOption { location_id: number; location: string; material_id: number; code: string; name: string | null; producible: boolean | null; purchasable: boolean | null }
const materialKey = (o: { location_id: number; material_id: number }) => `${o.location_id}|${o.material_id}`;
/** Tür malzemenin tedarik biçimine uyar mı (K-193): yalnız açıkça "Hayır" olan uymaz; boş (bilinmiyor) uyar. */
export const typeFits = (type: string, m: { producible: boolean | null; purchasable: boolean | null } | undefined) =>
  !m || !((type !== PURCHASE && m.producible === false) || (type !== PRODUCTION && m.purchasable === false));

/** "Yeni kayıt" ve "Düzenle" penceresi. Düzenlemede malzeme değişmez. Tür ve oran boş açılır (K-138). */
export function MaterialHoldDialog({ spec, scenario, row, owner, onClose, onSaved }: EntryDialogProps) {
  const editing = row !== null;
  const [material, setMaterial] = useState(owner?.level === "material" && owner.locationId != null ? `${owner.locationId}|${owner.id}` : "");
  const [type, setType] = useState<string>(editing ? String(row.HoldType ?? "") : "");
  const [from, setFrom] = useState<Date | null>(editing ? parseIso(row.StartDate) : null);
  const [to, setTo] = useState<Date | null>(editing ? parseIso(row.EndDate) : null);
  const [pct, setPct] = useState<number | null>(editing && typeof row.ClosePct === "number" ? row.ClosePct : null);
  const [reason, setReason] = useState(editing ? String(row.Reason ?? "") : "");
  const [options, setOptions] = useState<MaterialOption[] | null>(null);
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {   // güncel malzemeler, tedarik biçimiyle (düzenlemede de: türün uygunluğu için)
    const ctrl = new AbortController();
    getJson<{ materials: MaterialOption[] }>(`${BASE}/options`, ctrl.signal).then((d) => setOptions(d.materials))
      .catch(() => { if (!ctrl.signal.aborted) { setOptions([]); setError(C.failed); } });
    return () => ctrl.abort();
  }, []);

  const manyLocations = new Set((options ?? []).map((o) => o.location)).size > 1;   // birden çok lokasyonda seçenek "lokasyon · kod · ad" (K-189)
  const picked = editing ? (options ?? []).find((o) => o.material_id === row.MaterialId) : (options ?? []).find((o) => materialKey(o) === material);
  const missing = (!editing && !material) || !type || !from || pct === null;
  const pickMaterial = (value: string) => {
    setMaterial(value);
    const next = (options ?? []).find((o) => materialKey(o) === value);
    if (type && !typeFits(type, next)) setType("");   // seçili tür yeni malzemeye uymuyorsa boşalır
  };

  const submit = async () => {
    setBusy(true);
    setProblems({});
    setError(null);
    try {
      let warnings: string[] | undefined;
      const values: Record<string, unknown> = { HoldType: type, StartDate: from ? isoDate(from) : null, EndDate: to ? isoDate(to) : null, ClosePct: pct, Reason: reason.trim() || null };
      if (editing) {
        const before: Record<string, unknown> = { HoldType: row.HoldType ?? null, StartDate: row.StartDate ?? null, EndDate: row.EndDate ?? null, ClosePct: row.ClosePct ?? null,
                                                  Reason: row.Reason ?? null };
        const changes = Object.entries(values).filter(([name, value]) => JSON.stringify(value) !== JSON.stringify(before[name])).map(([field, value]) => ({ id: row.Id, field, value }));
        if (changes.length) warnings = (await api.change(scenario, changes)).warnings;
      } else {
        const [location, materialId] = material.split("|").map(Number);
        warnings = (await api.create(scenario, { LocationId: location, MaterialId: materialId, ...values })).warnings;
      }
      for (const w of warnings ?? []) emitNotice(w);
      onSaved();
    } catch (e) {
      if (e instanceof ApiError && e.details.length) setProblems(Object.fromEntries(e.details.map((d) => [d.field, d.problem])));
      else setError(e instanceof ApiError ? e.message : C.failed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog title={editing ? C.editTitle(spec.title) : C.newTitle(spec.title)} onClose={onClose} onSubmit={() => void submit()} submitLabel={tr.table.editSave} busy={busy}
            submitDisabled={Boolean(missing)} className="sc-dialog--form">
      <div className="sc-form-grid">
        <div className="sc-form-full">
          {editing ? <TextField label={T.material} value={String(row.MaterialCode ?? "")} onChange={() => undefined} disabled />
            : <SearchSelect label={T.material} value={material} onChange={pickMaterial} error={problems.MaterialId} emptyText={C.noMatch}
                            options={(options ?? []).map((o) => ({ value: materialKey(o), code: manyLocations ? `${o.location} · ${o.code}` : o.code, name: o.name ?? undefined }))} />}
        </div>
        <div className="sc-form-full">
          <Segment<string> label={T.type} value={type} onChange={setType} options={TYPES.map((t) => ({ value: t, label: t, disabled: !typeFits(t, picked) }))} />
          {problems.HoldType && <p className="sc-field-error">{problems.HoldType}</p>}
        </div>
        <DateField label={C.start} error={problems.StartDate} value={from} onChange={setFrom} />
        <DateField label={C.end} error={problems.EndDate} value={to} onChange={setTo} />
        <div className="sc-form-full">
          <NumberField label={T.pct} error={problems.ClosePct} live decimals={2} value={pct} onChange={setPct} />
        </div>
        <div className="sc-form-full"><TextField label={T.reason} error={problems.Reason} value={reason} onChange={setReason} /></div>
      </div>
      {error && <Alert tone="error">{error}</Alert>}
    </Dialog>
  );
}

export const MATERIAL_HOLDS: EntrySpec = {
  kind: "material-holds", list: "material-holds", table: TABLE, title: T.title, owner: true, start: "StartDate",
  fields: [{ name: "HoldType", label: T.type, kind: "choice", required: true, options: TYPES }, { name: "StartDate", label: C.start, kind: "date", required: true },
           { name: "EndDate", label: C.end, kind: "date" }, { name: "ClosePct", label: T.pct, kind: "number", required: true, decimals: 2 },
           { name: "Reason", label: T.reason, kind: "text" }],
  adapter: {
    api, writeFunction: 99, Dialog: MaterialHoldDialog,
    label: (row, shown) => `${String(row.MaterialCode ?? "")} · ${shown("StartDate", row)}`,
    ownerOf,
    hints: { MaterialCode: { width: 7.5 }, MaterialName: { width: 16 }, HoldType: { width: 11 }, ClosePct: { width: 15 }, Reason: { width: 13 }, Origin: { width: 8.6 },
             IsValid: { width: 5.6 } },
  },
};

const PARTS = "_parts";
const partsOf = (row: Row): Row[] => (Array.isArray(row[PARTS]) ? row[PARTS] as Row[] : [row]);
/** Zaman çubuğu için dönemin satırlarını (Üretim, Satın alma) tek satırda birleştirir: her dilim bir malzemenin bir plan dönemidir. */
export function mergePeriods(rows: Row[]): Row[] {
  const out = new Map<string, Row>();
  for (const row of rows) {
    const key = `${String(row.LocationId)}|${String(row.MaterialId)}|${String(row.PeriodStart)}`;
    const found = out.get(key);
    if (found) (found[PARTS] as Row[]).push(row);
    else out.set(key, { ...row, ValidFrom: row.PeriodStart, ValidTo: row.PeriodEnd, [PARTS]: [row] });
  }
  return [...out.values()];
}
/** Dilimin tonu: kapalı olan tedarik biçimi (Üretim amber, Satın alma nane, ikisi mercan); hiçbiri kapalı değilse blokajlı olanlar, çerçeveli. */
export function describePeriod(row: Row): SpanInfo {
  const parts = partsOf(row);
  const closed = parts.filter((p) => p.Status === CLOSED);
  const shown = closed.length ? closed : parts;
  const supplies = new Set(shown.map((p) => String(p.Supply)));
  const tone = supplies.size > 1 ? "both" : supplies.has(PRODUCTION) ? "own" : "group";
  const code = String(row.MaterialCode ?? "");
  const top = Math.max(...shown.map((p) => Number(p.Ratio)));
  return {
    key: `${String(row.LocationId)}|${String(row.MaterialId)}`, code, title: code, own: tone === "own", tone, outline: closed.length === 0, text: percent(top),
    lines: [code, `${String(row.Period ?? "")} (${trDate(String(row.PeriodStart))} – ${trDate(String(row.PeriodEnd))})`,
            ...parts.map((p) => `${String(p.Supply)}: ${T.days(formatNumber(Number(p.BlockedDays)), formatNumber(Number(p.PeriodDays)))} · ${percent(p.Ratio)} · ${T.threshold} ${percent(p.Threshold, 2)} · ${String(p.Status)}`)],
  };
}

/** Geçerlilik (dönem bazında): her satır bir malzeme, her dilim blokajlı günü olan bir plan dönemi. */
export const HOLD_VALIDITY: ValidityCustom = {
  list: "material-holds-validity", entry: MATERIAL_HOLDS, corner: T.corner, labelRem: 9,
  hints: { LocationCode: { width: 6.5 }, MaterialCode: { width: 7.5 }, Supply: { width: 7.5 }, Period: { width: 7 }, PeriodStart: { width: 7.6 }, PeriodEnd: { width: 7.6 },
           BlockedDays: { width: 8 }, Ratio: { width: 6.5 }, Threshold: { width: 6.5 }, Status: { width: 6 } },
  merge: mergePeriods,
  describe: describePeriod,
  ownerKey: (row) => `,m${String(row.MaterialId)},`,
  newOwner: ownerOf,
  label: (row) => String(row.MaterialCode ?? ""),
};

/** "Malzeme blokajı" sekmesi: tablo seçimi Kayıtlar · Geçerlilik; Kayıtlar'da Detay kartında Geçmiş. */
export function MaterialHoldsTab({ lead }: { lead: ReactNode }) {
  const { scenario } = useShell();
  const [view, setView] = useState<TableView>("kayitlar");
  const [card, setCard] = useState<Row | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [focus, setFocus] = useState<{ id: number; n: number } | undefined>(undefined);
  const [version, setVersion] = useState(0);
  const head = useMemo(() => <>{lead}<TableChoice value={view} onChange={setView} /></>, [lead, view]);
  const onChanged = () => setVersion((n) => n + 1);
  if (view === "gecerlilik") {
    return <ValidityView custom={HOLD_VALIDITY} lead={head} reloadKey={version} onChanged={onChanged}
                         onGoToRecord={(id) => { setFocus((cur) => ({ id, n: (cur?.n ?? 0) + 1 })); setView("kayitlar"); }} />;
  }
  const ids = !card ? [] : picked.length ? picked.map(Number) : [card.Id];
  const renderBody = ({ tabs: strip, controls }: { tabs: ReactNode; controls: ReactNode }) => (card ? (
    // Geçmiş: satırın kendi anahtarı ve izleyen senaryodaki değişikliklerin senaryolu anahtarı (docs/08)
    <DataTable key={`g:${ids.join(",")}`} list={ids.length > 1 ? "record-history-many" : "record-history"} compact cellMenu={NO_ITEMS} fieldHints={HISTORY_HINTS}
               baseFilters={[{ field: "TableName", op: "in", values: [TABLE] }, { field: "RecordKey", op: "in", values: ids.flatMap((i) => [String(i), `${i}@${scenario?.id ?? 0}`]) }]}
               toolbarLead={strip} toolbarEnd={controls} reloadKey={version} />
  ) : null);
  return (
    <MasterDetail id="model-constraints-holds" onClose={() => setCard(null)} hideTitle
                  master={<EntryTable spec={MATERIAL_HOLDS} lead={head} onDetail={setCard} selectedRowId={card?.Id ?? null} reloadKey={version} onChanged={onChanged}
                                      onSelection={setPicked} focus={focus} />}
                  detail={card ? { title: ids.length > 1 ? C.manyRecords(formatNumber(ids.length)) : String(card.MaterialCode ?? ""), tabsLabel: tr.modelConstraints.cardTabs,
                                   tabs: HISTORY_TABS, tab: "gecmis" as const, onTab: () => undefined, renderBody } : null} />
  );
}
