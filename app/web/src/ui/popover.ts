// Açılır öğelerin ortak yerleşimi (docs/12 "Açılır menülerin yerleşimi"): filtre ve kolon menüleri, alt menüler,
// görünüm menüsü, Grupla, Alanlar, takvim. Ekranda sabit konumda açılır ve görünür alana sığar: altta yer yoksa yukarı,
// sağ kenara yakınsa sola; alt menü ana menünün sağında, yer yoksa solunda.
import { type RefObject, useLayoutEffect } from "react";

export interface Box {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

type Size = { width: number; height: number };

/** Açan öğenin altında (yer yoksa üstünde); sağa taşacaksa sağ kenarı açan öğeyle hizalı. Ekran koordinatı. */
export function placePopover(anchor: Box, size: Size, viewport: Size, gap = 4, margin = 8): { left: number; top: number } {
  let left = anchor.left;
  if (left + size.width > viewport.width - margin) left = anchor.right - size.width;
  left = Math.max(margin, Math.min(left, viewport.width - margin - size.width));
  let top = anchor.bottom + gap;
  const above = anchor.top - gap - size.height;
  if (top + size.height > viewport.height - margin && above >= margin) top = above;
  return { left: Math.max(margin, left), top };
}

/** Alt menü: açan öğenin sağında, yer yoksa solunda; alttan taşacaksa yukarı kayar. Ekran koordinatı. */
export function placeSubmenu(anchor: Box, size: Size, viewport: Size, margin = 8): { left: number; top: number } {
  let left = anchor.right;
  if (left + size.width > viewport.width - margin) left = anchor.left - size.width;
  left = Math.max(margin, left);
  let top = anchor.top;
  if (top + size.height > viewport.height - margin) top = viewport.height - margin - size.height;
  return { left, top: Math.max(margin, top) };
}

export function viewportSize(): Size {
  return { width: document.documentElement.clientWidth || window.innerWidth,
           height: document.documentElement.clientHeight || window.innerHeight };
}

export const toBox = (el: Element): Box => {
  const r = el.getBoundingClientRect();
  return { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
};

type Anchor = RefObject<HTMLElement | null> | HTMLElement | null;

/**
 * Açık öğeyi (ref; CSS .sc-floating, position: fixed) açan öğeye göre yerleştirir. Her çizimden sonra ölçülür
 * (içerik büyüyünce de sığsın); pencere boyu değişince ve kaydırılınca yeniden yerleşir.
 */
export function useFloating(ref: RefObject<HTMLElement | null>, anchor: Anchor, open: boolean,
                            mode: "below" | "side" = "below") {
  useLayoutEffect(() => {
    const el = ref.current;
    const at = anchor && "current" in anchor ? anchor.current : anchor;
    if (!open || !el || !at) return;
    const place = () => {
      el.style.left = "0px";  // genişlik konumdan bağımsız ölçülsün
      el.style.top = "0px";
      const r = el.getBoundingClientRect();
      const pos = (mode === "side" ? placeSubmenu : placePopover)(toBox(at), { width: r.width, height: r.height }, viewportSize());
      el.style.left = `${pos.left}px`;
      el.style.top = `${pos.top}px`;
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  });
}
