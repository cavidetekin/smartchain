// Sistem ayarları (ekran 25, fonksiyon 96 ve 92; K-104, K-105, K-164, docs/12): sürüm satırı; sekmeler Veri sözlüğü · Giriş ve oturum · Sistem sağlığı ·
// Zamanlanmış işler. Ayar ekranı standardı: birden çok bölümlü sekmede solda alt menü, sıkı form, bölüm şeridinde Vazgeç ve Kaydet.
// Veri sözlüğünde şimdilik yalnız etiket düzenlenir; öteki alanlar pasif form öğesi, 5.1'de yalnız aktifleşir.
import { Pencil } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { ApiError, emitNotice } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { tr } from "../i18n/tr";
import { SwitchCell } from "../table/CellEditors";
import { DataTable, type FieldHints, type RowMenuSpec } from "../table/DataTable";
import { UnsavedGuard } from "../table/useTableEdits";
import type { Row } from "../table/types";
import { Alert, Button, Checkbox, ConfirmDialog, Dialog, NumberField, Segment, SelectField, TextField, Tooltip } from "../ui";
import { ScheduledJobs } from "./ScheduledJobs";
import { type FieldDetail, type PolicyValues, systemOwnerApi } from "./systemOwnerApi";

const T = tr.systemOwner;
const LABEL_MAX = 40;  // K-88

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : tr.users.failed);
const noop = () => undefined;
const listOptions = (values: string[], current: string | null) =>
  [...(current ? [] : [""]), ...values].map((value) => ({ value, label: value }));

function FieldDialog({ table, field, onClose, onDone }: { table: string; field: string; onClose(): void; onDone(): void }) {
  const [detail, setDetail] = useState<FieldDetail | null>(null);
  const [label, setLabel] = useState("");
  const [manual, setManual] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    systemOwnerApi.field(table, field, ctrl.signal).then((d) => {
      setDetail(d);
      setLabel(d.label ?? "");
      setManual(Boolean(d.manual_overrides));
    }).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    return () => ctrl.abort();
  }, [table, field]);

  const trimmed = label.trim();
  const labelChanged = trimmed !== (detail?.label ?? "");
  const manualChanged = manual !== Boolean(detail?.manual_overrides);
  const unchanged = !labelChanged && !manualChanged;
  // Manuel kapanıyor ve manuel değer var: onayla kalkar (K-170)
  const removesManual = Boolean(detail && manualChanged && !manual && detail.manual_count > 0);
  // Kullanılan ek alanın etiketi siliniyor: alan görünümlerden düşer (K-104).
  const hides = Boolean(detail?.is_additional && detail.label && !trimmed && (detail.used_in_views > 0 || detail.used_in_rules > 0));
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      if (labelChanged) await systemOwnerApi.setLabel(table, field, trimmed);
      if (manualChanged) await systemOwnerApi.setManual(table, field, manual, removesManual);
      onDone();
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };

  return (
    <Dialog title={T.fieldTitle} onClose={onClose}
            subtitle={<>{`${table} · ${field}`}{detail?.description && <span className="sc-dialog-subtitle-line">{detail.description}</span>}</>} onSubmit={submit} busy={busy}
            submitLabel={hides ? T.removeLabel : removesManual ? T.removeManual : T.save} danger={hides || removesManual} submitDisabled={!detail || unchanged} wide>
      {detail && (
        <>
          <div className="sc-field-rows">
            <TextField label={T.label} maxLength={LABEL_MAX} value={label} onChange={setLabel}
                       help={detail.is_additional ? T.additionalHelp : T.standardHelp(detail.standard_label)} />
            <SelectField label={T.fieldClass} disabled value={detail.field_class} onChange={noop}
                         options={listOptions(detail.options.field_class, detail.field_class)} />
            <Tooltip content={detail.manual_reason}>
              <Checkbox label={T.manualOverrides} disabled={Boolean(detail.manual_reason)} checked={manual} onChange={setManual} />
            </Tooltip>
            <Checkbox label={T.editableInWorkspace} disabled checked={detail.editable_in_workspace} onChange={noop} />
            <Checkbox label={T.required} disabled checked={Boolean(detail.is_required)} onChange={noop} />
            <TextField label={T.ifEmpty} disabled value={detail.if_empty ?? ""} onChange={noop} />
          </div>
          {hides && <Alert tone="risk">{T.usedWarning(detail.used_in_views, detail.used_in_rules)}</Alert>}
          {removesManual && <Alert tone="risk">{T.manualRemoveWarning(detail.manual_count)}</Alert>}
        </>
      )}
      {error && <Alert tone="error">{error}</Alert>}
    </Dialog>
  );
}

