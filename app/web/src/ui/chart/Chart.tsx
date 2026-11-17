// Grafiğin çizim yüzeyi (K-178): seçenekleri kütüphaneye verir, kutusu değişince yeniden boyutlar. Hâller (boş, yükleniyor, hata) ChartPane'de.
import { useEffect, useRef } from "react";

import { type ChartInstance, createChart } from "./echarts";

export default function Chart({ option, label }: { option: Record<string, unknown>; label: string }) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<ChartInstance | null>(null);

  useEffect(() => {
    if (!box.current) return undefined;
    const instance = createChart(box.current);
    chart.current = instance;
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

  return <div ref={box} className="sc-chart-canvas" role="img" aria-label={label} data-testid="chart-canvas" />;
}
