// Kayıtlı görünüm (U-9, K-89): seçici (görünür etiketsiz, ekran okuyucu adı "Görünüm"), "⋯" menüsü (Kaydet, Farklı
// kaydet, Varsayılan yap, Sil) ve hemen yanında "Sıralamayı temizle" ikonu (1.6 demosu). Kaydedilmemiş değişiklik "⋯" düğmesinin köşesinde indigo noktayla gösterilir.
// Görünümler veritabanında; kullanıcı A-36 gereği şimdilik user_id ile. Açılışta kullanıcının varsayılanı uygulanır.
import { ArrowUpDown, Ellipsis } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { tr } from "../i18n/tr";
import { Checkbox, ConfirmDialog, Dialog, TextField } from "../ui";
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
    api.views(ctrl.signal)
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
      const saved = await api.updateView(current.id, { definition: toDefinition(state) });
      setViews((vs) => vs.map((v) => (v.id === saved.id ? saved : v)));
      setBaseline(toDefinition(state));
    },
    async saveAs(state, name, shared) {
      const saved = await api.createView({ name, is_shared: shared, definition: toDefinition(state) });
      setViews((vs) => [...vs, saved].sort((a, b) => a.name.localeCompare(b.name, "tr")));
      setCurrentId(saved.id);
      setBaseline(toDefinition(state));
      setWarnings([]);
    },
    async remove() {
      if (!current) return;
      await api.deleteView(current.id);
      setViews((vs) => vs.filter((v) => v.id !== current.id));
      if (defaultId === current.id) setDefaultId(null);
      use(null);
    },
    async toggleDefault() {
      const next = defaultId === currentId ? null : currentId;
      await api.setDefaultView(next);
      setDefaultId(next);
    },
    dismissWarnings: () => setWarnings([]),
  };
}

export function ViewBar({ views, state, onClearSort }: { views: Views; state: TableState; onClearSort(): void }) {
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

  const owner = Boolean(current?.is_owner);
  const isDefault = views.defaultId === views.currentId;
  const items: { label: string; disabled: boolean; strong?: boolean; run(): void }[] = [
    { label: T.save, disabled: !(dirty && owner), strong: dirty && owner, run: () => views.save(state) },
    { label: T.saveAs, disabled: false, run: () => setSaveAs(true) },
    { label: isDefault && current ? T.removeDefault : T.makeDefault, disabled: isDefault && !current, run: () => views.toggleDefault() },
    { label: T.deleteView, disabled: !owner, run: () => setConfirm({ kind: "delete" }) },
  ];

  return (
    <div className="sc-viewbar">
      <select className="sc-input sc-select sc-viewbar-select" aria-label={T.view} value={views.currentId ?? ""}
              onChange={(e) => choose(e.target.value)}>
        <option value="">{T.standard}{views.defaultId === null ? ` (${T.defaultMark})` : ""}</option>
        {views.views.map((v) => <option key={v.id} value={v.id}>{label(v)}</option>)}
      </select>
      <div className="sc-table-anchor sc-viewbar-anchor" ref={menuRef}>
        <button type="button" className="sc-tool-btn" ref={menuButtonRef} aria-label={T.viewMenu} aria-haspopup="menu"
                aria-expanded={menuOpen} title={dirty ? T.unsaved : T.viewMenu} onClick={() => setMenuOpen((o) => !o)}>
          <Ellipsis aria-hidden="true" />
        </button>
        {dirty && <span className="sc-viewbar-dot" role="img" aria-label={T.unsaved} title={T.unsaved} />}
        {menuOpen && (
          <div ref={menuPopRef} className="sc-table-pop sc-popmenu sc-viewbar-menu sc-floating" role="menu" aria-label={T.viewMenu}>
            {items.map((it) => (
              <button key={it.label} type="button" role="menuitem" disabled={it.disabled}
                      className={`sc-popmenu-item${it.strong ? " is-strong" : ""}`}
                      onClick={() => { setMenuOpen(false); it.run(); }}>{it.label}</button>
            ))}
          </div>
        )}
      </div>
      <button type="button" className="sc-tool-btn" aria-label={T.clearSort} title={T.clearSort}
              disabled={state.sort.length === 0} onClick={onClearSort}><ArrowUpDown aria-hidden="true" /></button>
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
