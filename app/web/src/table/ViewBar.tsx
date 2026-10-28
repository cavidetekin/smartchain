// Kayıtlı görünüm (U-9, K-89): seçici, kaydedilmemiş işareti, Kaydet / Farklı kaydet, varsayılan yap, sil.
// Görünümler veritabanında; kullanıcı A-36 gereği şimdilik user_id ile. Açılışta kullanıcının varsayılanı uygulanır.
import { Ellipsis } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { tr } from "../i18n/tr";
import { Button, Checkbox, ConfirmDialog, Dialog, TextField } from "../ui";
import { useFloating } from "../ui/popover";
import { listApi, type ListColumn, type SavedView, type ViewDefinition } from "./types";
import { fromDefinition, isDirty, standardState, type TableState, toDefinition } from "./viewState";

const T = tr.table;

export interface Views {
  ready: boolean;
  error: string | null;
  views: SavedView[];
  defaultId: number | null;
  currentId: number | null;
  baseline: ViewDefinition | null;
  warnings: string[];
  select(id: number | null): void;
  save(state: TableState): Promise<void>;
  saveAs(state: TableState, name: string, shared: boolean): Promise<void>;
  remove(): Promise<void>;
  toggleDefault(): Promise<void>;
  dismissWarnings(): void;
}

/** Görünümleri okur, açılışta varsayılanı uygular; seçim ve kayıt işlemleri tablo durumunu (apply) günceller. */
export function useViews(list: string, userId: number, columns: ListColumn[] | null,
                         apply: (s: TableState) => void): Views {
  const api = useMemo(() => listApi(list), [list]);
  const [views, setViews] = useState<SavedView[]>([]);
  const [defaultId, setDefaultId] = useState<number | null>(null);
  const [currentId, setCurrentId] = useState<number | null>(null);
  const [baseline, setBaseline] = useState<ViewDefinition | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const applyRef = useRef(apply);
  applyRef.current = apply;

  const use = useCallback((view: SavedView | null) => {
    if (!columns) return;
    const state = view ? fromDefinition(view.definition, columns) : standardState(columns);
    applyRef.current(state);
    setCurrentId(view?.id ?? null);
    setBaseline(toDefinition(state));
    setWarnings(view?.warnings ?? []);
  }, [columns]);

  useEffect(() => {
    if (!columns) return;
    const ctrl = new AbortController();
    api.views(userId, ctrl.signal)
      .then((r) => {
        setViews(r.views);
        setDefaultId(r.default_view_id);
        use(r.views.find((v) => v.id === r.default_view_id) ?? null);
        setReady(true);
      })
      .catch(() => {
        if (ctrl.signal.aborted) return;
        setError(T.viewsError);
        use(null);
        setReady(true);
      });
    return () => ctrl.abort();
  }, [api, userId, columns, use]);

  const current = views.find((v) => v.id === currentId) ?? null;
  return {
    ready, error, views, defaultId, currentId, baseline, warnings,
    select: (id) => use(views.find((v) => v.id === id) ?? null),
    async save(state) {
      if (!current) return;
      const saved = await api.updateView(userId, current.id, { definition: toDefinition(state) });
      setViews((vs) => vs.map((v) => (v.id === saved.id ? saved : v)));
      setBaseline(toDefinition(state));
    },
    async saveAs(state, name, shared) {
      const saved = await api.createView(userId, { name, is_shared: shared, definition: toDefinition(state) });
      setViews((vs) => [...vs, saved].sort((a, b) => a.name.localeCompare(b.name, "tr")));
      setCurrentId(saved.id);
      setBaseline(toDefinition(state));
      setWarnings([]);
    },
    async remove() {
      if (!current) return;
      await api.deleteView(userId, current.id);
      setViews((vs) => vs.filter((v) => v.id !== current.id));
      if (defaultId === current.id) setDefaultId(null);
      use(null);
    },
    async toggleDefault() {
      const next = defaultId === currentId ? null : currentId;
      await api.setDefaultView(userId, next);
      setDefaultId(next);
    },
    dismissWarnings: () => setWarnings([]),
  };
}

