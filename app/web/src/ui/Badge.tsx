// Rozet (U-2, U-3): durum rengi her zaman yazıyla birlikte; yazısız rozet oluşturulamaz.
export type BadgeTone = "neutral" | "info" | "ok" | "risk" | "critical" | "muted";  // muted: sönük, durum rengi değil (ör. Yok sayıldı, K-174)

export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: string | number }) {
  const text = String(children).trim();
  if (!text) throw new Error("Rozet yazısız olamaz (U-3)");
  return <span className={`sc-tag sc-tag--${tone}`}>{text}</span>;
}
