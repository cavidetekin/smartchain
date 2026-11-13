// İpucu (K-132, docs/12): açıklama taşıyan ipucu tarayıcınınki yerine bu bileşenle; çok satır alır, odakta da görünür.
// Pencereye asılır: tablo hücresinin ve pencerenin kırpmasından etkilenmez. Sağ tıkta kapanır (açılan hücre menüsünü örtmesin, K-172).
import { type FocusEvent, type MouseEvent, type ReactNode, useId, useState } from "react";
import { createPortal } from "react-dom";

const GAP = 6;

export function Tooltip({ content, focusable = false, children }: {
  content: ReactNode;
  /** İçinde odaklanacak öğe yoksa (ikon, çip) klavyeyle de açılsın. */
  focusable?: boolean;
  children: ReactNode;
}) {
  const [at, setAt] = useState<{ x: number; y: number } | null>(null);
  const id = useId();
  if (!content) return <>{children}</>;
  const show = (e: MouseEvent<HTMLElement> | FocusEvent<HTMLElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    setAt({ x: box.left + box.width / 2, y: box.bottom + GAP });
  };
  const hide = () => setAt(null);
  return (
    <span className="sc-tip-anchor" tabIndex={focusable ? 0 : undefined} aria-describedby={at ? id : undefined}
          onMouseEnter={show} onMouseLeave={hide} onFocus={show} onBlur={hide} onContextMenu={hide}>
      {children}
      {at && createPortal(<div id={id} role="tooltip" className="sc-tooltip" style={{ left: at.x, top: at.y }}>{content}</div>, document.body)}
    </span>
  );
}
