// Parametreler › Uyarı eşikleri (fonksiyon 26; K-190; docs/12 "Parametreler"): seçili senaryonun uyarı eşikleri. Öteki başlıklarla aynı düzen: solda
// alt başlıklar (Talep · Malzeme · Kapasite · Plan kalitesi), sağda seçili kategorinin kartı: Uyarı · Birim · Yön · Düşük · Orta · Yüksek · Kritik ·
// Aktif. Eşikli uyarıda her önem için ayrı eşik (kademeli; boş hücre o kademenin kullanılmadığını gösterir; yüzde "%95" biçiminde); eşiksiz uyarıda
// dört önem kolonunun yerinde tek seçim düğmesi. Dolu kademeler yöne göre sıralı olmalıdır; sıra bozuksa hücre kırmızıdır ve Kaydet kapalıdır.
// Kapalı uyarının satırı belirgin soluktur, değerleri durur. Kaydetme kategori başınadır (sunucuya tablonun tamamı gider; öteki kategoriler kayıtlı
// hâliyle). Eşikler senaryoya bağlı ayardır (tam kopya): fark işareti yok.
import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/client";
import { formatNumber, parseTrNumber } from "../format";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import { SwitchCell } from "../table/CellEditors";
import { Alert, EditGrid, type GridColumn, Segment, SettingsFoot } from "../ui";
import { parametersApi, TIERS, type Tier, type WarningRow } from "./parametersApi";

const T = tr.parameters;
const W = tr.parameters.warnings;
const PCT = "%";
type Texts = Record<Tier, string>;
interface Draft extends WarningRow { texts: Texts }

const numberText = (v: number | null) => (v === null ? "" : formatNumber(v, Number.isInteger(v) ? 0 : Number.isInteger(v * 10) ? 1 : 2));
const asDraft = (r: WarningRow): Draft => ({ ...r, texts: { low: numberText(r.low), medium: numberText(r.medium), high: numberText(r.high), critical: numberText(r.critical) } });
const clean = (text: string) => text.trim().replace(/^%/, "").trim();
const errorText = (e: unknown) => (e instanceof ApiError ? e.message : T.failed);

/** Hücredeki sayı: boş → null; sayı değilse NaN. */
function valueOf(row: Draft, tier: Tier): number | null {
  const text = row.texts[tier];
  if (!text) return null;
  return parseTrNumber(text) ?? Number.NaN;
}

/** Hücrenin sorunu: sunucudaki kuralların aynısı (sayı, birim, yöne göre kademe sırası). */
function tierProblem(row: Draft, tier: Tier, severities: string[]): string | undefined {
  const value = valueOf(row, tier);
  if (value === null) return undefined;
  if (Number.isNaN(value)) return W.notNumber;
  if (value < 0) return W.negative;
  if (row.unit !== PCT && !Number.isInteger(value)) return W.notInteger;
  if (row.unit === PCT && Math.round(value * 100) !== value * 100) return W.twoDecimals;
  const at = TIERS.indexOf(tier);
  for (let i = at - 1; i >= 0; i -= 1) {   // bir önceki dolu ve geçerli kademe
    const before = valueOf(row, TIERS[i]);
    if (before === null || Number.isNaN(before)) continue;
    const ordered = row.direction === "above" ? value > before : value < before;
    return ordered ? undefined : W.order(severities[at], severities[i], row.direction === "above");
  }
  return undefined;
}

