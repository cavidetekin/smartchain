// Parametreler › Hedefler (fonksiyon 22; K-175, K-196; docs/12 "Hedefler"): hedef listesi kullanıcınındır. Tablo sayfanın tamamını kaplar:
// Sıra · Grup · Hedef · Kapsam · Açıklama · Süre bütçesi · Ödün payı · Aktif · satır menüsü. Grup hücresinin sol kenarında grup rengi (talep,
// malzeme, kaynak, diğer); renk açıklaması tablonun altında. Sıra sürüklenir (satır sırası hedefin önceliğidir: kolon başlığından sıralama yok);
// kolon genişliği ayarlanır (tarayıcıda saklanır). Şeritte (`actions`): "Başlangıç düzenine getir" ve "Yeni hedef tanımla" sekmelerin hemen
// yanında; Vazgeç ve Kaydet yalnız değişiklik olunca, tablonun sağ üstünde (K-132). Soluk yalnız "kapalı satır" demektir (satırın tamamı).
// "Yeni hedef tanımla", "Düzenle", "Hedefi sil" ve "Başlangıç düzenine getir" hemen yazılır (taslak değildir); kaydedilmemiş değişiklik varken
// pasiftir. Sistem kendiliğinden satır üretmez, bölmez, kaldırmaz; kapsamlar örtüşebilir.
import { Ellipsis } from "lucide-react";
import { Fragment, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import { ApiError } from "../api/client";
import { formatNumber, parseTrNumber } from "../format";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import { SwitchCell } from "../table/CellEditors";
import { Alert, Button, ConfirmDialog, Dialog, EditGrid, type GridColumn, GridSeq, MultiSelect, NumberField, SearchSelect, TextField, Tooltip } from "../ui";
import { MenuItem, RowPopMenu } from "../ui/PopMenu";
import { dropId } from "./DataRules";
import { type ObjectiveEdit, type ObjectiveKind, type ObjectiveRow, type ObjectivesData, parametersApi } from "./parametersApi";

const T = tr.parameters;
const FAMILIES = ["talep", "malzeme", "kaynak", "diger"] as const;
const DEFAULT_SECONDS = "60";
const DEFAULT_TOLERANCE = "5";
const DESCRIPTION_MAX = 200;
const LONG_SCOPE = 60;   // bundan uzun kapsam yazısı hücrede kısalabilir: tamamı ipucunda
const STORE = "sc.objectives.columns";   // kolon genişlikleri (tarayıcıda; kullanıcıya özel kolaylık)

const errorText = (e: unknown) => (e instanceof ApiError ? (e.details.length ? e.details[0].problem : e.message) : T.failed);
const trNumber = (v: number | null) => (v === null ? "" : formatNumber(v, Number.isInteger(v) ? 0 : 2));
const nameOf = (r: ObjectiveRow) => (r.scope_text ? `${r.label} · ${r.scope_text}` : r.label);

interface Draft extends ObjectiveRow { secondsText: string; toleranceText: string }
const asDraft = (r: ObjectiveRow): Draft => ({ ...r, secondsText: trNumber(r.seconds), toleranceText: trNumber(r.tolerance) });

function readWidths(): Record<string, number> {
  try {
    return (JSON.parse(localStorage.getItem(STORE) ?? "{}") as { widths?: Record<string, number> }).widths ?? {};
  } catch {
    return {};
  }
}

/** Pencere ("Yeni hedef tanımla" ve "Düzenle"; pencere ve form standardı): Grup ve Hedef (aramalı seçim; seçilmeden önce boş) → kapsam
 *  seçimleri (aramalı çoklu seçim) → Açıklama → Süre bütçesi ve Ödün payı. Kapsam almayan hedefte kapsam satırı yoktur. Bir eksende hepsini
 *  seçmek ile hiç seçmemek aynıdır (kapsama yazılmaz). Zorunlu alan eksikken birincil düğme pasif, mesaj yok. */
function ObjectiveDialog({ catalog, row, onClose, onSubmit }: {
  catalog: ObjectiveKind[]; row: ObjectiveRow | null; onClose(): void; onSubmit(body: ObjectiveEdit): Promise<void>;
}) {
  const groups = useMemo(() => FAMILIES.filter((f) => catalog.some((k) => k.family === f)), [catalog]);
  const first = row ? catalog.find((k) => k.code === row.code) : undefined;
  const [family, setFamily] = useState<string>(first?.family ?? "");
  const [code, setCode] = useState(row?.code ?? "");
  const [picked, setPicked] = useState<Record<string, (string | number)[]>>(row?.scope ?? {});
  const [description, setDescription] = useState(row?.description ?? "");
  const [seconds, setSeconds] = useState<number | null>(row?.seconds ?? null);
  const [tolerance, setTolerance] = useState<number | null>(row?.tolerance ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const kind = catalog.find((k) => k.code === code);
  const timed = !row || row.active;   // kapalı satırda süre ve ödün payı boştur; pencerede düzenlenmez
  const secondsOk = seconds !== null && Number.isInteger(seconds) && seconds >= 1;
  const toleranceOk = tolerance !== null && tolerance >= 0 && tolerance <= 100 && Math.round(tolerance * 100) === tolerance * 100;
  const ready = Boolean(kind) && (!timed || (secondsOk && toleranceOk));
  const send = async () => {
    if (!kind) return;
    setBusy(true);
    setError(null);
    const scope = Object.fromEntries(kind.axes.map((a) => [a.key, picked[a.key] ?? []] as const).filter(([k, v]) => v.length > 0
      && v.length < (kind.axes.find((a) => a.key === k)?.values.length ?? 0)));
    try {
      await onSubmit({ code, scope, description: description.trim() || null, seconds: timed ? seconds : null, tolerance: timed ? tolerance : null });
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };
  return (
    <Dialog title={row ? T.editObjective : T.define} onClose={onClose} onSubmit={() => void send()} submitLabel={row ? tr.ui.save : T.defineSubmit} busy={busy}
            submitDisabled={!ready} className="sc-dialog--form">
      <div className="sc-form-grid">
        <SearchSelect label={T.group} value={family} emptyText={T.noMatch} onChange={(v) => { setFamily(v); setCode(""); setPicked({}); }}
                      options={groups.map((f) => ({ value: f, code: T.families[f] }))} />
        <SearchSelect label={T.objective} value={code} emptyText={T.noMatch} disabled={!family} onChange={(v) => { setCode(v); setPicked({}); }}
                      options={catalog.filter((k) => k.family === family).map((k) => ({ value: k.code, code: k.label }))} />
        {kind?.axes.map((axis) => (
          <MultiSelect<string | number> key={`${code}:${axis.key}`} label={axis.label} options={axis.values} value={picked[axis.key] ?? []} placeholder={T.all}
                                        emptyText={T.noMatch} onChange={(next) => setPicked((p) => ({ ...p, [axis.key]: next }))} />
        ))}
        <div className="sc-form-full"><TextField label={T.description} value={description} maxLength={DESCRIPTION_MAX} onChange={setDescription} /></div>
        <NumberField label={T.secondsShort} unit={T.secondsUnit} value={seconds} onChange={setSeconds} live disabled={!timed} />
        <NumberField label={T.toleranceShort} unit={T.toleranceUnit} value={tolerance} onChange={setTolerance} decimals={Number.isInteger(tolerance ?? 0) ? 0 : 2} live
                     disabled={!timed} />
      </div>
      {error && <Alert tone="error">{error}</Alert>}
    </Dialog>
  );
}

export function Objectives({ canWrite, onDirty, actions }: {
  canWrite: boolean; onDirty(dirty: boolean): void;
  /** Sekme şeridinin sağındaki yer: işlemler, Alanlar, Vazgeç ve Kaydet buraya çizilir (şerit standardı). */
  actions: HTMLElement | null;
}) {
  const { scenario } = useShell();
  const api = useMemo(() => parametersApi(scenario?.id ?? 0), [scenario?.id]);
  const [data, setData] = useState<ObjectivesData | null>(null);
  const [rows, setRows] = useState<Draft[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [menu, setMenu] = useState<{ id: number; anchor: HTMLElement } | null>(null);
  const [dialog, setDialog] = useState<"define" | "reset" | { edit: Draft } | { remove: Draft } | null>(null);
  const [widths, setWidths] = useState<Record<string, number>>(readWidths);
  useEffect(() => { try { localStorage.setItem(STORE, JSON.stringify({ widths })); } catch { /* saklanamazsa oturumluk kalır */ } }, [widths]);
  const saved = data?.rows ?? null;
  const load = (d: ObjectivesData) => {
    setData(d);
    setRows(d.rows.map(asDraft));
  };
  useEffect(() => {
    const ctrl = new AbortController();
    api.objectives(ctrl.signal).then(load).catch((e: unknown) => { if (!ctrl.signal.aborted) setError(errorText(e)); });
    return () => ctrl.abort();
  }, []);

  const byId = useMemo(() => new Map((saved ?? []).map((r, i) => [r.id, { ...r, index: i }])), [saved]);
  const secondsOf = (r: Draft) => parseTrNumber(r.secondsText);
  const toleranceOf = (r: Draft) => parseTrNumber(r.toleranceText);
  const secondsProblem = (r: Draft) => {
    const n = secondsOf(r);
    return r.active && (n === null || !Number.isInteger(n) || n < 1) ? T.secondsProblem : undefined;
  };
  const toleranceProblem = (r: Draft) => {
    const n = toleranceOf(r);
    return r.active && (n === null || n < 0 || n > 100 || Math.round(n * 100) !== n * 100) ? T.toleranceProblem : undefined;
  };
  const orderChanged = saved !== null && rows.some((r, i) => saved[i]?.id !== r.id);
  const cellChanged = (r: Draft, field: "seconds" | "tolerance" | "active") => {
    const old = byId.get(r.id);
    if (!old) return false;
    if (field === "active") return old.active !== r.active;
    return r.active && (field === "seconds" ? old.seconds !== secondsOf(r) : old.tolerance !== toleranceOf(r));
  };
  const dirty = orderChanged || rows.some((r) => cellChanged(r, "seconds") || cellChanged(r, "tolerance") || cellChanged(r, "active"));
  useEffect(() => onDirty(dirty), [dirty, onDirty]);
  const noneActive = rows.length > 0 && !rows.some((r) => r.active);
  const invalid = noneActive || rows.some((r) => secondsProblem(r) || toleranceProblem(r));

  const patch = (id: number, change: Partial<Draft>) => setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...change } : r)));
  const toggle = (row: Draft, on: boolean) => setRows((rs) => {
    const rest = rs.filter((r) => r.id !== row.id);
    const active = rest.filter((r) => r.active);
    const off = rest.filter((r) => !r.active);
    const old = byId.get(row.id);
    const next: Draft = on
      ? { ...row, active: true, secondsText: trNumber(old?.seconds ?? null) || DEFAULT_SECONDS, toleranceText: trNumber(old?.tolerance ?? null) || DEFAULT_TOLERANCE }
      : { ...row, active: false, secondsText: "", toleranceText: "" };
    return [...active, next, ...off];  // açılan aktiflerin sonuna, kapanan kapalıların başına
  });
  const move = (id: string, target: string, side: "before" | "after") => setRows((rs) => {
    const ids = dropId(rs.filter((r) => r.active).map((r) => String(r.id)), id, target, side);
    const map = new Map(rs.map((r) => [String(r.id), r]));
    return [...ids.map((x) => map.get(x)!), ...rs.filter((r) => !r.active)];
  });
  const run = async (work: () => Promise<ObjectivesData>) => {
    setBusy(true);
    setError(null);
    setDialog(null);
    try {
      load(await work());
    } catch (e) {
      setError(e instanceof ApiError && e.details.length ? `${T.notSaved} ${e.details[0].problem}` : errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const save = () => run(() => api.saveObjectives(rows.map((r) => ({ id: r.id, active: r.active, seconds: r.active ? secondsOf(r) : null, tolerance: r.active ? toleranceOf(r) : null }))));
  const discard = () => { if (saved) setRows(saved.map(asDraft)); setError(null); };

  if (!data || !saved) return error ? <Alert tone="error">{error}</Alert> : null;
  let seq = 0;
  const seqOf = new Map(rows.map((r) => [r.id, r.active ? ++seq : null]));
  const total = rows.reduce((sum, r) => sum + (r.active ? secondsOf(r) ?? 0 : 0), 0);
  const scopeCell = (r: Draft) => {
    const text = r.scope_parts.length === 0 ? r.scope_text : (
      <>{r.scope_parts.map((p, i) => <Fragment key={p.label}>{i > 0 && " · "}<b>{p.label}:</b> {p.values.join(", ")}</Fragment>)}</>
    );
    const long = r.scope_text.length > LONG_SCOPE;   // uzun kapsam hücrede kısalır: tamamı ipucunda
    return <Tooltip content={long ? r.scope_text : null} focusable={long}><span>{text}</span></Tooltip>;
  };
  const columns: GridColumn<Draft>[] = [
    { key: "seq", label: T.seq, width: 4.5, render: (r) => <GridSeq seq={seqOf.get(r.id) ?? null} movable={canWrite && r.active} /> },
    { key: "group", label: T.group, width: 7, cls: "sc-objective-group", render: (r) => r.group },
    { key: "label", label: T.objective, width: 14, cls: "sc-objective-name", render: (r) => r.label },
    { key: "scope", label: T.scope, cls: "sc-objective-scope", render: scopeCell },
    { key: "description", label: T.description, width: 13, cls: "sc-objective-description",
      render: (r) => (r.description ? <span title={r.description.length > 30 ? r.description : undefined}>{r.description}</span> : null) },
    { key: "seconds", label: T.seconds, num: true, width: 10, render: (r) => <span className="sc-num">{r.active ? r.secondsText : ""}</span>,
      edit: { text: (r) => r.secondsText, commit: (r, text) => patch(r.id, { secondsText: text.trim() }), can: (r) => r.active },
      changed: (r) => cellChanged(r, "seconds"), problem: secondsProblem },
    { key: "tolerance", label: T.tolerance, num: true, width: 8.5, render: (r) => <span className="sc-num">{r.active ? r.toleranceText : ""}</span>,
      edit: { text: (r) => r.toleranceText, commit: (r, text) => patch(r.id, { toleranceText: text.trim() }), can: (r) => r.active },
      changed: (r) => cellChanged(r, "tolerance"), problem: toleranceProblem },
    { key: "active", label: T.active, width: 5.5, marked: true,
      render: (r) => <SwitchCell label={T.activeOf(nameOf(r))} checked={r.active} editable={canWrite} changed={cellChanged(r, "active")} onToggle={(v) => toggle(r, v)} />,
      changed: (r) => cellChanged(r, "active") },
    ...(canWrite ? [{ key: "menu", label: "", width: 3, cls: "sc-table-rowmenu", render: (r: Draft) => (
      <button type="button" className="sc-table-filter-btn" aria-haspopup="menu" aria-label={T.objectiveMenu(nameOf(r))}
              onClick={(e) => setMenu({ id: r.id, anchor: e.currentTarget })}>
        <Ellipsis aria-hidden="true" />
      </button>
    ) } as GridColumn<Draft>] : []),
  ];
  // Toplam satırı: "Toplam" Grup kolonunda, satır sayısı Kapsam'da, süre kendi kolonunda
  const footCell = (key: string) => {
    if (key === "group") return T.total;
    if (key === "scope") return T.rowsCount(rows.length);
    if (key === "seconds") return <span className="sc-num">{formatNumber(total)}</span>;
    return null;
  };
  const menuRow = menu ? rows.find((r) => r.id === menu.id) : undefined;
  const locked = dirty ? { allowed: false, reason: T.saveFirst } : { allowed: true };
  const strip = (
    <>
      {canWrite && (
        <>
          <Button variant="neutral" disabled={busy} disabledReason={dirty ? T.saveFirst : null} onClick={() => setDialog("reset")}>{T.resetLayout}</Button>
          <Button variant="primary" disabled={busy} disabledReason={dirty ? T.saveFirst : null} onClick={() => setDialog("define")}>{T.define}</Button>
        </>
      )}
      {/* Vazgeç ve Kaydet yalnız değişiklik olunca, tablonun sağ üstünde (K-132) */}
      {canWrite && dirty && (
        <span className="sc-section-actions-end">
          <Button variant="ghost" disabled={busy} onClick={discard}>{tr.ui.cancel}</Button>
          <Button variant="primary" busy={busy} disabled={invalid} onClick={() => void save()}>{tr.ui.save}</Button>
        </span>
      )}
    </>
  );
  return (
    <div className="sc-objectives">
      {actions && createPortal(strip, actions)}
      {noneActive && <Alert tone="risk">{T.oneActive}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}
      <section className="sc-objectives-table" aria-label={T.objectives}>
        <EditGrid<Draft> label={T.objectives} columns={columns} rows={rows} rowKey={(r) => String(r.id)}
                         rowClass={(r) => `sc-objective--${r.family}${r.active ? "" : " is-off"}`}
                         editable={canWrite} drag={{ can: (r) => r.active, move }}
                         resize={{ widths, onWidth: (key, rem) => setWidths((w) => ({ ...w, [key]: rem })) }}
                         foot={<tr>{columns.map((c) => <td key={c.key} className={c.num ? "is-num" : undefined}>{footCell(c.key)}</td>)}</tr>} />
      </section>
      <ul className="sc-objective-legend" aria-label={T.familyLegend}>
        {FAMILIES.map((f) => <li key={f}><i className={`sc-objective-swatch sc-objective-swatch--${f}`} aria-hidden="true" />{T.families[f]}</li>)}
      </ul>
      {menu && menuRow && (
        <RowPopMenu label={T.objectiveMenu(nameOf(menuRow))} anchor={menu.anchor} onClose={() => setMenu(null)}>
          <MenuItem label={T.editObjective} state={locked} onClick={() => { setDialog({ edit: menuRow }); setMenu(null); }} />
          <MenuItem label={T.removeObjective} state={locked} onClick={() => { setDialog({ remove: menuRow }); setMenu(null); }} />
        </RowPopMenu>
      )}
      {dialog === "define" && (
        <ObjectiveDialog catalog={data.catalog} row={null} onClose={() => setDialog(null)}
                         onSubmit={async (body) => { load(await api.createObjective(body)); setDialog(null); }} />
      )}
      {dialog && typeof dialog === "object" && "edit" in dialog && (
        <ObjectiveDialog catalog={data.catalog} row={dialog.edit} onClose={() => setDialog(null)}
                         onSubmit={async (body) => { load(await api.updateObjective(dialog.edit.id, body)); setDialog(null); }} />
      )}
      {dialog === "reset" && (
        <ConfirmDialog title={T.resetLayout} message={T.resetConfirm} confirmLabel={T.resetLayout} danger onConfirm={() => void run(api.resetObjectives)}
                       onCancel={() => setDialog(null)} />
      )}
      {dialog && typeof dialog === "object" && "remove" in dialog && (
        <ConfirmDialog title={T.removeObjective} message={T.removeConfirm(nameOf(dialog.remove))} confirmLabel={T.removeObjective} danger
                       onConfirm={() => void run(() => api.deleteObjective(dialog.remove.id))} onCancel={() => setDialog(null)} />
      )}
    </div>
  );
}
