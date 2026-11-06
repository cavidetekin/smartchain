// Üst şerit (K-139 eki, docs/12 · Üst şerit): ekranın üstündeki ayar ve filtre alanları her ekranda aynı biçimde.
// Beyaz kart içinde tek satır, etiketler alanın solunda; şerit ile tablo araç çubuğu arası --top-strip-gap.
import type { ReactNode } from "react";

export function TopStrip({ label, children }: { label: string; children: ReactNode }) {
  return <div className="sc-top-strip" role="group" aria-label={label}>{children}</div>;
}