/** Tablo ekrana sığar (K-166 görsel kontrol): varsayılan genişliklerle 10 kolon 1440 px'te taşıyordu. */
const DICTIONARY_HINTS: FieldHints = { TableName: { width: 11 }, FieldName: { width: 12 }, DisplayLabel: { width: 12 }, FieldClass: { width: 8 },
  ValuePriority: { width: 8 }, ManualOverrides: { width: 6 }, EditableInWorkspace: { width: 6 }, IsRequired: { width: 6 }, IfEmpty: { width: 9 }, IsAdditional: { width: 6 } };

function Dictionary() {
  const [reloadKey, setReloadKey] = useState(0);
  const [open, setOpen] = useState<{ table: string; field: string } | null>(null);
  const rowMenu: RowMenuSpec = useMemo(() => ({
    icon: Pencil,
    label: (row: Row) => T.editField(String(row.TableName), String(row.FieldName)),
    onOpen: (row: Row) => setOpen({ table: String(row.TableName), field: String(row.FieldName) }),
  }), []);
  return (
    <>
      <DataTable list="field-definitions" rowMenu={rowMenu} reloadKey={reloadKey} fieldHints={DICTIONARY_HINTS} />
      {open && (
        <FieldDialog {...open} onClose={() => setOpen(null)} onDone={() => {
          emitNotice(T.labelSaved(`${open.table}.${open.field}`));
          setReloadKey((n) => n + 1);
          setOpen(null);
        }} />
      )}
    </>
  );
}

interface FormSection {
  key: string;
  title: string;
  keys: string[];
  checkbox?: string;
}

type FormValues = Record<string, number | boolean | null>;

interface FormData {
  values: Record<string, number | boolean | null>;
  limits: Partial<Record<string, { min: number; max: number }>>;
  /** Varsayılanı olmayan, boş bırakılabilen ayarlar (ör. ham verinin saklama süresi, K-156). */
  optional?: string[];
}

/** Kaydedilmemiş değişiklikle bölüm ya da sekme değişirken onay (K-132, K-164). */
function UnsavedConfirm({ onStay, onLeave }: { onStay(): void; onLeave(): void }) {
  return <ConfirmDialog title={tr.table.unsavedTitle} message={tr.table.unsavedText} confirmLabel={tr.table.unsavedLeave} onCancel={onStay} onConfirm={onLeave} danger />;
}

/** Ayar sekmesi (K-105, K-106, K-164): birden çok bölümde solda alt menü, sağda yalnız seçili bölüm; bölüm şeridinde ad, Vazgeç ve Kaydet.
 *  Kayıtlı olmayan ayar varsayılanıyla gelir; yalnız seçili bölümün değişenleri gönderilir. Form içeriği kadar geniştir. */
