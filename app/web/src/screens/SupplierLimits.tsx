// Model kısıtları › Tedarikçi limiti (ekran 31 ikinci sekme, fonksiyon 103; K-191; docs/12 "Model kısıtları"): satın alınan malzemede tedarikçi üst
// limiti ve tedarikçi kapanışı. Kapasite yönetimi'nin giriş bileşenleriyle kurulur (aynı tablo, menü, tablo içi düzenleme, senaryo farkı işaretleri,
// Geçerlilik zaman çubuğu): sahip tanımı burada verilir (`EntryAdapter`, `ValidityCustom`). İki kayıt türü aynı listededir (Tür kolonu); türe
// uymayan hücre boştur ve düzenlenmez. Pencere 7.9b standardıyla: tür parçalı seçim, tedarikçi ve malzeme aramalı seçim (malzeme listesi yalnız
// seçili tedarikçinin malzemeleri; kapanışta birden çok malzeme seçilir, boş bırakılırsa bütün malzemeler), zorunlu alan boşken Kaydet pasif.
// Pencere "Üst limit" seçili açılır; Sebep iki türde de vardır (isteğe bağlı) ve tabloda iki türde de düzenlenir (K-191 demo).
// Alan sırası Lokasyon · Tür · Tedarikçi · Malzeme (K-194): tedarikçi listesi seçili lokasyona süzülür; Düzenle'de dördü de kilitli.
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { ApiError, emitNotice, getJson, sendJson } from "../api/client";
import { formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import { DataTable } from "../table/DataTable";
import type { Row } from "../table/types";
import { Alert, DateField, type DetailTab, Dialog, MasterDetail, NumberField, SearchSelect, Segment, TextField } from "../ui";
import { EntryTable } from "./CapacityEntries";
import { TableChoice, type TableView, type ValidityCustom, ValidityView } from "./CapacityValidity";
import { type EntryDialogProps, type EntrySpec, isoDate, type Owner, parseIso, type Saved } from "./capacityModel";
import { HISTORY_HINTS } from "./DataScreen";
import { emptyTextOf, LocationField, locationsOf, useLocationChoice, useLocations, useManyLocations, withLocation } from "./locationField";

const T = tr.modelConstraints.supplier;
const C = tr.capacity;
const NO_ITEMS = () => [];
export const UPPER = "Üst limit", CLOSURE = "Kapanış", CLOSED = "Kapalı";
export const PERIODS = ["Gün", "Hafta", "Ay", "Çeyrek", "Yıl"] as const;
const TABLE = "SupplierLimit";
const BASE = "/api/model-constraints/supplier-limits";
const url = (scenario: number, tail = "") => `${BASE}${tail}?scenario_id=${scenario}`;
const HISTORY_TABS: DetailTab<"gecmis">[] = [{ value: "gecmis", label: tr.modelConstraints.history, count: 1 }];
const lower = (s: string) => s.toLocaleLowerCase("tr");
const trDate = (iso: string) => { const [y, m, d] = iso.slice(0, 10).split("-"); return `${d}.${m}.${y}`; };
const amount = (v: unknown) => { const n = Number(v); return formatNumber(n, Number.isInteger(n) ? 0 : 2); };
/** Limitin yazımı: "600 / ay". */
export const limitText = (row: Row) => `${amount(row.UpperLimit)} / ${lower(String(row.LimitPeriod ?? ""))}`;
const pairCode = (row: Row) => `${String(row.SupplierCode ?? "")} · ${String(row.MaterialCode ?? "")}`;
const ownerOf = (row: Row): Owner => ({ level: "supplier", id: Number(row.SupplierId), code: String(row.SupplierCode ?? ""), locationId: Number(row.LocationId),
                                        materialId: typeof row.MaterialId === "number" ? row.MaterialId : null });

const api = {
  create: (scenario: number, values: Record<string, unknown>) => sendJson<Saved & { ids: number[] }>("POST", url(scenario), { values }),
  change: (scenario: number, changes: { id: number; field: string; value: unknown }[]) => sendJson<Saved & { saved: number }>("PUT", url(scenario), { changes }),
  remove: (scenario: number, id: number) => sendJson<unknown>("DELETE", url(scenario, `/${id}`)),
  invalidate: (scenario: number, id: number) => sendJson<unknown>("POST", url(scenario, `/${id}/invalidate`)),
  validate: (scenario: number, id: number) => sendJson<unknown>("POST", url(scenario, `/${id}/validate`)),
  restore: (scenario: number, id: number) => sendJson<unknown>("POST", url(scenario, `/${id}/restore`)),
};

interface MaterialOption { id: number; code: string; name: string | null; unit: string | null }
interface SupplierOption { location_id: number; location: string; supplier_id: number; code: string; name: string | null; materials: MaterialOption[] }
const supplierKey = (o: { location_id: number; supplier_id: number }) => `${o.location_id}|${o.supplier_id}`;

/** "Yeni kayıt" ve "Düzenle" penceresi. Düzenlemede tür, tedarikçi ve malzeme değişmez. */
export function SupplierLimitDialog({ spec, scenario, row, owner, onClose, onSaved }: EntryDialogProps) {
  const editing = row !== null;
  const [type, setType] = useState<string>(editing ? String(row.LimitType) : UPPER);   // yeni kayıt "Üst limit" seçili açılır
  const [supplier, setSupplier] = useState(owner?.level === "supplier" && owner.locationId != null ? `${owner.locationId}|${owner.id}` : "");
  const [material, setMaterial] = useState(owner?.materialId != null ? String(owner.materialId) : "");
  const [materials, setMaterials] = useState<string[]>(owner?.materialId != null ? [String(owner.materialId)] : []);   // kapanışta çoklu seçim
  const [from, setFrom] = useState<Date | null>(editing ? parseIso(row.ValidFrom) : null);
  const [to, setTo] = useState<Date | null>(editing ? parseIso(row.ValidTo) : null);
  const [limit, setLimit] = useState<number | null>(editing && typeof row.UpperLimit === "number" ? row.UpperLimit : null);
  const [period, setPeriod] = useState<string>(editing ? String(row.LimitPeriod ?? "") : "");
  const [reason, setReason] = useState(editing ? String(row.Reason ?? "") : "");
  const [options, setOptions] = useState<SupplierOption[] | null>(null);
  const derived = useMemo(() => options && locationsOf(options, (o) => ({ id: String(o.location_id), code: o.location })), [options]);
  const locations = useLocations(derived);     // verideki bütün lokasyonlar (tedarikçisi olmayan lokasyon da)
  const [location, setLocation] = useLocationChoice(locations, owner?.locationId != null ? String(owner.locationId) : "");
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {   // tedarikçiler ve malzemeleri: aktif ve güncel malzeme tedarikçisi kayıtları
    if (editing) return undefined;
    const ctrl = new AbortController();
    getJson<{ suppliers: SupplierOption[] }>(`${BASE}/options`, ctrl.signal).then((d) => setOptions(d.suppliers))
      .catch(() => { if (!ctrl.signal.aborted) { setOptions([]); setError(C.failed); } });
    return () => ctrl.abort();
  }, [editing]);

  const upper = type === UPPER, closure = type === CLOSURE;
  const inLocation = (options ?? []).filter((o) => String(o.location_id) === location);   // tedarikçi listesi seçili lokasyona süzülür (K-194)
  const picked = inLocation.find((o) => supplierKey(o) === supplier);
  const offered = picked?.materials ?? [];
  const unit = editing ? row.Uom : offered.find((m) => String(m.id) === material)?.unit;
  const missing = !type || (!editing && !supplier) || !from || (upper && ((!editing && !material) || limit === null || !period)) || (closure && !to);

  const submit = async () => {
    setBusy(true);
    setProblems({});
    setError(null);
    try {
      let warnings: string[] | undefined;
      if (editing) {
        const next: Record<string, unknown> = { ValidFrom: from ? isoDate(from) : null, ValidTo: to ? isoDate(to) : null,
                                                Reason: reason.trim() || null, ...(upper ? { UpperLimit: limit, LimitPeriod: period || null } : {}) };
        const before: Record<string, unknown> = { ValidFrom: row.ValidFrom ?? null, ValidTo: row.ValidTo ?? null, UpperLimit: row.UpperLimit ?? null,
                                                  LimitPeriod: row.LimitPeriod ?? null, Reason: row.Reason ?? null };
        const changes = Object.entries(next).filter(([name, value]) => JSON.stringify(value) !== JSON.stringify(before[name])).map(([field, value]) => ({ id: row.Id, field, value }));
        if (changes.length) warnings = (await api.change(scenario, changes)).warnings;
      } else {
        const [location, supplierId] = supplier.split("|").map(Number);
        warnings = (await api.create(scenario, {
          LimitType: type, LocationId: location, SupplierId: supplierId, ValidFrom: from ? isoDate(from) : null, ValidTo: to ? isoDate(to) : null,
          Reason: reason.trim() || null,
          ...(upper ? { MaterialId: material ? Number(material) : null, UpperLimit: limit, LimitPeriod: period || null }
            : (materials.length > 1 ? { MaterialIds: materials.map(Number) } : { MaterialId: materials.length ? Number(materials[0]) : null })),
        })).warnings;
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

  const materialOptions = offered.map((m) => ({ value: String(m.id), code: m.code, name: m.name ?? undefined }));
  return (
    <Dialog title={editing ? C.editTitle(spec.title) : C.newTitle(spec.title)} onClose={onClose} onSubmit={() => void submit()} submitLabel={tr.table.editSave} busy={busy}
            submitDisabled={Boolean(missing)} className="sc-dialog--form">
      <div className="sc-form-grid">
        {editing ? <LocationField options={[]} value="" onChange={() => undefined} locked={String(row.LocationCode ?? "")} />
          : <LocationField options={locations ?? []} value={location} error={problems.LocationId}
                           onChange={(v) => { setLocation(v); setSupplier(""); setMaterial(""); setMaterials([]); }} />}
        <div className="sc-form-full">
          {editing ? <TextField label={T.type} value={type === CLOSURE ? T.closure : T.upper} onChange={() => undefined} disabled />
            : <Segment<string> label={T.type} value={type} onChange={setType} options={[{ value: UPPER, label: T.upper }, { value: CLOSURE, label: T.closure }]} />}
          {problems.LimitType && <p className="sc-field-error">{problems.LimitType}</p>}
        </div>
        {editing ? (
          <div className="sc-form-full sc-form-owner">
            <TextField label={T.supplier} value={String(row.SupplierCode ?? "")} onChange={() => undefined} disabled />
            <TextField label={T.material} value={String(row.MaterialCode ?? "")} onChange={() => undefined} disabled />
          </div>
        ) : (
          <>
            <div className="sc-form-full">
              <SearchSelect label={T.supplier} value={supplier} onChange={(v) => { setSupplier(v); setMaterial(""); setMaterials([]); }} error={problems.SupplierId}
                            emptyText={emptyTextOf(location, inLocation.length)} disabled={!location}
                            options={inLocation.map((o) => ({ value: supplierKey(o), code: o.code, name: o.name ?? undefined }))} />
            </div>
            {closure ? (
              <div className="sc-form-full">
                {/* kapanışta birden çok malzeme: seçilen her malzeme ayrı kayıt olur; hiç seçilmezse bütün malzemeler */}
                <SearchSelect label={T.material} value="" onChange={(v) => { if (v) setMaterials((all) => (all.includes(v) ? all : [...all, v])); }} error={problems.MaterialId}
                              emptyText={C.noMatch} disabled={!supplier} options={materialOptions.filter((o) => !materials.includes(o.value))} />
                <ul className="sc-pick-list" aria-label={T.pickedMaterials}>
                  {materials.length === 0 && <li className="sc-tag sc-tag--muted">{T.allMaterials}</li>}
                  {materials.map((id) => {
                    const m = offered.find((x) => String(x.id) === id);
                    return (
                      <li key={id} className="sc-tag">
                        {m?.code ?? id}
                        <button type="button" className="sc-pick-remove" aria-label={T.removeMaterial(m?.code ?? id)} onClick={() => setMaterials((all) => all.filter((x) => x !== id))}>×</button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : (
              <div className="sc-form-full">
                <SearchSelect label={T.material} value={material} onChange={setMaterial} error={problems.MaterialId} emptyText={C.noMatch} disabled={!supplier}
                              options={materialOptions} />
              </div>
            )}
          </>
        )}
        <DateField label={C.start} error={problems.ValidFrom} value={from} onChange={setFrom} />
        <DateField label={C.end} error={problems.ValidTo} value={to} onChange={setTo} />
        {upper && (
          <>
            <div className="sc-form-full">
              <NumberField label={T.limit} error={problems.UpperLimit} live decimals={2} unit={typeof unit === "string" ? unit : null} value={limit} onChange={setLimit} />
            </div>
            <div className="sc-form-full">
              <Segment<string> label={T.period} value={period} onChange={setPeriod} options={PERIODS.map((p) => ({ value: p, label: p }))} />
              {problems.LimitPeriod && <p className="sc-field-error">{problems.LimitPeriod}</p>}
            </div>
          </>
        )}
        <div className="sc-form-full"><TextField label={T.reason} error={problems.Reason} value={reason} onChange={setReason} /></div>
      </div>
      {error && <Alert tone="error">{error}</Alert>}
    </Dialog>
  );
}

const UPPER_FIELDS = new Set(["ValidFrom", "ValidTo", "UpperLimit", "LimitPeriod", "Reason"]);
const CLOSURE_FIELDS = new Set(["ValidFrom", "ValidTo", "Reason"]);
export const SUPPLIER_LIMITS: EntrySpec = {
  kind: "supplier-limits", list: "supplier-limits", table: TABLE, title: T.title, owner: true, start: "ValidFrom",
  fields: [{ name: "ValidFrom", label: C.start, kind: "date", required: true }, { name: "ValidTo", label: C.end, kind: "date" },
           { name: "UpperLimit", label: T.limit, kind: "number", decimals: 2 }, { name: "LimitPeriod", label: T.period, kind: "choice", options: PERIODS },
           { name: "Reason", label: T.reason, kind: "text" }],
  adapter: {
    api, writeFunction: 103, Dialog: SupplierLimitDialog,
    label: (row, shown) => `${pairCode(row)} · ${shown("ValidFrom", row)}`,
    ownerOf,
    // iki tür aynı tabloda: kapanışta Limit ve Limitin dönemi düzenlenmez (hücre boştur); tarihler ve Sebep iki türde de düzenlenir
    canEdit: (field, row) => (row.LimitType === CLOSURE ? CLOSURE_FIELDS : UPPER_FIELDS).has(field),
    hints: { LimitType: { width: 6 }, SupplierCode: { width: 6.5 }, MaterialCode: { width: 7 }, UpperLimit: { width: 7 }, LimitPeriod: { width: 9.5 }, Uom: { width: 4.2 },
             Reason: { width: 10 }, Origin: { width: 8.6 }, IsValid: { width: 5.6 }, SupplierName: { width: 16 }, MaterialName: { width: 16 } },
  },
};

/** Geçerlilik: her satır bir tedarikçi ve malzeme; üst limit dilimi nane ("600 / ay"), kapanış dilimi amber ve üstte. */
export const SUPPLIER_VALIDITY: ValidityCustom = {
  list: "supplier-limits-validity", entry: SUPPLIER_LIMITS, corner: T.corner, labelRem: 13,
  hints: { LocationCode: { width: 6.5 }, SupplierCode: { width: 7 }, MaterialCode: { width: 8 }, Status: { width: 7 }, ValidFrom: { width: 7.2 }, ValidTo: { width: 7.2 },
           UpperLimit: { width: 8 }, LimitPeriod: { width: 9.5 }, DailyAverage: { width: 10.5 }, Uom: { width: 4.5 } },
  describe: (row) => {
    const closed = row.Status === CLOSED;
    const code = pairCode(row);
    const range = row.ValidTo ? `${trDate(String(row.ValidFrom))} – ${trDate(String(row.ValidTo))}` : C.view.since(trDate(String(row.ValidFrom)));
    const unit = row.Uom ? ` ${String(row.Uom)}` : "";
    return {
      key: `${String(row.LocationId)}|${String(row.SupplierId)}|${String(row.MaterialId ?? 0)}`, code, title: code, own: closed, top: closed,
      text: closed ? T.closed : limitText(row),
      lines: closed ? [code, T.closed, range, ...(row.Reason ? [String(row.Reason)] : [])]
        : [code, `${T.limit}: ${amount(row.UpperLimit)}${unit} / ${lower(String(row.LimitPeriod ?? ""))}`, range, `${T.dailyAverage}: ${formatNumber(Number(row.DailyAverage), 2)}${unit}`,
           ...(row.SourceOrigin === "Senaryo farkı" ? [C.view.scenarioDiff] : [])],
    };
  },
  ownerKey: (row) => `,s${String(row.SupplierId)},`,   // genel kapanışın kaydı malzemesizdir: tedarikçinin bütün kayıtlarında aranır
  newOwner: ownerOf,
  label: pairCode,
};

/** "Tedarikçi limiti" sekmesi: tablo seçimi Kayıtlar · Geçerlilik; Kayıtlar'da Detay kartında Geçmiş. */
export function SupplierLimitsTab({ lead }: { lead: ReactNode }) {
  const { scenario } = useShell();
  const [view, setView] = useState<TableView>("kayitlar");
  const [card, setCard] = useState<Row | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [focus, setFocus] = useState<{ id: number; n: number } | undefined>(undefined);
  const [version, setVersion] = useState(0);
  const many = useManyLocations();
  const head = useMemo(() => <>{lead}<TableChoice value={view} onChange={setView} /></>, [lead, view]);
  const onChanged = () => setVersion((n) => n + 1);
  if (view === "gecerlilik") {
    return <ValidityView custom={SUPPLIER_VALIDITY} lead={head} reloadKey={version} onChanged={onChanged}
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
    <MasterDetail id="model-constraints-suppliers" onClose={() => setCard(null)} hideTitle
                  master={<EntryTable spec={SUPPLIER_LIMITS} lead={head} onDetail={setCard} selectedRowId={card?.Id ?? null} reloadKey={version} onChanged={onChanged}
                                      onSelection={setPicked} focus={focus} />}
                  detail={card ? { title: ids.length > 1 ? C.manyRecords(formatNumber(ids.length)) : withLocation(many, card.LocationCode, pairCode(card)), tabsLabel: tr.modelConstraints.cardTabs, tabs: HISTORY_TABS,
                                   tab: "gecmis" as const, onTab: () => undefined, renderBody } : null} />
  );
}
