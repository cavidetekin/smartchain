// Açılır menü (satırın "⋯" menüsü, ekran 22, 24; tablonun hücre menüsü, K-173): açan öğenin yanında, dışarı tıklama ve Esc kapatır, ok tuşlarıyla gezilir.
import { type ReactNode, useEffect, useId, useRef } from "react";

import { useFloating } from "./popover";

export interface MenuState {
  allowed: boolean;
  reason?: string | null;
}

/** Menü öğesi (ör. sağ tıkta hücreye özgü seçenekler: Kopyala, Manuel değeri kaldır; K-171). kind: grup başlığı ("Seçili 3 satır") ya da ayraç. */
export interface MenuAction { label: string; onClick?(): void; state?: MenuState; kind?: "heading" | "separator" }

/** Sağ tıkta menünün başına eklenen öğeler (çoklu seçimin grubu, hücre seçenekleri) ve ayraç (K-171). end: false ise sonda ayraç yok. */
export function MenuActions({ items, onDone, end = true }: { items?: MenuAction[]; onDone?(): void; end?: boolean }) {
  if (!items?.length) return null;
  return (
    <>
      {items.map((it, i) => {
        if (it.kind === "separator") return <div key={`sep${i}`} role="separator" className="sc-popmenu-sep" />;
        if (it.kind === "heading") return <div key={`h${i}`} role="presentation" className="sc-popmenu-heading">{it.label}</div>;
        return <MenuItem key={it.label} label={it.label} state={it.state ?? { allowed: true }} onClick={() => { onDone?.(); it.onClick?.(); }} />;
      })}
      {end && <div role="separator" className="sc-popmenu-sep" />}
    </>
  );
}

export function MenuItem({ label, state, onClick }: { label: string; state: MenuState; onClick(): void }) {
  const reasonId = useId();
  return (
    <>
      <button type="button" role="menuitem" className="sc-popmenu-item" disabled={!state.allowed}
              title={state.reason ?? undefined} aria-describedby={state.reason ? reasonId : undefined} onClick={onClick}>
        {label}
      </button>
      {state.reason && <span id={reasonId} className="sc-visually-hidden">{state.reason}</span>}
    </>
  );
}

/** ready: içerik hazır olunca (ör. kayıt sunucudan gelince) ilk öğeye odaklanılır. */
export function RowPopMenu({ label, anchor, onClose, ready = true, children }: {
  label: string; anchor: HTMLElement; onClose(): void; ready?: boolean; children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useFloating(ref, anchor, true);

  useEffect(() => {
    if (ready) ref.current?.querySelector<HTMLButtonElement>("button:not([disabled])")?.focus();
  }, [ready]);

  useEffect(() => {
    const down = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node) && !anchor.contains(e.target as Node)) onClose();
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        anchor.focus();
      }
    };
    document.addEventListener("mousedown", down);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("mousedown", down);
      document.removeEventListener("keydown", key);
    };
  }, [anchor, onClose]);

  return (
    <div className="sc-table-pop sc-table-pop--menu sc-floating" ref={ref}>
      <div className="sc-popmenu" role="menu" aria-label={label}
           onKeyDown={(e) => {
             if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
             e.preventDefault();
             const buttons = [...e.currentTarget.querySelectorAll<HTMLButtonElement>("button:not([disabled])")];
             const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
             buttons[(at + (e.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length]?.focus();
           }}>
        {children}
      </div>
    </div>
  );
}
