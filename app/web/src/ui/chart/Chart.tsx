// Grafiğin çizim yüzeyi (K-178): seçenekleri kütüphaneye verir, kutusu değişince yeniden boyutlar. Hâller (boş, yükleniyor, hata) ChartPane'de.
// Tıklama ve sağ tık (K-179) parça sırasıyla (seri, veri) bildirilir; tarayıcının sağ tık menüsü grafikte açılmaz.
import { useEffect, useRef } from "react";

import { type ChartEvent, type ChartInstance, createChart } from "./echarts";

export default function Chart({ option, label, minHeight, onPick, onMenu }: {
  option: Record<string, unknown>; label: string;
  /** Çizimin en küçük yüksekliği (küçük grafikler): bölme bundan kısaysa kaydırılır. */
  minHeight?: number;
  onPick?(seriesIndex: number, dataIndex: number): void;
  onMenu?(seriesIndex: number, dataIndex: number, x: number, y: number): void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<ChartInstance | null>(null);
  const handlers = useRef({ onPick, onMenu });
  handlers.current = { onPick, onMenu };

  useEffect(() => {
    if (!box.current) return undefined;
    const instance = createChart(box.current);
    chart.current = instance;
    const part = (p: ChartEvent) => (p.componentType === "series" && p.seriesIndex !== undefined && p.dataIndex !== undefined ? [p.seriesIndex, p.dataIndex] as const : null);
    instance.on("click", (p) => { const at = part(p); if (at) handlers.current.onPick?.(at[0], at[1]); });
    instance.on("contextmenu", (p) => {
      const at = part(p);
      const e = p.event?.event;
      if (at && e) handlers.current.onMenu?.(at[0], at[1], e.clientX, e.clientY);
    });
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => instance.resize());
    observer?.observe(box.current);
    return () => {
      observer?.disconnect();
      chart.current = null;
      instance.dispose();
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, { notMerge: true });  // her değişiklikte baştan: silinen seri ekranda kalmaz
  }, [option]);

  return <div ref={box} className="sc-chart-canvas" role="img" aria-label={label} data-testid="chart-canvas" style={minHeight ? { minHeight } : undefined} onContextMenu={(e) => e.preventDefault()} />;
}
