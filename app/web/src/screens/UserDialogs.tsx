// Kullanıcılar ekranının pencereleri (docs/12 "Kullanıcılar" ve "Arayüz metni"; K-101): ekle, geçici şifre, rol, ad soyad,
// onaylar. Geçici şifre yalnız pencerenin prop'unda durur; pencere kapanınca hiçbir yerde kalmaz.
import { type ReactNode, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ROLES, SYSTEM_OWNER } from "../auth/permissions";
import { tr } from "../i18n/tr";
import { Alert, Button, Dialog, SelectField, TextField } from "../ui";
import { copyText, type TemporaryPassword, USER_NAME_PATTERN, type UserDetail, type UserRecord, usersApi } from "./usersApi";

const T = tr.users;

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : T.failed);

/** "ad soyad · kullanıcı adı" (ad soyad boş olabilir). */
export const whoOf = (user: UserRecord) => [user.full_name, user.user_name].filter(Boolean).join(" · ");
export const nameOf = (user: UserRecord) => user.full_name || user.user_name;

export function AddUserDialog({ onClose, onCreated }: { onClose(): void; onCreated(out: TemporaryPassword): void }) {
  const me = useAuth().me!;
  const roles = ROLES.filter((r) => r !== SYSTEM_OWNER || me.role === SYSTEM_OWNER);
  const [fullName, setFullName] = useState("");
  const [userName, setUserName] = useState("");
  const [role, setRole] = useState("End user");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [taken, setTaken] = useState<{ name: string; suggestion: string | null } | null>(null);

  const nameValid = USER_NAME_PATTERN.test(userName);
  const nameError = taken?.name === userName ? T.nameTaken
    : userName && !nameValid ? T.nameFormat : undefined;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      onCreated(await usersApi.create({ full_name: fullName.trim(), user_name: userName, role }));
    } catch (e) {
      if (e instanceof ApiError && e.code === "user_name_taken") {
        setTaken({ name: userName, suggestion: e.details[0]?.suggestion ?? null });
      } else {
        setError(errorText(e));
      }
      setBusy(false);
    }
  };

  return (
    <Dialog title={T.addTitle} onClose={onClose} onSubmit={submit} submitLabel={T.create} busy={busy}
            submitDisabled={!fullName.trim() || !nameValid || taken?.name === userName} wide>
      <div className="sc-form-row">
        <TextField label={T.fullName} required maxLength={150} value={fullName} onChange={setFullName} />
        <div>
          <TextField label={T.userName} required maxLength={60} autoComplete="off" spellCheck={false} value={userName}
                     help={T.userNameHelp} error={nameError} onChange={(v) => setUserName(v.trim().toLowerCase())} />
          {taken?.name === userName && taken.suggestion && (
            <Button size="sm" variant="ghost" onClick={() => setUserName(taken.suggestion!)}>{T.useSuggestion(taken.suggestion)}</Button>
          )}
        </div>
      </div>
      <SelectField label={T.role} value={role} onChange={setRole} help={T.scopes[role]}
                   options={roles.map((r) => ({ value: r, label: r }))} />
      {role === SYSTEM_OWNER && <Alert tone="risk">{T.ownerWarning}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}
    </Dialog>
  );
}

/** Yalnız "Kapat" ile kapanır (K-101): şifre bir kez gösterilir, yanlışlıkla Esc'le kaybolmasın. */
export function TemporaryPasswordDialog({ result, kind, onClose }: {
  result: TemporaryPassword; kind: "created" | "reset"; onClose(): void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [copied, setCopied] = useState<boolean | null>(null);
  const { user, temporary_password: password } = result;
  const copy = async () => setCopied(await copyText(password, input.current));

  return (
    <Dialog title={kind === "created" ? T.createdTitle : T.resetDoneTitle} subtitle={`${whoOf(user)} · ${user.role}`}
            onClose={onClose} onSubmit={onClose} submitLabel={tr.ui.close} dismissible={false}>
      <span className="sc-field-label" id="sc-temp-password">{T.tempPassword}</span>
      <div className="sc-temp-password">
        <input ref={input} className="sc-input sc-num" readOnly value={password} autoComplete="off" spellCheck={false}
               aria-labelledby="sc-temp-password" onFocus={(e) => e.currentTarget.select()} />
        <Button variant="secondary" onClick={() => void copy()}>{copied === null ? T.copy : copied ? T.copied : T.copyFailed}</Button>
      </div>
      <p>{T.onceOnly}</p>
    </Dialog>
  );
}

export function RoleDialog({ detail, onClose, onDone }: { detail: UserDetail; onClose(): void; onDone(role: string): void }) {
  const { user } = detail;
  const [role, setRole] = useState(user.role);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await usersApi.changeRole(user.id, role);
      onDone(role);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };
  return (
    <Dialog title={T.roleTitle} subtitle={whoOf(user)} onClose={onClose} onSubmit={submit} submitLabel={T.roleSubmit} busy={busy}
            submitDisabled={role === user.role}>
      <SelectField label={T.newRole} value={role} onChange={setRole} help={T.scopes[role]}
                   options={detail.assignable_roles.map((r) => ({ value: r, label: r }))} />
      {role === SYSTEM_OWNER && <Alert tone="risk">{T.ownerWarning}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}
    </Dialog>
  );
}

export function NameDialog({ detail, onClose, onDone }: { detail: UserDetail; onClose(): void; onDone(): void }) {
  const { user } = detail;
  const [fullName, setFullName] = useState(user.full_name ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await usersApi.changeName(user.id, fullName.trim());
      onDone();
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };
  return (
    <Dialog title={T.nameTitle} subtitle={user.user_name} onClose={onClose} onSubmit={submit} submitLabel={T.save} busy={busy}
            submitDisabled={!fullName.trim() || fullName.trim() === user.full_name}>
      <TextField label={T.fullName} required maxLength={150} value={fullName} onChange={setFullName} />
      {error && <Alert tone="error">{error}</Alert>}
    </Dialog>
  );
}

/** Onay penceresi: işlem burada çalışır; hata pencerede kalır (menü açılalı durum değişmiş olabilir). */
export function ActionDialog<R>({ title, submitLabel, danger, run, onClose, onDone, children }: {
  title: string; submitLabel: string; danger?: boolean; run(): Promise<R>; onClose(): void; onDone(out: R): void; children: ReactNode;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      onDone(await run());
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };
  return (
    <Dialog title={title} onClose={onClose} onSubmit={submit} submitLabel={submitLabel} busy={busy} danger={danger}>
      <p className="sc-dialog-message">{children}</p>
      {error && <Alert tone="error">{error}</Alert>}
    </Dialog>
  );
}