function SettingsTab({ label, sections, labels, read, write, crossCheck, onDirty }: {
  label: string;
  sections: FormSection[];
  labels: Record<string, string>;
  read(signal: AbortSignal): Promise<FormData>;
  write(changes: Record<string, number | boolean | null>): Promise<FormData>;
  crossCheck?(key: string, values: FormValues): string | undefined;
  onDirty(dirty: boolean): void;
}) {
  const [data, setData] = useState<FormData | null>(null);
  const [values, setValues] = useState<FormValues>({});
  const [current, setCurrent] = useState(sections[0].key);
  const [pending, setPending] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = (d: FormData) => {
    setData(d);
    setValues(d.values);
  };
  useEffect(() => {
    const ctrl = new AbortController();
    read(ctrl.signal).then(load).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    return () => ctrl.abort();
  }, [read]);

  const section = sections.find((s) => s.key === current) ?? sections[0];
  const keys = [...section.keys, ...(section.checkbox ? [section.checkbox] : [])];
  const problem = (key: string): string | undefined => {
    const v = values[key];
    if (v === null && data?.optional?.includes(key)) return undefined;
    const limit = data?.limits[key];
    if (limit && (typeof v !== "number" || v < limit.min || v > limit.max)) return T.limit(limit.min, limit.max);
    return crossCheck?.(key, values);
  };
  const changed = keys.filter((k) => data && values[k] !== data.values[k]);
  const invalid = keys.some((k) => problem(k));
  const dirty = changed.length > 0;
  useEffect(() => onDirty(dirty), [dirty, onDirty]);

  const discard = () => data && setValues(data.values);
  const go = (key: string) => {
    if (key === current) return;
    if (dirty) setPending(key);
    else setCurrent(key);
  };
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      load(await write(Object.fromEntries(changed.map((k) => [k, values[k]]))));
      emitNotice(T.policySaved);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  if (!data) return error ? <Alert tone="error">{error}</Alert> : null;
  const form = (
    <div className="sc-settings-section">
      <section className="sc-settings-card" aria-label={section.title}>
        <div className="sc-field-rows">
          {section.keys.map((key) => (
            <NumberField key={key} label={labels[key]} value={values[key] as number | null} error={problem(key)}
                         tip={data.optional?.includes(key) ? T.optionalEmpty : undefined}
                         onChange={(v) => setValues((s) => ({ ...s, [key]: v }))} />
          ))}
          {section.checkbox && (  // Evet/Hayır ayarı anahtardır (K-165)
            <div className="sc-field sc-switch-row">
              <span className="sc-field-label">{labels[section.checkbox]}</span>
              <SwitchCell label={labels[section.checkbox]} checked={Boolean(values[section.checkbox])} editable size="md"
                          onToggle={(v) => setValues((s) => ({ ...s, [section.checkbox as string]: v }))} />
            </div>
          )}
        </div>
        <footer className="sc-settings-foot">
          <Button variant="ghost" disabled={!dirty || busy} onClick={discard}>{T.discard}</Button>
          <Button variant="primary" busy={busy} disabled={!dirty || invalid} onClick={() => void save()}>{T.save}</Button>
        </footer>
      </section>
      {error && <Alert tone="error">{error}</Alert>}
    </div>
  );
  return (
    <>
      {sections.length > 1 ? (
        <div className="sc-settings-body">
          <nav className="sc-settings-nav" aria-label={T.subMenu(label)}>
            {sections.map((s) => (
              <button key={s.key} type="button" aria-current={s.key === section.key ? "true" : undefined} onClick={() => go(s.key)}>{s.title}</button>
            ))}
          </nav>
          {form}
        </div>
      ) : form}
      {pending && <UnsavedConfirm onStay={() => setPending(null)} onLeave={() => { discard(); setCurrent(pending); setPending(null); }} />}
    </>
  );
}

const POLICY_SECTIONS: FormSection[] = [
  { key: "password", title: T.passwordSection, keys: ["PasswordMinLength", "PasswordHistoryCount", "PasswordMaxAgeDays"], checkbox: "PasswordRequireLetterAndDigit" },
  { key: "session", title: T.sessionSection, keys: ["LoginMaxFailedAttempts", "LoginLockMinutes", "SessionIdleMinutes", "SessionWarningMinutes"] },
];
const HEALTH_SECTIONS: FormSection[] = [
  { key: "monitoring", title: T.healthGroup, keys: ["DiskWarnPercent", "QueueWaitWarnMinutes", "SystemEventRetentionDays"] },
  { key: "import", title: T.importGroup, keys: ["ImportSyncMaxMb", "ImportMaxMb", "ImportMaxRows"] },
  { key: "cleanup", title: T.cleanupGroup, keys: ["RawDataRetentionDays"] },
];

