// Rozet (U-2, U-3): durum rengi her zaman yazıyla birlikte; yazısız rozet oluşturulamaz.
export type BadgeTone = "neutral" | "info" | "ok" | "risk" | "critical";

export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: string | number }) {
  const text = String(children).trim();
  if (!text) throw new Error("Rozet yazısız olamaz (U-3)");
  return <span className={`sc-tag sc-tag--${tone}`}>{text}</span>;
}
