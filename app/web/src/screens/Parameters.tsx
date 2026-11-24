// Parametreler (ekran 06; fonksiyon 22, 23; K-175, K-177, docs/12): bağlam çubuğunda seçili senaryonun parametreleri. Şeritte ana başlıklar
// (Model · Hedefler · Talep · Malzeme · Kapasite · Zaman · Plan kararlılığı); form başlıklarında solda alt başlıklar, sağda sıkı kart (Sistem
// ayarları düzeni); tablo başlıklarında (Hedefler, Zaman › Ufuk ve dönemler) form içi tablo, Kaydet ve Vazgeç tablonun altında. Kaydedilmemiş
// değişiklikle başlık, alt başlık ya da ekran değişirken uyarı (K-132). Başarılı kayıtta bildirim yok.
import { Ellipsis } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { formatDate, parseTrNumber, serverDate } from "../format";
import { tr } from "../i18n/tr";

import { UnsavedGuard } from "../table/useTableEdits";
import { Alert, Button, ChoiceRow, ConfirmDialog, EditGrid, type GridColumn, GridSeq, NumberField, OverflowTabs, SelectField, SettingsCard, SettingsFoot,
         SettingsLayout, SwitchRow, UnitRow } from "../ui";
import { MenuItem, RowPopMenu } from "../ui/PopMenu";
import { dropId } from "./DataRules";
import { Objectives } from "./Objectives";
import { type Axis, type BucketPart, type BucketRow, type BucketsData, type ParamDef, type ParametersData, type ParamValues,
         parametersApi, type Period, type SubDef } from "./parametersApi";
import { useShell } from "../shell/ShellContext";
import { WarningThresholds } from "./WarningThresholds";

const T = tr.parameters;
/** Seçili senaryonun uçları (K-177); ekran senaryo yüklendikten sonra çizilir (App `ScenarioBound`). */
const useApi = () => {
  const { scenario } = useShell();
  return useMemo(() => parametersApi(scenario?.id ?? 0), [scenario?.id]);
};
const YES = "1";
const NO = "0";
const SEGMENT_MAX = 4;  // daha çok seçenek açılır listeyle (hafta başlangıcı)

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : T.failed);
const problemsOf = (e: unknown): Record<string, string> =>
  (e instanceof ApiError ? Object.fromEntries(e.details.map((d) => [d.field, d.problem])) : {});

// ------------------------------------------------------------------ form başlığı

