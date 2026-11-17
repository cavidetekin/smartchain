// Çizim kütüphanesinin tek içe alma noktası (K-178): Apache ECharts, yalnız kullanılan parçalar, SVG çizici. Pakete gömülüdür; ağa çıkmaz.
// Bu dosya grafik ilk açıldığında ayrı parça olarak yüklenir (Chart.tsx `lazy` ile içe alınır).
import { BarChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import { DataZoomSliderComponent, GraphicComponent, GridComponent, LegendComponent, MarkLineComponent, TitleComponent, TooltipComponent } from "echarts/components";
import { init, use } from "echarts/core";
import { LabelLayout } from "echarts/features";
import { CanvasRenderer, SVGRenderer } from "echarts/renderers";

use([BarChart, LineChart, PieChart, ScatterChart, CanvasRenderer, DataZoomSliderComponent, GraphicComponent, GridComponent, LegendComponent, MarkLineComponent, TitleComponent, TooltipComponent, LabelLayout, SVGRenderer]);

export interface ChartInstance {
  setOption(option: Record<string, unknown>, opts?: { notMerge?: boolean }): void;
  resize(): void;
  dispose(): void;
  /** Tıklama ve sağ tık (K-179): params.seriesIndex, params.dataIndex; params.event.event tarayıcı olayı. */
  on(event: "click" | "contextmenu", handler: (params: ChartEvent) => void): void;
}

export interface ChartEvent {
  componentType?: string;
  seriesIndex?: number;
  dataIndex?: number;
  event?: { event?: MouseEvent };
}

export function createChart(el: HTMLElement): ChartInstance {
  return init(el, undefined, { renderer: "svg" }) as unknown as ChartInstance;
}

/** Grafiğin görseli (K-179): ekran dışındaki bir tuvale çizilir (yazı tipleri doğru çıksın diye tuval çizici), 2× çözünürlükte PNG (data: adresi).
 *  Zemin verilen renktir. Ekrandaki grafiğe dokunmaz. */
export async function renderPng(option: Record<string, unknown>, width: number, height: number, background: string): Promise<string> {
  try { await document.fonts?.ready; } catch { /* yazı tipleri hazır değilse sistem yazı tipiyle çizilir */ }
  const el = document.createElement("div");
  el.style.cssText = `position:fixed;left:-100000px;top:0;width:${width}px;height:${height}px;pointer-events:none`;
  document.body.appendChild(el);
  const chart = init(el, undefined, { renderer: "canvas", width, height, devicePixelRatio: 2 });
  try {
    chart.setOption({ ...option, animation: false });
    return chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: background });
  } finally {
    chart.dispose();
    el.remove();
  }
}
