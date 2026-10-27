// Açılır pencerenin görünür alana sığacak konumu (docs/12): sağ kenara yakınsa sola, altta yer yoksa yukarı açılır.

export interface Box {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/** Ekran koordinatlarında sol üst köşe. anchor: açan öğenin kutusu; size: pencerenin boyu. */
export function placePopover(anchor: Box, size: { width: number; height: number },
                             viewport: { width: number; height: number }, gap = 4, margin = 8): { left: number; top: number } {
  let left = anchor.left;
  if (left + size.width > viewport.width - margin) left = anchor.right - size.width;
  left = Math.max(margin, Math.min(left, viewport.width - margin - size.width));
  let top = anchor.bottom + gap;
  const above = anchor.top - gap - size.height;
  if (top + size.height > viewport.height - margin && above >= margin) top = above;
  return { left: Math.max(margin, left), top };
}

export function viewportSize() {
  return { width: document.documentElement.clientWidth || window.innerWidth,
           height: document.documentElement.clientHeight || window.innerHeight };
}
