// Çizim kütüphanesinin tek içe alma noktası (K-178): Apache ECharts, yalnız kullanılan parçalar, SVG çizici. Pakete gömülüdür; ağa çıkmaz.
// Bu dosya grafik ilk açıldığında ayrı parça olarak yüklenir (Chart.tsx `lazy` ile içe alınır).
import { BarChart, LineChart } from "echarts/charts";
import { DataZoomSliderComponent, GridComponent, LegendComponent, MarkLineComponent, TitleComponent, TooltipComponent } from "echarts/components";
import { init, use } from "echarts/core";
import { LabelLayout } from "echarts/features";
import { SVGRenderer } from "echarts/renderers";

use([BarChart, LineChart, DataZoomSliderComponent, GridComponent, LegendComponent, MarkLineComponent, TitleComponent, TooltipComponent, LabelLayout, SVGRenderer]);

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
