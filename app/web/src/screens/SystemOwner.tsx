// Sistem ayarları (ekran 25, fonksiyon 96; K-104, K-105, docs/12): sürüm satırı, veri sözlüğü, şifre ve oturum ayarları.
// Veri sözlüğünde şimdilik yalnız etiket düzenlenir; öteki alanlar pasif form öğesi, 5.1'de yalnız aktifleşir.
import { Pencil } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { ApiError, emitNotice } from "../api/client";
import { appVersion } from "../auth/authApi";
import { tr } from "../i18n/tr";
import { DataTable, type RowMenuSpec } from "../table/DataTable";
import type { Row } from "../table/types";
import { Alert, Button, Card, Checkbox, Dialog, NumberField, Segment, SelectField, TextField } from "../ui";
import { type FieldDetail, type LoginPolicy, type PolicyKey, type PolicyValues, systemOwnerApi } from "./systemOwnerApi";

const T = tr.systemOwner;
const LABEL_MAX = 40;  // K-88

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : tr.users.failed);
const noop = () => undefined;
const listOptions = (values: string[], current: string | null) =>
  [...(current ? [] : [""]), ...values].map((value) => ({ value, label: value }));

function FieldDialog({ table, field, onClose, onDone }: { table: string; field: string; onClose(): void; onDone(): void }) {
  const [detail, setDetail] = useState<FieldDetail | null>(null);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    systemOwnerApi.field(table, field, ctrl.signal).then((d) => {
      setDetail(d);
      setLabel(d.label ?? "");
    }).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    return () => ctrl.abort();
  }, [table, field]);

  const trimmed = label.trim();
  const unchanged = trimmed === (detail?.label ?? "");
  // Kullanılan ek alanın etiketi siliniyor: alan görünümlerden düşer (K-104).
  const hides = Boolean(detail?.is_additional && detail.label && !trimmed && (detail.used_in_views > 0 || detail.used_in_rules > 0));
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await systemOwnerApi.setLabel(table, field, trimmed);
      onDone();
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };

  return (
    <Dialog title={T.fieldTitle} onClose={onClose}
            subtitle={<>{`${table} · ${field}`}{detail?.description && <span className="sc-dialog-subtitle-line">{detail.description}</span>}</>} onSubmit={submit} busy={busy}
            submitLabel={hides ? T.removeLabel : T.save} danger={hides} submitDisabled={!detail || unchanged} wide>
      {detail && (
        <>
          <div className="sc-field-rows">
            <TextField label={T.label} maxLength={LABEL_MAX} value={label} onChange={setLabel}
                       help={detail.is_additional ? T.additionalHelp : T.standardHelp(detail.standard_label)} />
            <SelectField label={T.fieldClass} disabled value={detail.field_class} onChange={noop}
                         options={listOptions(detail.options.field_class, detail.field_class)} />
            <SelectField label={T.valuePriority} disabled value={detail.value_priority ?? ""} onChange={noop}
                         options={listOptions(detail.options.value_priority, detail.value_priority)} />
            <Checkbox label={T.manualOverrides} disabled checked={Boolean(detail.manual_overrides)} onChange={noop} />
            <Checkbox label={T.editableInWorkspace} disabled checked={detail.editable_in_workspace} onChange={noop} />
            <Checkbox label={T.required} disabled checked={Boolean(detail.is_required)} onChange={noop} />
            <TextField label={T.defaultValue} disabled value={detail.default_value ?? ""} onChange={noop} />
          </div>
          {hides && <Alert tone="risk">{T.usedWarning(detail.used_in_views, detail.used_in_rules)}</Alert>}
        </>
      )}
      {error && <Alert tone="error">{error}</Alert>}
    </Dialog>
  );
}

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
      <DataTable list="field-definitions" rowMenu={rowMenu} reloadKey={reloadKey} />
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

const NUMBERS: { title: string; keys: PolicyKey[] }[] = [
  { title: T.passwordGroup, keys: ["PasswordMinLength", "PasswordHistoryCount", "PasswordMaxAgeDays"] },
  { title: T.sessionGroup, keys: ["LoginMaxFailedAttempts", "LoginLockMinutes", "SessionIdleMinutes", "SessionWarningMinutes"] },
];

function PolicyForm() {
  const [policy, setPolicy] = useState<LoginPolicy | null>(null);
  const [values, setValues] = useState<Partial<Record<PolicyKey, number | boolean | null>>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = (p: LoginPolicy) => {
    setPolicy(p);
    setValues(p.values);
  };
  useEffect(() => {
    const ctrl = new AbortController();
    systemOwnerApi.policy(ctrl.signal).then(load).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    return () => ctrl.abort();
  }, []);

  const problem = (key: PolicyKey): string | undefined => {
    const v = values[key];
    const limit = policy?.limits[key];
    if (limit && (typeof v !== "number" || v < limit.min || v > limit.max)) return T.limit(limit.min, limit.max);
    const idle = values.SessionIdleMinutes;
    if (key === "SessionWarningMinutes" && typeof v === "number" && typeof idle === "number" && v >= idle) return T.warningTooLong;
    return undefined;
  };
  const keys = Object.keys(policy?.values ?? {}) as PolicyKey[];
  const changed = keys.filter((k) => policy && values[k] !== policy.values[k]);
  const invalid = keys.some((k) => problem(k));

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      load(await systemOwnerApi.setPolicy(Object.fromEntries(changed.map((k) => [k, values[k]])) as Partial<PolicyValues>));
      emitNotice(T.policySaved);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  if (!policy) return error ? <Alert tone="error">{error}</Alert> : null;
  return (
    <div className="sc-settings-form">
      {NUMBERS.map((group) => (
        <Card key={group.title} title={group.title}>
          <div className="sc-field-rows">
            {group.keys.map((key) => (
              <NumberField key={key} label={T.policy[key]} value={values[key] as number | null} error={problem(key)}
                           onChange={(v) => setValues((s) => ({ ...s, [key]: v }))} />
            ))}
            {group.title === T.passwordGroup && (
              <Checkbox label={T.policy.PasswordRequireLetterAndDigit} checked={Boolean(values.PasswordRequireLetterAndDigit)}
                        onChange={(v) => setValues((s) => ({ ...s, PasswordRequireLetterAndDigit: v }))} />
            )}
          </div>
        </Card>
      ))}
      {error && <Alert tone="error">{error}</Alert>}
      <div>
        <Button variant="primary" busy={busy} disabled={!changed.length || invalid} onClick={() => void save()}>{T.save}</Button>
      </div>
    </div>
  );
}

type Section = "dictionary" | "policy";

export function SystemOwner() {
  const [section, setSection] = useState<Section>("dictionary");
  const [version, setVersion] = useState<string | null>(null);
  useEffect(() => {
    void appVersion().then(setVersion);
  }, []);
  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{T.title}</h1>
        {version && <p className="sc-muted">{T.version(version)}</p>}
      </header>
      <div className="sc-section-switch">
        <Segment<Section> label={T.sections} hideLabel value={section} onChange={setSection}
                 options={[{ value: "dictionary", label: T.dictionary }, { value: "policy", label: T.policyTitle }]} />
      </div>
      {section === "dictionary" ? <Dictionary /> : <PolicyForm />}
    </section>
  );
}
