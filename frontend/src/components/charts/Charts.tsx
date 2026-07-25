import {
  BarChart,
  GraphChart,
  HeatmapChart,
  LineChart,
  SankeyChart,
  ScatterChart,
} from "echarts/charts";
import {
  AriaComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import ReactEChartsCore from "echarts-for-react/lib/core";
import type { ComponentProps } from "react";
import type {
  AtomPoint,
  BusinessPayload,
  MatrixCell,
  NetworkData,
  QuantumPayload,
  ScenarioVisualPayload,
} from "../../types";
import { useI18n } from "../../i18n";

echarts.use([
  AriaComponent,
  BarChart,
  CanvasRenderer,
  GraphChart,
  GridComponent,
  HeatmapChart,
  LegendComponent,
  LineChart,
  SankeyChart,
  ScatterChart,
  TooltipComponent,
  VisualMapComponent,
]);

type EChartsProps = Omit<ComponentProps<typeof ReactEChartsCore>, "echarts">;

function ReactECharts(props: EChartsProps) {
  return <ReactEChartsCore echarts={echarts} {...props} />;
}

const palette = {
  background: "transparent",
  text: "#dfeae5",
  muted: "#82938c",
  grid: "#26312d",
  cyan: "#27d9e7",
  green: "#4ade80",
  amber: "#f0b94c",
  red: "#f16f6f",
  surface: "#111716",
};

const common = {
  backgroundColor: palette.background,
  textStyle: { color: palette.text, fontFamily: "Inter, system-ui, sans-serif" },
  animationDuration: 420,
  aria: { enabled: true },
};

const axis = {
  axisLine: { lineStyle: { color: palette.grid } },
  axisTick: { show: false },
  axisLabel: { color: palette.muted, fontSize: 10 },
  splitLine: { lineStyle: { color: palette.grid, opacity: 0.55 } },
  nameTextStyle: { color: palette.muted, fontSize: 11 },
};

const tooltip = {
  trigger: "item",
  backgroundColor: palette.surface,
  borderColor: palette.grid,
  textStyle: { color: palette.text, fontSize: 12 },
};

const seriesColors = [palette.cyan, palette.green, palette.amber, "#8fa6ff"];

function categoryColor(index: number) {
  return seriesColors[index % seriesColors.length];
}

function minuteLabel(value: number) {
  const hours = Math.floor(value / 60);
  const minutes = Math.round(value % 60);
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

export function BusinessChart({ business }: { business: BusinessPayload }) {
  const { tx } = useI18n();
  const { kind, points, xLabel, yLabel } = business.chart;
  const displayedXLabel = tx(xLabel);
  const displayedYLabel = tx(yLabel);
  if (kind === "allocation-bars") {
    return (
      <ReactECharts
        className="chart-canvas"
        option={{
          ...common,
          tooltip,
          grid: { left: 92, right: 24, top: 20, bottom: 34 },
          xAxis: { ...axis, type: "value", name: displayedXLabel },
          yAxis: {
            ...axis,
            type: "category",
            data: points.map((point) => tx(point.label)),
            axisLabel: { color: palette.muted, width: 82, overflow: "truncate" },
          },
          series: [
            {
              type: "bar",
              data: points.map((point) => ({
                value: point.y,
                itemStyle: { color: point.selected ? palette.green : "#31564e" },
                name: tx(point.label),
              })),
              barWidth: 12,
            },
          ],
        }}
      />
    );
  }
  const percentAxis = kind === "efficient-frontier" || kind === "risk-grid";
  const timeAxis = kind === "funding-timeline";
  const formatX = (value: number) =>
    percentAxis
      ? `${(value * 100).toFixed(1)}%`
      : timeAxis
        ? minuteLabel(value)
        : value.toFixed(2);
  const formatY = (value: number) =>
    percentAxis ? `${(value * 100).toFixed(1)}%` : value.toFixed(2);
  const option = {
    ...common,
    tooltip: {
      ...tooltip,
      formatter: (params: { data: { name: string; value: [number, number, number]; detail: string } }) =>
        `<strong>${tx(params.data.name)}</strong><br/>${displayedXLabel} ${formatX(params.data.value[0])}<br/>${displayedYLabel} ${formatY(params.data.value[1])}<br/>${tx(params.data.detail)}`,
    },
    grid: { left: 58, right: 26, top: 26, bottom: 50 },
    xAxis: {
      ...axis,
      type: "value",
      name: displayedXLabel,
      min: timeAxis ? 540 : undefined,
      max: timeAxis ? 930 : undefined,
      axisLabel: {
        ...axis.axisLabel,
        formatter: percentAxis
          ? (value: number) => `${(value * 100).toFixed(0)}%`
          : timeAxis
            ? minuteLabel
            : undefined,
      },
    },
    yAxis: {
      ...axis,
      type: "value",
      name: displayedYLabel,
      minInterval: timeAxis ? 1 : undefined,
      axisLabel: {
        ...axis.axisLabel,
        formatter: percentAxis ? (value: number) => `${(value * 100).toFixed(0)}%` : undefined,
      },
    },
    series: [
      {
        type: "scatter",
        symbol: "circle",
        data: points.map((point) => ({
          name: point.label,
          value: [point.x, point.y, point.size],
          detail: point.detail,
          itemStyle: {
            color: point.selected ? palette.green : palette.cyan,
            opacity: point.selected ? 1 : 0.45,
            borderColor: point.selected ? "#dffff0" : "transparent",
            borderWidth: point.selected ? 2 : 0,
          },
        })),
        symbolSize: (value: number[]) => Math.max(7, Math.min(24, value[2] ?? 8)),
      },
    ],
  };
  return <ReactECharts className="chart-canvas" option={option} />;
}

export function NetworkChart({ network }: { network: NetworkData }) {
  const groups = [...new Set(network.nodes.map((node) => node.group))];
  return (
    <ReactECharts
      className="chart-canvas"
      option={{
        ...common,
        tooltip,
        legend: {
          data: groups,
          bottom: 0,
          textStyle: { color: palette.muted, fontSize: 10 },
        },
        series: [
          {
            type: "graph",
            layout: "force",
            roam: true,
            force: { repulsion: 160, edgeLength: [62, 110], gravity: 0.08 },
            categories: groups.map((name) => ({ name })),
            data: network.nodes.map((node) => ({
              name: node.id,
              value: node.value,
              category: groups.indexOf(node.group),
              symbolSize: Math.max(14, Math.min(30, node.value * 1.2)),
            })),
            links: network.edges.map((edge) => ({
              source: edge.source,
              target: edge.target,
              lineStyle: {
                color: edge.kind === "conflict" ? palette.amber : palette.cyan,
                type: edge.kind === "conflict" ? "solid" : "dashed",
                opacity: 0.65,
              },
            })),
            label: { show: true, color: palette.text, fontSize: 10 },
            lineStyle: { width: 1.2 },
            itemStyle: { color: palette.cyan, borderColor: "#0a1110", borderWidth: 2 },
          },
        ],
      }}
    />
  );
}

export function ScenarioChart({
  visual,
  selectedIds,
}: {
  visual: ScenarioVisualPayload;
  selectedIds: string[];
}) {
  const { t, tx } = useI18n();
  const selected = new Set(selectedIds);

  if (
    visual.kind === "portfolio-correlation" ||
    visual.kind === "derivatives-pnl-surface"
  ) {
    const isCorrelation = visual.kind === "portfolio-correlation";
    const absoluteMaximum = Math.max(
      ...visual.matrix.cells.map((cell) => Math.abs(cell.value)),
      1e-9,
    );
    return (
      <ReactECharts
        className="chart-canvas scenario-chart"
        option={{
          ...common,
          tooltip: {
            ...tooltip,
            formatter: (params: {
              data: {
                id: string;
                label: string;
                value: [number, number, number];
                stressedPrice?: number;
                riskWeight?: number;
                delta?: number;
                gamma?: number;
                vega?: number;
              };
            }) => {
              const value = params.data.value[2];
              const formatted = isCorrelation
                ? value.toFixed(3)
                : `${value >= 0 ? "+" : ""}${value.toFixed(4)}`;
              if (isCorrelation) {
                return `<strong>${tx(params.data.label)}</strong><br/>${t("correlation")} ${formatted}`;
              }
              return [
                `<strong>${tx(params.data.label)}</strong>`,
                `${t("priceChange")} ${formatted}`,
                `${t("referencePrice")} ${(params.data.stressedPrice ?? 0).toFixed(4)}`,
                `${t("riskWeight")} ${(params.data.riskWeight ?? 0).toFixed(3)}`,
                `Delta ${(params.data.delta ?? 0).toFixed(4)}`,
                `Gamma ${(params.data.gamma ?? 0).toFixed(4)}`,
                `Vega ${(params.data.vega ?? 0).toFixed(4)}`,
              ].join("<br/>");
            },
          },
          grid: { left: 78, right: 26, top: 18, bottom: 72 },
          xAxis: {
            ...axis,
            type: "category",
            data: visual.matrix.xLabels.map(tx),
            name: tx(visual.xLabel),
            axisLabel: {
              color: palette.muted,
              rotate: isCorrelation ? 34 : 0,
              formatter: (value: string) =>
                isCorrelation && value.length > 6 ? `${value.slice(0, 6)}…` : value,
            },
          },
          yAxis: {
            ...axis,
            type: "category",
            data: visual.matrix.yLabels.map(tx),
            name: tx(visual.yLabel),
            axisLabel: {
              color: palette.muted,
              formatter: (value: string) =>
                isCorrelation && value.length > 6 ? `${value.slice(0, 6)}…` : value,
            },
          },
          visualMap: {
            min: isCorrelation ? -1 : -absoluteMaximum,
            max: isCorrelation ? 1 : absoluteMaximum,
            orient: "horizontal",
            left: "center",
            bottom: 2,
            calculable: false,
            text: isCorrelation
              ? [t("positiveCorrelation"), t("negativeCorrelation")]
              : [t("profit"), t("loss")],
            textStyle: { color: palette.muted, fontSize: 10 },
            inRange: { color: ["#a6534b", "#17201e", palette.cyan] },
          },
          series: [
            {
              type: "heatmap",
              data: visual.matrix.cells.map((cell) => ({
                id: cell.id,
                label: cell.label,
                value: [cell.x, cell.y, cell.value],
                stressedPrice: cell.stressedPrice,
                riskWeight: cell.riskWeight,
                delta: cell.delta,
                gamma: cell.gamma,
                vega: cell.vega,
                itemStyle: selected.has(cell.id)
                  ? { borderColor: palette.green, borderWidth: 3 }
                  : { borderColor: palette.surface, borderWidth: 1 },
              })),
              label: {
                show: visual.matrix.cells.length <= 16,
                color: palette.text,
                fontSize: 10,
                formatter: (params: { value: [number, number, number] }) =>
                  isCorrelation
                    ? params.value[2].toFixed(2)
                    : params.value[2].toFixed(2),
              },
            },
          ],
        }}
      />
    );
  }

  if (
    visual.kind === "settlement-network" ||
    visual.kind === "fraud-entity-network"
  ) {
    const groups = visual.categories;
    return (
      <ReactECharts
        className="chart-canvas scenario-chart"
        option={{
          ...common,
          tooltip: {
            ...tooltip,
            formatter: (params: {
              dataType: "node" | "edge";
              data: { label?: string; detail?: string; kind?: string };
            }) =>
              params.dataType === "edge"
                ? `${params.data.kind === "conflict" ? t("settlementConflict") : params.data.kind === "dependency" ? t("dependency") : t("entityRelation")}`
                : `<strong>${tx(params.data.label ?? "")}</strong><br/>${tx(params.data.detail ?? "")}`,
          },
          legend: {
            data: groups.map(tx),
            bottom: 0,
            textStyle: { color: palette.muted, fontSize: 10 },
          },
          series: [
            {
              type: "graph",
              layout: "circular",
              roam: true,
              circular: { rotateLabel: false },
              categories: groups.map((name, index) => ({
                name: tx(name),
                itemStyle: { color: categoryColor(index) },
              })),
              data: visual.nodes.map((node) => ({
                name: node.id,
                label: node.label,
                detail: node.detail,
                category: Math.max(0, groups.indexOf(node.group)),
                symbol: node.role === "entity" ? "diamond" : "circle",
                symbolSize:
                  node.role === "entity"
                    ? 18 + Math.min(12, node.value * 3)
                    : 16 + Math.min(18, Math.sqrt(node.value) * 1.5),
                itemStyle: selected.has(node.id)
                  ? {
                      color: palette.green,
                      borderColor: "#dcffeb",
                      borderWidth: 2,
                      shadowBlur: 16,
                      shadowColor: palette.green,
                    }
                  : undefined,
              })),
              links: visual.edges.map((edge) => ({
                source: edge.source,
                target: edge.target,
                kind: edge.kind,
                symbol: edge.kind === "dependency" ? ["none", "arrow"] : ["none", "none"],
                lineStyle: {
                  color:
                    edge.kind === "conflict"
                      ? palette.amber
                      : edge.kind === "dependency"
                        ? palette.cyan
                        : palette.grid,
                  type: edge.kind === "dependency" ? "dashed" : "solid",
                  width: edge.kind === "conflict" ? 2 : 1.2,
                  opacity: 0.75,
                  curveness: 0.12,
                },
              })),
              label: { show: true, color: palette.text, fontSize: 10 },
              lineStyle: { color: palette.grid },
            },
          ],
        }}
      />
    );
  }

  if (visual.kind === "collateral-flow") {
    const labels = new Map(visual.nodes.map((node) => [node.id, node.label]));
    return (
      <ReactECharts
        className="chart-canvas scenario-chart"
        option={{
          ...common,
          tooltip: {
            ...tooltip,
            formatter: (params: {
              dataType: "node" | "edge";
              data: { name?: string; source?: string; target?: string; value: number; label?: string };
            }) =>
              params.dataType === "edge"
                ? `<strong>${tx(params.data.label ?? "")}</strong><br/>${t("coverage")} ${params.data.value} ${t("units")}`
                : `<strong>${tx(labels.get(params.data.name ?? "") ?? params.data.name ?? "")}</strong><br/>${params.data.value} ${t("units")}`,
          },
          series: [
            {
              type: "sankey",
              left: 20,
              right: 24,
              top: 22,
              bottom: 18,
              nodeWidth: 10,
              nodeGap: 9,
              draggable: false,
              data: visual.nodes.map((node) => ({
                name: node.id,
                value: node.value,
                label: node.label,
                itemStyle: {
                  color: node.role === "target" ? palette.amber : palette.cyan,
                  borderColor: palette.surface,
                },
              })),
              links: visual.edges.map((edge) => ({
                source: edge.source,
                target: edge.target,
                value: edge.value ?? 0,
                label: edge.label,
                lineStyle: {
                  color: selected.has(edge.id ?? "") ? palette.green : palette.cyan,
                  opacity: selected.has(edge.id ?? "") ? 0.78 : 0.22,
                },
              })),
              label: {
                color: palette.text,
                fontSize: 10,
                formatter: (params: { data: { label: string } }) => tx(params.data.label),
              },
              lineStyle: { curveness: 0.5 },
            },
          ],
        }}
      />
    );
  }

  if (visual.kind === "liquidity-timeline") {
    return (
      <ReactECharts
        className="chart-canvas scenario-chart"
        option={{
          ...common,
          tooltip: { ...tooltip, trigger: "axis" },
          legend: {
            data: visual.series.map((series) => tx(series.name)),
            top: 0,
            right: 12,
            textStyle: { color: palette.muted, fontSize: 10 },
          },
          grid: { left: 52, right: 22, top: 42, bottom: 48 },
          xAxis: {
            ...axis,
            type: "value",
            min: 540,
            max: 930,
            name: tx(visual.xLabel),
            axisLabel: { color: palette.muted, formatter: minuteLabel },
          },
          yAxis: { ...axis, type: "value", name: tx(visual.yLabel), minInterval: 1 },
          series: [
            ...visual.series.map((series, index) => ({
              name: tx(series.name),
              type: "line",
              step: "end",
              showSymbol: false,
              data: series.points.map((point) => [point.x, point.y]),
              lineStyle: { color: categoryColor(index), width: 2 },
              itemStyle: { color: categoryColor(index) },
            })),
            {
              name: t("optionalAction"),
              type: "scatter",
              data: visual.points.map((point) => ({
                name: tx(point.label),
                value: [point.x, point.y, point.size],
                detail: tx(point.detail),
                itemStyle: {
                  color: selected.has(point.id) ? palette.green : palette.text,
                  borderColor: selected.has(point.id) ? "#dcffeb" : palette.surface,
                  borderWidth: 2,
                  opacity: selected.has(point.id) ? 1 : 0.72,
                },
                symbolSize: 9 + point.size * 2,
              })),
            },
          ],
        }}
      />
    );
  }

  return (
    <ReactECharts
      className="chart-canvas scenario-chart"
      option={{
        ...common,
        tooltip: {
          ...tooltip,
          formatter: (params: {
            data: { name: string; value: [number, number, number, number]; detail: string };
          }) =>
            `<strong>${tx(params.data.name)}</strong><br/>${t("capitalCost")} ${params.data.value[0].toFixed(2)}<br/>${t("riskAdjustedValue")} ${params.data.value[1].toFixed(2)}<br/>${t("efficiency")} ${params.data.value[2].toFixed(2)}<br/>${tx(params.data.detail)}`,
        },
        legend: {
          data: visual.categories.map(tx),
          bottom: 0,
          textStyle: { color: palette.muted, fontSize: 10 },
        },
        grid: { left: 58, right: 24, top: 20, bottom: 52 },
        xAxis: { ...axis, type: "value", name: tx(visual.xLabel), scale: true },
        yAxis: { ...axis, type: "value", name: tx(visual.yLabel), scale: true },
        series: visual.categories.map((group, index) => ({
          name: tx(group),
          type: "scatter",
          data: visual.points
            .filter((point) => point.group === group)
            .map((point) => ({
              name: tx(point.label),
              detail: tx(point.detail),
              value: [point.x, point.y, point.value, point.size],
              symbolSize: 10 + point.size * 4,
              itemStyle: {
                color: selected.has(point.id) ? palette.green : categoryColor(index),
                opacity: selected.has(point.id) ? 1 : 0.62,
                borderColor: selected.has(point.id) ? "#dcffeb" : palette.surface,
                borderWidth: 2,
              },
            })),
        })),
      }}
    />
  );
}

export function MatrixHeatmap({ variables, cells }: { variables: string[]; cells: MatrixCell[] }) {
  const { tx } = useI18n();
  const index = new Map(variables.map((value, position) => [value, position]));
  const values = cells.map((cell) => [index.get(cell.right), index.get(cell.left), cell.value]);
  const max = Math.max(...cells.map((cell) => Math.abs(cell.value)), 1);
  return (
    <ReactECharts
      className="chart-canvas"
      option={{
        ...common,
        tooltip: {
          ...tooltip,
          formatter: (params: { data: [number, number, number] }) => {
            const [x, y, value] = params.data;
            return `${tx(variables[y])} × ${tx(variables[x])}<br/><strong>${value.toPrecision(5)}</strong>`;
          },
        },
        grid: { left: 66, right: 24, top: 22, bottom: 70 },
        xAxis: {
          ...axis,
          type: "category",
          data: variables.map(tx),
          axisLabel: { color: palette.muted, rotate: 45, formatter: (value: string) => value.slice(0, 8) },
          splitArea: { show: false },
        },
        yAxis: {
          ...axis,
          type: "category",
          data: variables.map(tx),
          axisLabel: { color: palette.muted, formatter: (value: string) => value.slice(0, 8) },
        },
        visualMap: {
          min: -max,
          max,
          calculable: false,
          orient: "horizontal",
          left: "center",
          bottom: 4,
          textStyle: { color: palette.muted, fontSize: 10 },
          inRange: { color: ["#b76545", "#18211f", palette.cyan] },
        },
        series: [{ type: "heatmap", data: values, emphasis: { itemStyle: { borderColor: palette.text } } }],
      }}
    />
  );
}

function equalRange(atoms: AtomPoint[]) {
  const values = atoms.flatMap((atom) => [atom.x, atom.y]);
  const minimum = Math.min(...values, 0);
  const maximum = Math.max(...values, 1);
  const padding = Math.max(1, (maximum - minimum) * 0.12);
  return { min: minimum - padding, max: maximum + padding };
}

export function AtomChart({ atoms }: { atoms: AtomPoint[] }) {
  const { t } = useI18n();
  const range = equalRange(atoms);
  return (
    <ReactECharts
      className="chart-canvas compact-chart"
      option={{
        ...common,
        tooltip: {
          ...tooltip,
          formatter: (params: { data: { name: string; value: [number, number]; selected: boolean } }) =>
            `<strong>${params.data.name}</strong><br/>(${params.data.value[0]}, ${params.data.value[1]}) μm<br/>${params.data.selected ? t("selected") : t("notSelected")}`,
        },
        grid: { left: 52, right: 26, top: 22, bottom: 42 },
        xAxis: { ...axis, type: "value", min: range.min, max: range.max, name: "x / μm" },
        yAxis: { ...axis, type: "value", min: range.min, max: range.max, name: "y / μm" },
        series: [
          {
            type: "scatter",
            data: atoms.map((atom) => ({
              name: atom.id,
              value: [atom.x, atom.y],
              selected: Boolean(atom.selected),
              symbolSize: atom.selected ? 21 : 13,
              itemStyle: {
                color: atom.selected ? palette.green : palette.cyan,
                shadowBlur: atom.selected ? 16 : 7,
                shadowColor: atom.selected ? palette.green : palette.cyan,
              },
            })),
            label: {
              show: atoms.length <= 12,
              position: "top",
              color: palette.muted,
              fontSize: 9,
              formatter: (params: { name: string }) => params.name.replace(/^(item_|risk_|trade_|alert_)/, ""),
            },
          },
        ],
      }}
    />
  );
}

export function waveformDisplaySeries(waveforms: QuantumPayload["waveforms"]) {
  const channels = [
    ["Rabi", "rabi", palette.green, 2, "solid", "circle"],
    ["Detuning", "detuning", palette.cyan, 0, "dashed", "triangle"],
    ["Phase", "phase", palette.amber, -2, "dotted", "diamond"],
  ] as const;
  return channels.map(([name, key, color, lane, lineType, symbol]) => ({
    name,
    type: "line",
    showSymbol: true,
    symbol,
    symbolSize: 5,
    smooth: false,
    data: waveforms[key].map((point) => [
      point.time,
      lane + point.value * 0.38,
      point.raw,
    ]),
    lineStyle: { color, width: 2, type: lineType },
    itemStyle: { color },
  }));
}

export function WaveformChart({ waveforms }: { waveforms: QuantumPayload["waveforms"] }) {
  const { t } = useI18n();
  return (
    <ReactECharts
      className="chart-canvas compact-chart"
      option={{
        ...common,
        tooltip: {
          ...tooltip,
          trigger: "axis",
          formatter: (items: Array<{ seriesName: string; value: [number, number, number] }>) => {
            const time = items[0]?.value[0] ?? 0;
            const rows = items.map(
              (item) => `${item.seriesName}: <strong>${item.value[2].toPrecision(5)}</strong>`,
            );
            return `${t("timeAxis")} ${time.toFixed(4)}<br/>${rows.join("<br/>")}`;
          },
        },
        legend: { top: 0, right: 10, textStyle: { color: palette.muted, fontSize: 10 } },
        grid: { left: 76, right: 22, top: 42, bottom: 42 },
        xAxis: { ...axis, type: "value", name: t("timeAxis") },
        yAxis: {
          ...axis,
          type: "value",
          min: -2.6,
          max: 2.6,
          interval: 2,
          name: t("waveformLane"),
          axisLabel: {
            ...axis.axisLabel,
            formatter: (value: number) =>
              value === 2 ? "Rabi" : value === 0 ? "Detuning" : value === -2 ? "Phase" : "",
          },
        },
        series: waveformDisplaySeries(waveforms),
      }}
    />
  );
}

export function CountsChart({ counts }: { counts: QuantumPayload["counts"] }) {
  const { tx } = useI18n();
  return (
    <ReactECharts
      className="chart-canvas counts-chart"
      option={{
        ...common,
        tooltip,
        grid: { left: 52, right: 20, top: 24, bottom: 84 },
        xAxis: {
          ...axis,
          type: "category",
          data: counts.map((item) => tx(item.state)),
          axisLabel: { color: palette.muted, rotate: 42, fontFamily: "monospace", fontSize: 9 },
        },
        yAxis: { ...axis, type: "value", name: "counts", minInterval: 1 },
        series: [
          {
            type: "bar",
            data: counts.map((item, index) => ({
              value: item.count,
              itemStyle: { color: index === 0 ? palette.green : palette.cyan, opacity: index === 0 ? 1 : 0.62 },
            })),
            barMaxWidth: 34,
          },
        ],
      }}
    />
  );
}

export function ParameterChart({ history }: { history: QuantumPayload["parameterHistory"] }) {
  const { t } = useI18n();
  return (
    <ReactECharts
      className="chart-canvas compact-chart"
      option={{
        ...common,
        tooltip: {
          ...tooltip,
          formatter: (raw: unknown) => {
            const point = raw as {
              name?: string;
              data?: {
                value: number;
                parameters: Record<string, number>;
              };
            };
            const data = point.data;
            if (!data) return point.name ?? "";
            const parameters = Object.entries(data.parameters)
              .map(([name, value]) => `${name}: ${value.toFixed(4)}`)
              .join("<br/>");
            return [
              point.name ?? "",
              `objective: ${data.value.toFixed(6)}`,
              parameters,
            ].filter(Boolean).join("<br/>");
          },
        },
        grid: { left: 58, right: 20, top: 22, bottom: 42 },
        xAxis: { ...axis, type: "category", data: history.map((item) => `P${item.index + 1}`), name: t("parameterPointAxis") },
        yAxis: { ...axis, type: "value", name: "objective", scale: true },
        series: [
          {
            type: "line",
            data: history.map((item) => ({
              value: item.objective,
              parameters: item.parameters,
              itemStyle: { color: item.selected ? palette.green : palette.cyan },
              symbolSize: item.selected ? 12 : 8,
            })),
            lineStyle: { color: palette.cyan, width: 2 },
          },
        ],
      }}
    />
  );
}