export function ViewBar({ views, state }: { views: Views; state: TableState }) {
  const [confirm, setConfirm] = useState<{ kind: "switch"; id: number | null } | { kind: "delete" } | null>(null);
  const [saveAs, setSaveAs] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const menuPopRef = useRef<HTMLDivElement>(null);
  useFloating(menuPopRef, menuButtonRef, menuOpen);
  const current = views.views.find((v) => v.id === views.currentId) ?? null;
  const dirty = views.baseline ? isDirty(state, views.baseline) : false;

  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [menuOpen]);

  const choose = (raw: string) => {
    const id = raw ? Number(raw) : null;
    if (dirty) setConfirm({ kind: "switch", id });
    else views.select(id);
  };
  const label = (v: SavedView) => `${v.name}${v.is_owner ? "" : ` · ${T.sharedBy(v.owner_name)}`}${v.id === views.defaultId ? ` (${T.defaultMark})` : ""}`;

  return (
    <div className="sc-viewbar">
      <select className="sc-input sc-select sc-viewbar-select" aria-label={T.view} value={views.currentId ?? ""}
              onChange={(e) => choose(e.target.value)}>
        <option value="">{T.standard}{views.defaultId === null ? ` (${T.defaultMark})` : ""}</option>
        {views.views.map((v) => <option key={v.id} value={v.id}>{label(v)}</option>)}
      </select>
      {dirty && (
        <span className="sc-viewbar-unsaved" title={T.unsaved}>
          <span className="sc-viewbar-dirty" role="img" aria-label={T.unsaved}>•</span>
          <span className="sc-muted">{T.unsavedShort}</span>
        </span>
      )}
      {dirty && current?.is_owner && <Button size="sm" variant="primary" onClick={() => views.save(state)}>{T.save}</Button>}
      <Button size="sm" variant="ghost" onClick={() => setSaveAs(true)}>{T.saveAs}</Button>
      {current && (
        <div className="sc-table-anchor" ref={menuRef}>
          <button type="button" className="sc-tool-btn" ref={menuButtonRef} aria-label={T.viewMenu} aria-haspopup="menu" aria-expanded={menuOpen}
                  onClick={() => setMenuOpen((o) => !o)}><Ellipsis aria-hidden="true" /></button>
          {menuOpen && (
            <div ref={menuPopRef} className="sc-table-pop sc-popmenu sc-viewbar-menu sc-floating" role="menu" aria-label={T.viewMenu}>
              <button type="button" role="menuitem" className="sc-popmenu-item"
                      onClick={() => { setMenuOpen(false); views.toggleDefault(); }}>
                {views.defaultId === current.id ? T.removeDefault : T.makeDefault}
              </button>
              {current.is_owner && (
                <button type="button" role="menuitem" className="sc-popmenu-item"
                        onClick={() => { setMenuOpen(false); setConfirm({ kind: "delete" }); }}>{T.deleteView}</button>
              )}
            </div>
          )}
        </div>
      )}
      {saveAs && <SaveAsDialog onClose={() => setSaveAs(false)} onSave={(name, shared) => views.saveAs(state, name, shared)} />}
      {confirm?.kind === "switch" && (
        <ConfirmDialog title={T.switchTitle} message={T.switchMessage} confirmLabel={T.switchConfirm}
                       onCancel={() => setConfirm(null)}
                       onConfirm={() => { views.select(confirm.id); setConfirm(null); }} />
      )}
      {confirm?.kind === "delete" && current && (
        <ConfirmDialog title={T.deleteTitle} message={T.deleteMessage(current.name)} confirmLabel={T.deleteView} danger
                       onCancel={() => setConfirm(null)}
                       onConfirm={() => { setConfirm(null); views.remove(); }} />
      )}
    </div>
  );
}

function SaveAsDialog({ onClose, onSave }: { onClose(): void; onSave(name: string, shared: boolean): Promise<void> }) {
  const [name, setName] = useState("");
  const [shared, setShared] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await onSave(name.trim(), shared);
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      setBusy(false);
    }
  };
  return (
    <Dialog title={T.saveAs} onClose={onClose} onSubmit={submit} submitLabel={T.save} busy={busy}>
      <TextField label={T.viewName} value={name} onChange={(v) => { setName(v); setError(undefined); }} required
                 maxLength={100} error={error} />
      <Checkbox label={T.shared} checked={shared} onChange={setShared} />
    </Dialog>
  );
}