export function WarningThresholds({ category, canWrite, onDirty }: { category: string; canWrite: boolean; onDirty(dirty: boolean): void }) {
  const { scenario } = useShell();
  const api = useMemo(() => parametersApi(scenario?.id ?? 0), [scenario?.id]);
  const [saved, setSaved] = useState<WarningRow[] | null>(null);
  const [severities, setSeverities] = useState<string[]>([]);
  const [rows, setRows] = useState<Draft[]>([]);   // bütün kategoriler: kayıt tablonun tamamını gönderir
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rejected, setRejected] = useState<Record<string, string>>({});   // sunucunun reddettiği hücreler: "<kod>|<alan>" → neden
  const load = (d: { rows: WarningRow[]; severities: string[] }) => {
    setSaved(d.rows);
    setSeverities(d.severities);
    setRows(d.rows.map(asDraft));
    setRejected({});
  };
  useEffect(() => {
    const ctrl = new AbortController();
    api.warningThresholds(ctrl.signal).then(load).catch((e: unknown) => { if (!ctrl.signal.aborted) setError(errorText(e)); });
    return () => ctrl.abort();
  }, [api]);

  const byCode = useMemo(() => new Map((saved ?? []).map((r) => [r.code, r])), [saved]);
  const changed = (r: Draft, field: Tier | "active" | "severity") => {
    const old = byCode.get(r.code);
    if (!old) return false;
    if (field === "active") return old.active !== r.active;
    if (field === "severity") return old.severity !== r.severity;
    const now = valueOf(r, field);
    return Number.isNaN(now) || old[field] !== now;
  };
  const thresholded = (r: Draft) => r.unit !== null;
  const empty = (r: Draft) => thresholded(r) && TIERS.every((t) => !r.texts[t]);
  const problemOf = (r: Draft, field: Tier | "active") => {
    const fromServer = rejected[`${r.code}|${field}`];
    if (field === "active") return r.active && empty(r) ? W.noTier : fromServer;
    return (thresholded(r) ? tierProblem(r, field, severities) : undefined) ?? fromServer;
  };
  const dirty = rows.some((r) => changed(r, "active") || changed(r, "severity") || (thresholded(r) && TIERS.some((t) => changed(r, t))));
  useEffect(() => onDirty(dirty), [dirty, onDirty]);
  const invalid = rows.some((r) => (r.active && empty(r)) || (thresholded(r) && TIERS.some((t) => tierProblem(r, t, severities))));

  const patch = (code: string, change: Partial<Draft>) => {
    setRows((rs) => rs.map((r) => (r.code === code ? { ...r, ...change } : r)));
    setRejected((all) => Object.fromEntries(Object.entries(all).filter(([key]) => !key.startsWith(`${code}|`))));
  };
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      load(await api.saveWarningThresholds(rows.map((r) => ({
        code: r.code, active: r.active, severity: thresholded(r) ? null : r.severity,
        ...(Object.fromEntries(TIERS.map((t) => [t, thresholded(r) ? valueOf(r, t) : null])) as Record<Tier, number | null>) }))));
    } catch (e) {
      if (e instanceof ApiError && e.details.length) {
        const found: Record<string, string> = {};
        for (const d of e.details) {
          const m = /^rows\.(\d+)\.(\w+)$/.exec(d.field);
          const row = m ? rows[Number(m[1]) - 1] : undefined;
          if (row) found[`${row.code}|${m![2]}`] = d.problem;
        }
        setRejected(found);
        setError(`${T.notSaved} ${e.details[0].record ? `${e.details[0].record}: ` : ""}${e.details[0].problem}`);
      } else {
        setError(errorText(e));
      }
    } finally {
      setBusy(false);
    }
  };

  if (!saved) return error ? <Alert tone="error">{error}</Alert> : null;
  const stop = (e: { stopPropagation(): void }) => e.stopPropagation();   // seçim düğmesinin ok tuşları ve tıklaması tablonun imlecine gitmesin
  const tierColumn = (tier: Tier, index: number): GridColumn<Draft> => ({
    key: tier, label: severities[index] ?? tier, num: true, width: 6,
    // Eşiksiz uyarı: dört önem kolonunun yerinde tek seçim düğmesi (ilk önem kolonu dördünü kaplar)
    span: index === 0 ? (r) => (thresholded(r) ? 1 : TIERS.length) : undefined,
    render: (r) => {
      if (thresholded(r)) return <span className="sc-num">{r.texts[tier] && r.unit === PCT ? `${PCT}${r.texts[tier]}` : r.texts[tier]}</span>;
      return (
        <span className="sc-severity-choice" onClick={stop} onDoubleClick={stop} onKeyDown={stop}>
          <Segment<string> label={W.severityOf(r.label)} hideLabel value={r.severity ?? ""} onChange={(v) => patch(r.code, { severity: v })}
                           options={severities.map((s) => ({ value: s, label: s, disabled: !canWrite }))} />
        </span>
      );
    },
    edit: { text: (r) => r.texts[tier], commit: (r, text) => patch(r.code, { texts: { ...r.texts, [tier]: clean(text) } }), can: thresholded },
    changed: (r) => (thresholded(r) ? changed(r, tier) : changed(r, "severity")),
    problem: (r) => (thresholded(r) ? problemOf(r, tier) : rejected[`${r.code}|severity`]),
  });
  const columns: GridColumn<Draft>[] = [
    { key: "label", label: W.warning, render: (r) => r.label },
    { key: "unit", label: W.unit, width: 3.8, render: (r) => r.unit ?? "" },
    { key: "direction", label: W.direction, width: 9.5, render: (r) => (r.direction === "above" ? W.above : r.direction === "below" ? W.below : "") },
    ...TIERS.map(tierColumn),
    { key: "active", label: T.active, width: 5.5, marked: true,
      render: (r) => <SwitchCell label={T.activeOf(r.label)} checked={r.active} editable={canWrite} changed={changed(r, "active")} onToggle={(v) => patch(r.code, { active: v })} />,
      changed: (r) => changed(r, "active"), problem: (r) => problemOf(r, "active") },
  ];
  const label = W.tableOf(category);
  return (
    <div className="sc-settings-section sc-settings-section--grid sc-settings-section--wide">
      <section className="sc-settings-card" aria-label={label}>
        <EditGrid<Draft> label={label} columns={columns} rows={rows.filter((r) => r.category === category)} rowKey={(r) => r.code}
                         rowClass={(r) => (r.active ? "" : "is-off is-dim")} editable={canWrite} />
        <SettingsFoot dirty={dirty} busy={busy} invalid={invalid} onDiscard={() => { setRows(saved.map(asDraft)); setRejected({}); setError(null); }} onSave={() => void save()} />
      </section>
      {error && <Alert tone="error">{error}</Alert>}
    </div>
  );
}
