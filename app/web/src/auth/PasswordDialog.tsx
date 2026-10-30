// Şifre değiştirme penceresi (mockup m24f-0739; K-98). İki yerde kullanılır:
// - zorunlu: ilk girişte, sıfırlamadan sonra ve süre dolunca; atlanamaz (Vazgeç ve Esc yok), arka plan bulanık;
// - isteğe bağlı: kullanıcı menüsündeki "Şifre değiştir" (Vazgeç'li).
// Kurallar yazarken denetlenir; düğme ancak hepsi sağlanınca açılır. Son kararı sunucu verir (422 kuralları işaretler).
import { useState } from "react";

import { ApiError } from "../api/client";
import { tr } from "../i18n/tr";
import { Alert, Dialog, TextField } from "../ui";
import { authApi, type Me } from "./authApi";
import { type PolicyRule, PolicyChecklist, type RuleState } from "./PolicyChecklist";

/** Türkçe harf duyarsız karşılaştırma (sunucudaki security._fold ile aynı): İ/I/ı/i aynı sayılır. */
export function fold(text: string): string {
  return text.replace(/[İIı]/g, "i").toLocaleLowerCase("tr");
}

export function policyRules(me: Me, next: string, repeat: string, serverFails: Set<string>): PolicyRule[] {
  const p = me.policy;
  const state = (ok: boolean, key: string): RuleState => (serverFails.has(key) || !ok ? "fail" : "ok");
  const rules: PolicyRule[] = [
    { key: "min_length", label: tr.auth.rules.minLength(p.min_length), state: state(next.length >= p.min_length, "min_length") },
  ];
  if (p.require_letter_and_digit) {
    rules.push({ key: "letter_and_digit", label: tr.auth.rules.letterAndDigit,
                 state: state(/\p{L}/u.test(next) && /\d/.test(next), "letter_and_digit") });
  }
  rules.push({ key: "contains_user_name", label: tr.auth.rules.noUserName,
               state: state(!next || !fold(next).includes(fold(me.user_name)), "contains_user_name") });
  if (p.history_count > 0) {
    rules.push({ key: "history", label: tr.auth.rules.history(p.history_count),
                 state: serverFails.has("history") ? "fail" : "pending" });
  }
  rules.push({ key: "match", label: tr.auth.rules.match, state: next !== "" && repeat === next ? "ok" : "fail" });
  return rules;
}

export function PasswordDialog({ me, forced, onDone, onCancel }: {
  me: Me;
  /** Zorunlu değişiklik: atlanamaz. */
  forced?: boolean;
  onDone(): void;
  onCancel?(): void;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [serverFails, setServerFails] = useState<Set<string>>(new Set());
  const [currentError, setCurrentError] = useState<string | null>(null);
  const [sameError, setSameError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const rules = policyRules(me, next, repeat, serverFails);
  const ready = current !== "" && rules.every((r) => r.state !== "fail");
  const temporary = forced && me.password_change_reason !== "Süre doldu";
  const reason = forced && me.password_change_reason ? tr.auth.reasons[me.password_change_reason] : null;

  const changeNext = (value: string) => {
    setNext(value);
    setServerFails(new Set());  // sunucunun "geçmişte var" kararı yeni şifreye taşınmaz
    setSameError(false);
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await authApi.changePassword(current, next);
      onDone();
    } catch (e) {
      if (e instanceof ApiError && e.code === "current_password_wrong") {
        setCurrentError(tr.auth.currentWrong);
      } else if (e instanceof ApiError && e.code === "password_policy") {
        const problems = new Set(e.details.map((d) => d.problem));
        setSameError(problems.has("same_as_current"));
        problems.delete("same_as_current");
        setServerFails(problems);
      } else if (!(e instanceof ApiError && e.status === 401)) {  // oturum bittiyse giriş sayfasına dönülür
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog title={forced ? tr.auth.setPassword : tr.auth.changePassword}
            subtitle={reason ? `${reason} · ${tr.auth.policySource}` : tr.auth.policySource}
            onClose={() => onCancel?.()} onSubmit={submit} busy={busy} submitDisabled={!ready}
            submitLabel={forced ? tr.auth.saveAndContinue : tr.auth.save} dismissible={!forced} blurred={forced}>
      <TextField label={temporary ? tr.auth.temporaryPassword : tr.auth.currentPassword} type="password"
                 autoComplete="current-password" value={current} error={currentError ?? undefined}
                 onChange={(v) => { setCurrent(v); setCurrentError(null); }} />
      <TextField label={tr.auth.newPassword} type="password" autoComplete="new-password" value={next}
                 error={sameError ? tr.auth.sameAsCurrent : undefined} onChange={changeNext} />
      <TextField label={tr.auth.repeatPassword} type="password" autoComplete="new-password" value={repeat}
                 error={repeat && repeat !== next ? tr.auth.mismatch : undefined} onChange={setRepeat} />
      <PolicyChecklist rules={rules} />
      {error && <Alert tone="error">{error}</Alert>}
    </Dialog>
  );
}