const warningShorter = (key: string, values: FormValues) => {
  const [warning, idle] = [values.SessionWarningMinutes, values.SessionIdleMinutes];
  return key === "SessionWarningMinutes" && typeof warning === "number" && typeof idle === "number" && warning >= idle ? T.warningTooLong : undefined;
};
const writePolicy = (changes: FormValues) => systemOwnerApi.setPolicy(changes as Partial<PolicyValues>);

type Tab = "dictionary" | "policy" | "health" | "flows";
/** Sekme, adresteki adı ve yetkisi (K-164): yetkisi olmayan sekme gösterilmez; Admin yalnız Zamanlanmış işler'i görür. */
const TABS: { value: Tab; slug: string; label: string; fn: number }[] = [
  { value: "dictionary", slug: "veri-sozlugu", label: T.dictionary, fn: 96 },
  { value: "policy", slug: "giris-ve-oturum", label: T.policyTitle, fn: 96 },
  { value: "health", slug: "sistem-sagligi", label: T.healthTitle, fn: 96 },
  { value: "flows", slug: "zamanlanmis-isler", label: T.flowsTab, fn: 92 },
];

export function SystemOwner() {
  const me = useAuth().me!;
  const tabs = TABS.filter((t) => can(me, t.fn));
  const { search, pathname } = useLocation();
  const navigate = useNavigate();
  const params = new URLSearchParams(search);  // useSearchParams pakete dış bağlantılı uyarı metni getirir (internetsizlik testi)
  const setParams = (next: Record<string, string>, opts: { replace: boolean }) => navigate(`${pathname}?${new URLSearchParams(next).toString()}`, opts);
  const fromUrl = TABS.find((t) => t.slug === params.get("sekme"))?.value;
  const [tab, setTab] = useState<Tab>(tabs.find((t) => t.value === fromUrl)?.value ?? tabs[0]?.value ?? "dictionary");
  const [pending, setPending] = useState<Tab | null>(null);
  const [dirty, setDirty] = useState(false);
  const initialFlow = Number(params.get("is")) || null;
  useEffect(() => {  // çipteki "Geçmiş" başka sekmedeyken de bu sekmeye getirir
    if (fromUrl && tabs.some((t) => t.value === fromUrl)) setTab(fromUrl);
  }, [fromUrl]);  // eslint-disable-line react-hooks/exhaustive-deps
  const choose = (next: Tab) => {
    if (next === tab) return;
    if (dirty) {
      setPending(next);
      return;
    }
    setTab(next);
    setParams({ sekme: TABS.find((t) => t.value === next)!.slug }, { replace: true });
  };
  const leave = () => {
    const next = pending!;
    setPending(null);
    setDirty(false);
    setTab(next);
    setParams({ sekme: TABS.find((t) => t.value === next)!.slug }, { replace: true });
  };
  const onDirty = useCallback((d: boolean) => setDirty(d), []);

  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{T.title}</h1>
      </header>
      {tabs.length > 1 && (
        <div className="sc-section-switch">
          <Segment<Tab> label={T.sections} hideLabel value={tab} onChange={choose} options={tabs.map((t) => ({ value: t.value, label: t.label }))} />
        </div>
      )}
      {tab === "dictionary" && <Dictionary />}
      {tab === "policy" && <SettingsTab key="policy" label={T.policyTitle} sections={POLICY_SECTIONS} labels={T.policy} read={systemOwnerApi.policy} write={writePolicy}
                                        crossCheck={warningShorter} onDirty={onDirty} />}
      {tab === "health" && <SettingsTab key="health" label={T.healthTitle} sections={HEALTH_SECTIONS} labels={T.health} read={systemOwnerApi.healthSettings}
                                        write={systemOwnerApi.setHealthSettings} onDirty={onDirty} />}
      {tab === "flows" && <ScheduledJobs initialFlow={initialFlow} onDirty={onDirty} />}
      <UnsavedGuard dirty={dirty} />
      {pending && <UnsavedConfirm onStay={() => setPending(null)} onLeave={leave} />}
    </section>
  );
}
