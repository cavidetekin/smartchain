// Sıralanabilir liste (docs/12 "Sıralanabilir liste standardı", K-201): öğelerinin sırası kullanıcı tarafından değiştirilen sade liste (tablo değil).
// Satır: sıra no, tutamak, ad; sağda öğeye özel denetim (satırın sağ kenarına yaslı). Sürükleme (bırakılacak yer indigo çizgi), klavyede
// Alt + ↑ / ↓ (odak satırla birlikte gider). "Yukarı taşı" · "aşağı taşı" düğmeleri isteğe bağlıdır (`moveButtons`; varsayılan kapalı). Liste kendisi kaydetmez: yeni sırayı kullanan ekrana bildirir. İlk kullanan Parametreler › Pegging.
import { ArrowDown, ArrowUp, GripVertical } from "lucide-react";
import { type DragEvent, type KeyboardEvent, type ReactNode, useEffect, useRef, useState } from "react";

import { tr } from "../i18n/tr";

export interface SortableItem {
  id: string;
  label: string;
  /** Satırın sağındaki denetim (ör. yön seçimi). */
  end?: ReactNode;
}

/** Öğeyi hedefin üstüne ya da altına taşır. */
export function moveItem<T>(ids: T[], id: T, target: T, side: "before" | "after"): T[] {
  if (id === target) return ids;
  const rest = ids.filter((x) => x !== id);
  const at = rest.indexOf(target);
  if (at < 0) return ids;
  rest.splice(side === "before" ? at : at + 1, 0, id);
  return rest;
}

export function SortableList({ label, items, onOrder, readOnly, moveButtons = false }: {
  /** Listenin erişilebilir adı. */
  label: string;
  items: SortableItem[];
  /** Yeni sıra (öğe kimlikleri). */
  onOrder(ids: string[]): void;
  /** Yetki yoksa tutamak ve düğmeler görünmez, sürükleme çalışmaz. */
  readOnly?: boolean;
  /** Satırın sonunda "yukarı taşı" · "aşağı taşı" simge düğmeleri (varsayılan kapalı; Pegging'de kapalı, K-201). */
  moveButtons?: boolean;
}) {
  const T = tr.sortable;
  const [drag, setDrag] = useState<{ id: string; over?: string; side?: "before" | "after" } | null>(null);
  const list = useRef<HTMLOListElement>(null);
  const refocus = useRef<string | null>(null);     // klavyeyle ya da düğmeyle taşınan satır: odak onunla gider
  const ids = items.map((i) => i.id);

  useEffect(() => {
    const id = refocus.current;
    if (!id) return;
    refocus.current = null;
    const row = [...(list.current?.children ?? [])].find((el) => (el as HTMLElement).dataset.item === id) as HTMLElement | undefined;
    const target = row?.querySelector<HTMLElement>(`[data-move="${refocusButton.current ?? ""}"]:not(:disabled)`) ?? row;
    target?.focus();
    refocusButton.current = null;
  });
  const refocusButton = useRef<"up" | "down" | null>(null);

  const step = (id: string, by: -1 | 1, from?: "up" | "down") => {
    const at = ids.indexOf(id);
    const to = at + by;
    if (to < 0 || to >= ids.length) return;
    refocus.current = id;
    refocusButton.current = from ?? null;
    onOrder(moveItem(ids, id, ids[to], by < 0 ? "before" : "after"));
  };
  const onKey = (id: string, e: KeyboardEvent<HTMLLIElement>) => {
    if (readOnly || !e.altKey || (e.key !== "ArrowUp" && e.key !== "ArrowDown") || e.target !== e.currentTarget) return;
    e.preventDefault();
    step(id, e.key === "ArrowUp" ? -1 : 1);
  };
  const over = (id: string, e: DragEvent<HTMLLIElement>) => {
    if (!drag) return;
    e.preventDefault();
    const box = e.currentTarget.getBoundingClientRect();
    const side = e.clientY < box.top + box.height / 2 ? "before" : "after";
    if (drag.over !== id || drag.side !== side) setDrag({ id: drag.id, over: id, side });
  };
  const drop = (id: string, e: DragEvent<HTMLLIElement>) => {
    e.preventDefault();
    if (drag && drag.id !== id) onOrder(moveItem(ids, drag.id, id, drag.side ?? "before"));
    setDrag(null);
  };

  return (
    <ol ref={list} className="sc-sortable" aria-label={label}>
      {items.map((item, i) => {
        const classes = ["sc-sortable-row", drag?.id === item.id ? "is-dragging" : "", drag?.over === item.id && drag.id !== item.id ? `is-drop-${drag.side}` : ""]
          .filter(Boolean).join(" ");
        return (
          <li key={item.id} className={classes} data-item={item.id} tabIndex={readOnly ? undefined : 0} draggable={!readOnly}
              aria-label={T.row(i + 1, item.label)} onKeyDown={(e) => onKey(item.id, e)}
              onDragStart={(e) => { e.dataTransfer?.setData("text/plain", item.id); if (e.dataTransfer) e.dataTransfer.effectAllowed = "move"; setDrag({ id: item.id }); }}
              onDragOver={(e) => over(item.id, e)} onDrop={(e) => drop(item.id, e)} onDragEnd={() => setDrag(null)}>
            <span className="sc-sortable-no sc-num">{i + 1}</span>
            {!readOnly && <GripVertical className="sc-sortable-grip" aria-hidden="true" />}
            <span className="sc-sortable-name">{item.label}</span>
            {item.end && <span className="sc-sortable-end">{item.end}</span>}
            {moveButtons && !readOnly && (
              <span className="sc-sortable-moves">
                <button type="button" className="sc-tool-btn" data-move="up" aria-label={T.up(item.label)} title={T.upTitle} disabled={i === 0}
                        onClick={() => step(item.id, -1, "up")}><ArrowUp aria-hidden="true" /></button>
                <button type="button" className="sc-tool-btn" data-move="down" aria-label={T.down(item.label)} title={T.downTitle} disabled={i === items.length - 1}
                        onClick={() => step(item.id, 1, "down")}><ArrowDown aria-hidden="true" /></button>
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
