// Tablo içi düzenleme (K-132, docs/12): taslak ekranda kalır, tablonun sağ üstündeki Kaydet toplu yazar, Vazgeç geri alır.
// Kaydedilmemiş değişiklikle ekrandan çıkılırsa ya da sayfa kapatılırsa uyarı çıkar. Sonraki bütün tablo içi düzenlemeler bunu kullanır.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useBlocker } from "react-router";

import { tr } from "../i18n/tr";
import { Button, ConfirmDialog } from "../ui";

type Drafts = Record<string, Record<string, unknown>>;

export function useTableEdits() {
  const [drafts, setDrafts] = useState<Drafts>({});

  const set = useCallback((key: string, field: string, value: unknown, saved: unknown) => {
    setDrafts((all) => {
      const row = { ...all[key] };
      if (value === saved) delete row[field];
      else row[field] = value;
      const next = { ...all };
      if (Object.keys(row).length) next[key] = row;
      else delete next[key];
      return next;
    });
  }, []);
  const discard = useCallback(() => setDrafts({}), []);

  return useMemo(() => ({
    drafts,
    dirty: Object.keys(drafts).length > 0,
    get: <T,>(key: string, field: string, saved: T): T => (drafts[key] && field in drafts[key] ? drafts[key][field] as T : saved),
    changed: (key: string, field: string) => Boolean(drafts[key] && field in drafts[key]),
    set,
    discard,
  }), [drafts, set, discard]);
}

export function EditBar({ dirty, busy, onSave, onDiscard, disabledReason }: {
  dirty: boolean; busy?: boolean; onSave(): void; onDiscard(): void;
  /** Kayıt şimdi yapılamıyorsa nedeni (ör. zamanlanmış akış sürüyor, K-163). */
  disabledReason?: string | null;
}) {
  if (!dirty) return null;
  const T = tr.table;
  return (
    <span className="sc-edit-bar">
      <Button size="sm" variant="primary" busy={busy} disabledReason={disabledReason ?? null} onClick={onSave}>{T.editSave}</Button>
      <Button size="sm" disabled={busy} onClick={onDiscard}>{T.editDiscard}</Button>
    </span>
  );
}

export function UnsavedGuard({ dirty }: { dirty: boolean }) {
  const T = tr.table;
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirty && currentLocation.pathname !== nextLocation.pathname);

  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();  // tarayıcının kendi uyarısı: yenileme, sekme kapatma
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  if (blocker.state !== "blocked") return null;
  return <ConfirmDialog title={T.unsavedTitle} message={T.unsavedText} confirmLabel={T.unsavedLeave} danger onCancel={() => blocker.reset()} onConfirm={() => blocker.proceed()} />;
}
