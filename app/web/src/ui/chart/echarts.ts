// Çizim kütüphanesinin tek içe alma noktası (K-178): Apache ECharts, yalnız kullanılan parçalar, SVG çizici. Pakete gömülüdür; ağa çıkmaz.
// Bu dosya grafik ilk açıldığında ayrı parça olarak yüklenir (Chart.tsx `lazy` ile içe alınır).
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, MarkLineComponent, TitleComponent, TooltipComponent } from "echarts/components";
import { init, use } from "echarts/core";
import { LabelLayout } from "echarts/features";
import { SVGRenderer } from "echarts/renderers";

use([BarChart, LineChart, GridComponent, LegendComponent, MarkLineComponent, TitleComponent, TooltipComponent, LabelLayout, SVGRenderer]);

export interface ChartInstance {
  setOption(option: Record<string, unknown>, opts?: { notMerge?: boolean }): void;
  resize(): void;
  dispose(): void;
}

export function createChart(el: HTMLElement): ChartInstance {
  return init(el, undefined, { renderer: "svg" }) as unknown as ChartInstance;
}