function ParamForm({ title, params, data, canWrite, onSaved, onDirty, onValues }: {
  title: string; params: ParamDef[]; data: ParametersData; canWrite: boolean; onSaved(next: ParametersData): void; onDirty(dirty: boolean): void;
  /** Taslak değerler (ör. raporlama ekseni anahtarı kaydetmeden ikinci tabloyu açar). */
  onValues?(values: ParamValues): void;
}) {
  const api = useApi();
  const [values, setValues] = useState<ParamValues>(data.values);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [problems, setProblems] = useState<Record<string, string>>({});
  useEffect(() => setValues(data.values), [data]);

  const changed = params.filter((p) => values[p.key] !== data.values[p.key]);
  const dirty = changed.length > 0;
  useEffect(() => onDirty(dirty), [dirty, onDirty]);
  useEffect(() => onValues?.(values), [values, onValues]);
  const unitKeys = new Set(params.map((p) => p.unit_key).filter(Boolean));
  const set = (key: string, value: string | null) => {
    setValues((s) => ({ ...s, [key]: value }));
    setProblems((s) => ({ ...s, [key]: "" }));
  };
  const local = (p: ParamDef): string | undefined => {
    const v = values[p.key];
    if (p.kind !== "int" && p.kind !== "number") return undefined;
    if (v === null) return p.nullable ? undefined : tr.ui.invalidNumber;
    const n = Number(v);
    if (p.min !== undefined && n < p.min) return tr.systemOwner.limit(p.min, p.max ?? Number.MAX_SAFE_INTEGER);
    if (p.max !== undefined && n > p.max) return tr.systemOwner.limit(p.min ?? 0, p.max);
    return undefined;
  };
  const invalid = params.some((p) => local(p));
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      onSaved(await api.save(Object.fromEntries(changed.map((p) => [p.key, values[p.key]]))));
      setProblems({});
    } catch (e) {
      const found = problemsOf(e);
      setProblems(found);
      setError(Object.keys(found).length ? null : errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const discard = () => {
    setValues(data.values);
    setProblems({});
    setError(null);
  };

  return (
    <SettingsCard title={title} wide dirty={dirty} busy={busy} invalid={invalid} error={error} onDiscard={discard} onSave={() => void save()}>
      {params.map((p) => {
        const off = !canWrite || Boolean(p.enabled_when && values[p.enabled_when.key] !== p.enabled_when.value);
        const problem = problems[p.key] || undefined;
        if (unitKeys.has(p.key)) return null;  // birim, değerinin satırında
        if (p.unit_key) {
          const unit = params.find((x) => x.key === p.unit_key);
          const end = data.computed.fix_period_end;
          const same = values[p.key] === data.values[p.key] && values[p.unit_key] === data.values[p.unit_key];
          const v = values[p.key];
          return <UnitRow key={p.key} label={p.label} tip={p.hint} disabled={!canWrite} error={problem ?? problems[p.unit_key] ?? local(p)}
                          value={v === null || v === undefined ? null : Number(v)} onValue={(n) => set(p.key, n === null ? null : String(n))}
                          unit={values[p.unit_key] ?? ""} units={unit?.options ?? []} unitLabel={unit?.label ?? ""} onUnit={(u) => set(p.unit_key!, u)}
                          help={p.key === "FixPeriod" && same && end ? T.fixEnd(formatDate(serverDate(end))) : undefined} />;
        }
        if (p.kind === "bool") {
          return <SwitchRow key={p.key} label={p.label} tip={p.hint} checked={values[p.key] === YES} disabled={off} onToggle={(v) => set(p.key, v ? YES : NO)} />;
        }
        if (p.kind === "choice" && (p.options ?? []).length <= SEGMENT_MAX) {
          return <ChoiceRow key={p.key} label={p.label} tip={p.hint} options={p.options ?? []} value={values[p.key] ?? ""} error={problem}
                            onChange={(v) => canWrite && set(p.key, v)} />;
        }
        if (p.kind === "choice") {
          return <SelectField key={p.key} label={p.label} value={values[p.key] ?? ""} error={problem} disabled={!canWrite}
                              options={(p.options ?? []).map((o) => ({ value: o, label: o }))} onChange={(v) => set(p.key, v)} />;
        }
        const n = values[p.key];
        return <NumberField key={p.key} label={p.label} tip={p.hint} decimals={p.kind === "number" ? 2 : 0} disabled={!canWrite}
                            value={n === null || n === undefined ? null : Number(n)} error={problem ?? local(p)}
                            onChange={(v) => set(p.key, v === null ? null : String(v))} />;
      })}
    </SettingsCard>
  );
}

// ------------------------------------------------------------------ zaman: ufuk ve dönemler

interface BucketDraft { id: string; bucket_type: string; countText: string; span_unit: string }
let nextId = 0;
const asBucket = (r: BucketRow): BucketDraft => ({ id: `b${++nextId}`, bucket_type: r.bucket_type, countText: r.count === null ? "" : String(r.count), span_unit: r.span_unit });
const toRow = (r: BucketDraft): BucketRow => ({ bucket_type: r.bucket_type, count: parseTrNumber(r.countText), span_unit: r.span_unit });
const sameRows = (a: BucketRow[], b: BucketRow[]) => JSON.stringify(a) === JSON.stringify(b);
const PREVIEW_MS = 250;

function Horizon({ parts }: { parts: BucketPart[] }) {
  if (!parts.length) return null;
  return (
    <div className="sc-horizon" role="img" aria-label={T.horizon}>
      {parts.map((p, i) => (
        <div key={i} style={{ flexGrow: p.days, flexBasis: 0 }} title={`${formatDate(serverDate(p.start))} – ${formatDate(serverDate(p.end))}`}>
          {T.horizonPart(p.count ?? 0, T.units[p.span_unit] ?? p.span_unit, T.bucketAdjective[p.bucket_type] ?? p.bucket_type)}
        </div>
      ))}
    </div>
  );
}

const PERIOD_COLUMNS: GridColumn<Period>[] = [
  { key: "no", label: T.period, num: true, width: 6, render: (r) => <span className="sc-num">{r.no}</span> },
  { key: "start", label: T.start, width: 9, render: (r) => <span className="sc-num">{formatDate(serverDate(r.start))}</span> },
  { key: "end", label: T.end, width: 9, render: (r) => <span className="sc-num">{formatDate(serverDate(r.end))}</span> },
  { key: "bucket_type", label: T.bucketType, render: (r) => r.bucket_type },
  { key: "days", label: T.days, num: true, width: 8, render: (r) => <span className="sc-num">{r.days}</span> },
];

/** Hesaplanan dönemler (salt okunur): kısa hafta ve yarım ay burada görünür; taslak değişince kaydetmeden güncellenir. */
function PeriodList({ label, periods }: { label: string; periods: Period[] }) {
  if (!periods.length) return null;
  return (
    <section className="sc-settings-card sc-period-list" aria-label={label}>
      <EditGrid<Period> label={label} columns={PERIOD_COLUMNS} rows={periods} rowKey={(r) => String(r.no)} editable={false} />
    </section>
  );
}

function Buckets({ axis, label, periodsLabel, canWrite, onDirty }: {
  axis: Axis; label: string; periodsLabel: string; canWrite: boolean; onDirty(dirty: boolean): void;
}) {
  const api = useApi();
  const [saved, setSaved] = useState<BucketsData | null>(null);
  const [rows, setRows] = useState<BucketDraft[]>([]);
  const [parts, setParts] = useState<BucketPart[]>([]);
  const [periods, setPeriods] = useState<Period[]>([]);
  useEffect(() => () => onDirty(false), [onDirty]);  // tablo kapanınca (ör. raporlama ekseni yeniden "planla aynı") taslağı da kalkar
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [menu, setMenu] = useState<{ id: string; anchor: HTMLElement } | null>(null);
  const load = (d: BucketsData) => {
    setSaved(d);
    setRows(d.rows.map(asBucket));
    setParts(d.rows);
    setPeriods(d.periods);
    setProblems({});
  };
  useEffect(() => {
    const ctrl = new AbortController();
    api.buckets(axis, ctrl.signal).then(load).catch((e: unknown) => { if (!ctrl.signal.aborted) setError(errorText(e)); });
    return () => ctrl.abort();
  }, [axis]);

  const current = rows.map(toRow);
  const savedRows = useMemo(() => (saved?.rows ?? []).map((r) => ({ bucket_type: r.bucket_type, count: r.count, span_unit: r.span_unit })), [saved]);
  const dirty = saved !== null && !sameRows(current, savedRows);
  useEffect(() => onDirty(dirty), [dirty, onDirty]);

  // Taslak değişince tarihler ve şerit sunucudan (takvim kuralları tek yerde)
  const key = JSON.stringify(current);
  const first = useRef(true);
  useEffect(() => {
    if (!saved) return undefined;
    if (first.current) {
      first.current = false;
      return undefined;
    }
    if (!dirty) {
      setParts(saved.rows);
      setPeriods(saved.periods);
      setProblems({});
      return undefined;
    }
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      api.preview(axis, current, ctrl.signal).then((d) => {
        setParts(d.rows);
        setPeriods(d.periods);
        setProblems({});
      }).catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        setProblems(problemsOf(e));
        setParts([]);
        setPeriods([]);
      });
    }, PREVIEW_MS);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [key, saved]);  // eslint-disable-line react-hooks/exhaustive-deps

  const patch = (id: string, change: Partial<BucketDraft>) => setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...change } : r)));
  const add = () => setRows((rs) => {
    const last = rs[rs.length - 1];
    const type = last?.bucket_type ?? saved?.bucket_types[0] ?? "Gün";
    return [...rs, { id: `b${++nextId}`, bucket_type: type, countText: "1", span_unit: last ? last.span_unit : type }];
  });
  const remove = (id: string) => setRows((rs) => rs.filter((r) => r.id !== id));
  const move = (id: string, target: string, side: "before" | "after") => setRows((rs) => {
    const map = new Map(rs.map((r) => [r.id, r]));
    return dropId(rs.map((r) => r.id), id, target, side).map((x) => map.get(x)!);
  });
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      load(await api.saveBuckets(axis, current));
    } catch (e) {
      const found = problemsOf(e);
      setProblems(found);
      setError(Object.keys(found).length ? null : errorText(e));
    } finally {
      setBusy(false);
    }
  };

  if (!saved) return error ? <Alert tone="error">{error}</Alert> : null;
  const savedAt = (i: number) => savedRows[i];
  const problem = (i: number, field: string) => problems[`rows.${i + 1}.${field}`] || undefined;
  const index = (r: BucketDraft) => rows.findIndex((x) => x.id === r.id);
  const countProblem = (r: BucketDraft, i: number) => {
    const n = parseTrNumber(r.countText);
    return n === null || !Number.isInteger(n) || n < 1 ? T.countProblem : problem(i, "Count");
  };
  const date = (i: number, field: "start" | "end") => (parts[i] ? formatDate(serverDate(parts[i][field])) : "");
  const columns: GridColumn<BucketDraft>[] = [
    { key: "seq", label: T.seq, width: 5, render: (_r, i) => <GridSeq seq={i + 1} movable={canWrite} /> },
    { key: "bucket_type", label: T.bucketType, render: (r) => r.bucket_type,
      edit: { text: (r) => r.bucket_type, commit: (r, text) => patch(r.id, { bucket_type: text }), options: saved.bucket_types },
      changed: (r) => savedAt(index(r))?.bucket_type !== r.bucket_type, problem: (_r, i) => problem(i, "BucketType") },
    { key: "count", label: T.count, num: true, width: 7, render: (r) => <span className="sc-num">{r.countText}</span>,
      edit: { text: (r) => r.countText, commit: (r, text) => patch(r.id, { countText: text.trim() }) },
      changed: (r) => savedAt(index(r))?.count !== parseTrNumber(r.countText), problem: countProblem },
    { key: "span_unit", label: T.spanUnit, width: 9, render: (r) => r.span_unit,
      edit: { text: (r) => r.span_unit, commit: (r, text) => patch(r.id, { span_unit: text }), options: saved.span_units },
      changed: (r) => savedAt(index(r))?.span_unit !== r.span_unit, problem: (_r, i) => problem(i, "SpanUnit") },
    { key: "start", label: T.start, width: 8, render: (_r, i) => <span className="sc-num">{date(i, "start")}</span> },
    { key: "end", label: T.end, width: 8, render: (_r, i) => <span className="sc-num">{date(i, "end")}</span> },
    ...(canWrite ? [{ key: "menu", label: "", width: 3, cls: "sc-table-rowmenu", render: (r: BucketDraft, i: number) => (
      <button type="button" className="sc-table-filter-btn" aria-haspopup="menu" aria-label={T.rowMenu(i + 1)}
              onClick={(e) => setMenu({ id: r.id, anchor: e.currentTarget })}>
        <Ellipsis aria-hidden="true" />
      </button>
    ) } as GridColumn<BucketDraft>] : []),
  ];
  const invalid = rows.length === 0 || rows.some((r, i) => countProblem(r, i)) || Object.values(problems).some(Boolean);
  const menuRow = menu ? rows.findIndex((r) => r.id === menu.id) : -1;
  return (
    <div className="sc-settings-section sc-settings-section--grid">
      {canWrite && <div className="sc-grid-lead"><Button variant="primary" onClick={add}>{T.addRow}</Button></div>}
      <section className="sc-settings-card" aria-label={label}>
        <EditGrid<BucketDraft> label={label} columns={columns} rows={rows} rowKey={(r) => r.id} editable={canWrite} drag={{ can: () => true, move }} />
        <SettingsFoot dirty={dirty} busy={busy} invalid={invalid} onDiscard={() => load(saved)} onSave={() => void save()} />
      </section>
      <Horizon parts={parts} />
      <PeriodList label={periodsLabel} periods={periods} />
      {problems.rows && <Alert tone="risk">{problems.rows}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}
      {menu && menuRow >= 0 && (
        <RowPopMenu label={T.rowMenu(menuRow + 1)} anchor={menu.anchor} onClose={() => setMenu(null)}>
          <MenuItem label={T.remove} state={rows.length > 1 ? { allowed: true } : { allowed: false, reason: T.lastRow }}
                    onClick={() => { remove(menu.id); setMenu(null); }} />
        </RowPopMenu>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ ekran

export function Parameters() {
  const me = useAuth().me!;
  const api = useApi();
  const canWrite = can(me, 22, "write");
  const { search, pathname } = useLocation();
  const navigate = useNavigate();
  const [data, setData] = useState<ParametersData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dirtyOf, setDirtyOf] = useState<Record<string, boolean>>({});  // sayfadaki her form ve tablo kendi taslağını bildirir
  const dirty = Object.values(dirtyOf).some(Boolean);
  const [pending, setPending] = useState<{ sekme: string; bolum?: string } | null>(null);
  const [formKey, setFormKey] = useState(0);  // Vazgeçilerek geçişte taslak atılır
  const [draft, setDraft] = useState<ParamValues>({});
  const [stripEnd, setStripEnd] = useState<HTMLDivElement | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    api.read(ctrl.signal).then(setData).catch((e: unknown) => { if (!ctrl.signal.aborted) setError(errorText(e)); });
    return () => ctrl.abort();
  }, []);
  const onDirty = useCallback((d: boolean) => setDirtyOf((s) => (Boolean(s.form) === d ? s : { ...s, form: d })), []);
  const onGridDirty = useCallback((d: boolean) => setDirtyOf((s) => (Boolean(s.grid) === d ? s : { ...s, grid: d })), []);

  const params = new URLSearchParams(search);  // useSearchParams pakete dış bağlantılı uyarı metni getirir (internetsizlik testi)
  const section = data?.sections.find((s) => s.key === params.get("sekme")) ?? data?.sections[0];
  const sub: SubDef | undefined = section?.subs.find((s) => s.key === params.get("bolum")) ?? section?.subs[0];
  const show = (next: { sekme: string; bolum?: string }) => {
    setDirtyOf({});
    navigate(`${pathname}?${new URLSearchParams(next.bolum ? { sekme: next.sekme, bolum: next.bolum } : { sekme: next.sekme }).toString()}`, { replace: true });
  };
  const go = (next: { sekme: string; bolum?: string }) => {
    if (next.sekme === section?.key && (next.bolum ?? sub?.key) === sub?.key) return;
    if (dirty) setPending(next);
    else show(next);
  };

  if (!data || !section) return error ? <Alert tone="error">{error}</Alert> : null;
  const reportOwn = (draft.ReportAxisSameAsPlan ?? data.values.ReportAxisSameAsPlan) === NO;  // anahtar kaydetmeden tabloyu açar ve kapatır
  let body;
  if (section.table === "objectives") {
    body = <Objectives key={formKey} canWrite={canWrite} onDirty={onGridDirty} actions={stripEnd} />;
  } else if (sub?.table === "warnings") {   // Uyarı eşikleri (K-190): alt başlık = kategori; kaydetme kategori başına
    body = <WarningThresholds key={`${sub.key}:${formKey}`} category={sub.title} canWrite={can(me, 26, "write")} onDirty={onGridDirty} />;
  } else if (sub?.table === "buckets") {
    body = <Buckets key={`plan:${formKey}`} axis="plan" label={T.buckets} periodsLabel={T.periods} canWrite={canWrite} onDirty={onGridDirty} />;
  } else if (sub) {
    body = (
      <div className="sc-settings-stack">
        <ParamForm key={`${section.key}:${sub.key}:${formKey}`} title={sub.title} params={sub.params} data={data} canWrite={canWrite} onSaved={setData} onDirty={onDirty} onValues={setDraft} />
        {sub.table === "report" && reportOwn && <Buckets key={`rapor:${formKey}`} axis="rapor" label={T.reportBuckets} periodsLabel={T.reportPeriods} canWrite={canWrite} onDirty={onGridDirty} />}
      </div>
    );
  }
  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{T.title}</h1>
      </header>
      <div className="sc-section-switch sc-section-switch--actions">
        <OverflowTabs<string> label={T.sections} value={section.key} onChange={(key) => go({ sekme: key })}
                              options={data.sections.map((s) => ({ value: s.key, label: s.title }))} />
        {/* şerit standardı: tablo başlığının işlemleri sekmelerin hemen yanında, Vazgeç ve Kaydet sağda (Hedefler buraya çizer) */}
        <div className="sc-section-actions" ref={setStripEnd} />
      </div>
      <SettingsLayout label={section.title} sections={section.subs} current={sub?.key ?? ""} onSelect={(key) => go({ sekme: section.key, bolum: key })}>
        {body}
      </SettingsLayout>
      <UnsavedGuard dirty={dirty} />
      {pending && (
        <ConfirmDialog title={tr.table.unsavedTitle} message={tr.table.unsavedText} confirmLabel={tr.table.unsavedLeave} danger
                       onCancel={() => setPending(null)} onConfirm={() => { const next = pending; setPending(null); setFormKey((k) => k + 1); show(next); }} />
      )}
    </section>
  );
}
