// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AnalysisPayload, ScenarioSpec } from "../types";
import { I18nProvider } from "../i18n";
import { ControlPanel } from "./ControlPanel";

afterEach(cleanup);

const scenario: ScenarioSpec = {
  caseId: "settlement",
  shortTitle: "交易结算",
  title: "交易结算批次优化",
  eyebrow: "CONFLICT GRAPH + LIQUIDITY",
  description: "局域冲突与全局约束。",
  icon: "landmark",
  accent: "emerald",
  presets: [{ value: "base", label: "日常批次" }],
  controls: [
    {
      key: "weight",
      label: "金额权重",
      kind: "range",
      minimum: 0.2,
      maximum: 0.8,
      step: 0.1,
      options: [],
      unit: "",
    },
  ],
  values: { weight: 0.5 },
  recommendedMode: "hybrid",
  recommendedExecution: {
    shots: 32,
    seed: 23,
    layers: 1,
    searchStrategy: "preset",
    parameterBudget: 2,
  },
};

const analysis = {
  caseId: "settlement",
  inputRows: [],
  problem: {
    id: "finance.settlement",
    type: "qubo",
    hash: "problem-hash",
    variables: [],
    matrix: { variables: [], cells: [] },
    termGroups: [],
    coefficientLedger: {
      applicability: "qubo",
      balanced: true,
      hamiltonianBalanced: true,
      contributionCount: 0,
      canonicalTermCount: 0,
      rows: [],
    },
  },
  resource: {},
  layout: [],
  scenarioVisual: {
    kind: "settlement-network",
    title: "交易冲突与前置依赖",
    subtitle: "当前批次结构。",
    xLabel: "",
    yLabel: "",
    categories: [],
    nodes: [],
    edges: [],
    points: [],
    matrix: { xLabels: [], yLabels: [], cells: [] },
    series: [],
  },
  decision: {
    recommendedMode: "hybrid",
    reason: "冲突项进入 Analog，其余约束保留为 Digital residual。",
    modes: [
      {
        mode: "digital",
        algorithm: "qaoa",
        status: "comparable",
        compilerFeasible: true,
        businessSuitable: true,
        reason: "可比较",
        diagnosticCodes: [],
        analogTermCount: 0,
        digitalTermCount: 8,
        analogBusinessPairs: [],
        coveredGroupIds: [],
        missingContributionIds: [],
        unexpectedAnalogTermIds: [],
        unexpectedInteractionPairs: [],
        geometryStatus: "missing",
        geometrySource: null,
        layoutPolicy: "provided",
        declaredContributionCount: 0,
        coveredContributionCount: 0,
      },
      {
        mode: "hybrid",
        algorithm: "qaoa",
        status: "recommended",
        compilerFeasible: true,
        businessSuitable: true,
        reason: "推荐",
        diagnosticCodes: [],
        analogTermCount: 3,
        digitalTermCount: 5,
        analogBusinessPairs: [["a", "b"]],
        coveredGroupIds: ["conflicts"],
        missingContributionIds: [],
        unexpectedAnalogTermIds: [],
        unexpectedInteractionPairs: [],
        geometryStatus: "verified",
        geometrySource: "verified_embedding",
        layoutPolicy: "provided",
        declaredContributionCount: 1,
        coveredContributionCount: 1,
      },
      {
        mode: "analog",
        algorithm: "qaa",
        status: "unsuitable",
        compilerFeasible: false,
        businessSuitable: false,
        reason: "无法完整表达",
        diagnosticCodes: ["PROBLEM_AHS_NOT_EXPRESSIBLE"],
        analogTermCount: 0,
        digitalTermCount: 0,
        analogBusinessPairs: [],
        coveredGroupIds: [],
        missingContributionIds: [],
        unexpectedAnalogTermIds: [],
        unexpectedInteractionPairs: [],
        geometryStatus: "verified",
        geometrySource: "verified_embedding",
        layoutPolicy: "provided",
        declaredContributionCount: 1,
        coveredContributionCount: 1,
      },
    ],
  },
} satisfies AnalysisPayload;

function renderPanel(
  overrides: {
    running?: boolean;
    analyzing?: boolean;
    mode?: "digital" | "hybrid" | "analog";
    recommendedConfiguration?: boolean;
  } = {},
) {
  const onMode = vi.fn();
  const onRun = vi.fn();
  const onLayers = vi.fn();
  const onSearchStrategy = vi.fn();
  render(
    <I18nProvider initialLanguage="zh">
      <ControlPanel
        scenario={scenario}
        preset="base"
        values={scenario.values}
        analysis={analysis}
        mode={overrides.mode ?? "hybrid"}
        shots={32}
        seed={23}
        layers={1}
        searchStrategy="preset"
        parameterBudget={2}
        optimizerStarts={1}
        repeats={1}
        recommendedConfiguration={overrides.recommendedConfiguration ?? true}
        running={overrides.running ?? false}
        analyzing={overrides.analyzing ?? false}
        onPreset={vi.fn()}
        onValue={vi.fn()}
        onMode={onMode}
        onShots={vi.fn()}
        onSeed={vi.fn()}
        onLayers={onLayers}
        onSearchStrategy={onSearchStrategy}
        onParameterBudget={vi.fn()}
        onOptimizerStarts={vi.fn()}
        onRepeats={vi.fn()}
        onRun={onRun}
        onReset={vi.fn()}
      />
    </I18nProvider>,
  );
  return { onLayers, onMode, onRun, onSearchStrategy };
}

describe("ControlPanel", () => {
  it("exposes a compact control toggle for narrow layouts", () => {
    renderPanel();
    const toggle = screen.getByRole("button", { name: /参数与执行/ });

    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(toggle.getAttribute("aria-controls")).toBe("control-panel-body");

    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
  });

  it("switches comparable modes and blocks unsuitable modes", () => {
    const { onMode } = renderPanel();

    fireEvent.click(screen.getByRole("button", { name: /digital/i }));

    expect(onMode).toHaveBeenCalledWith("digital");
    expect(
      (screen.getByRole("button", { name: /analog/i }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(
      screen.getByRole("button", { name: /hybrid/i }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("shows the reason for the selected comparison mode", () => {
    renderPanel({ mode: "digital" });

    expect(screen.getByText("可比较")).toBeTruthy();
  });

  it("identifies recommended and custom execution configurations", () => {
    renderPanel();
    expect(screen.getByText("推荐执行配置")).toBeTruthy();

    cleanup();
    renderPanel({ recommendedConfiguration: false });
    expect(screen.getByText("自定义执行配置")).toBeTruthy();
  });

  it("shows QAOA search controls only for Digital mode", () => {
    const { onLayers, onSearchStrategy } = renderPanel({ mode: "digital" });

    fireEvent.change(screen.getByLabelText("QAOA 层数"), {
      target: { value: "2" },
    });
    fireEvent.change(screen.getByLabelText("参数搜索"), {
      target: { value: "seeded_sample" },
    });

    expect(onLayers).toHaveBeenCalledWith(2);
    expect(onSearchStrategy).toHaveBeenCalledWith("seeded_sample");
    cleanup();
    renderPanel({ mode: "hybrid" });
    expect(screen.queryByLabelText("QAOA 层数")).toBeNull();
  });

  it("prevents duplicate execution while a run is active", () => {
    const { onRun } = renderPanel({ running: true });
    const runButton = screen.getByRole("button", { name: "执行中" });

    expect((runButton as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(runButton);
    expect(onRun).not.toHaveBeenCalled();
  });
});
