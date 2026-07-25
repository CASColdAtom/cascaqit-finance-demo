// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AnalysisPayload, ScenarioSpec } from "./types";

const api = vi.hoisted(() => ({
  analyzeScenario: vi.fn(),
  getScenarios: vi.fn(),
  runScenario: vi.fn(),
}));

vi.mock("./api", () => api);

import App from "./App";

const scenario: ScenarioSpec = {
  caseId: "portfolio",
  shortTitle: "投资组合",
  title: "多资产投资组合优化",
  eyebrow: "DENSE COVARIANCE",
  description: "在收益、风险和行业约束之间选择组合。",
  icon: "chart-no-axes-combined",
  accent: "cyan",
  presets: [{ value: "base", label: "基准市场" }],
  controls: [],
  values: { risk_weight: 0.5 },
  recommendedMode: "digital",
  recommendedExecution: {
    shots: 128,
    seed: 23,
    layers: 2,
    searchStrategy: "preset",
    parameterBudget: 2,
  },
};

const analysis: AnalysisPayload = {
  caseId: "portfolio",
  inputRows: [],
  problem: {
    id: "finance.portfolio",
    type: "qubo",
    hash: "problem-hash",
    variables: ["asset_00"],
    matrix: { variables: ["asset_00"], cells: [] },
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
  resource: {
    logical_variables: 1,
    logical_terms: 1,
    state_vector_dimension: 2,
  },
  layout: [],
  scenarioVisual: {
    kind: "portfolio-correlation",
    title: "资产相关性矩阵",
    subtitle: "当前资产关系。",
    xLabel: "资产",
    yLabel: "资产",
    categories: [],
    nodes: [],
    edges: [],
    points: [],
    matrix: { xLabels: [], yLabels: [], cells: [] },
    series: [],
  },
  decision: {
    recommendedMode: "digital",
    reason: "稠密协方差与全局约束使用 Digital。",
    modes: [
      {
        mode: "digital",
        algorithm: "qaoa",
        status: "recommended",
        compilerFeasible: true,
        businessSuitable: true,
        reason: "推荐",
        diagnosticCodes: [],
        analogTermCount: 0,
        digitalTermCount: 1,
        analogBusinessPairs: [],
        coveredGroupIds: [],
        missingContributionIds: [],
        unexpectedAnalogTermIds: [],
        unexpectedInteractionPairs: [],
        geometryStatus: "missing",
        geometrySource: null,
        layoutPolicy: "deterministic_grid",
        declaredContributionCount: 0,
        coveredContributionCount: 0,
      },
    ],
  },
};

beforeEach(() => {
  api.getScenarios.mockResolvedValue([scenario]);
  api.analyzeScenario.mockResolvedValue({
    scenario,
    preset: "base",
    analysis,
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("App", () => {
  it("loads the catalog, analyzes the default input, and resolves the deferred view", async () => {
    render(<App />);

    expect(screen.getByText("正在连接实验服务")).toBeTruthy();
    expect(
      await screen.findByRole("heading", { name: "多资产投资组合优化" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("img", { name: "CASColdAtom 中科酷原" }).getAttribute("src"),
    ).toBe("/cascoldatom-logo-transparent.png");
    expect(await screen.findByText("资产相关性矩阵")).toBeTruthy();
    expect(
      screen.getByRole("tab", { name: "场景态势" }).getAttribute("aria-selected"),
    ).toBe("true");
    expect(api.analyzeScenario).toHaveBeenCalledWith(
      "portfolio",
      { preset: "base", values: scenario.values },
      expect.any(AbortSignal),
    );
    expect(screen.queryByText("运行后显示场景结构")).toBeNull();
    expect((screen.getByLabelText("QAOA 层数") as HTMLSelectElement).value).toBe("2");
    expect((screen.getByLabelText("Shots") as HTMLSelectElement).value).toBe("128");
    expect(screen.getByText("推荐执行配置")).toBeTruthy();
  });

  it("switches the workbench shell and scenario metadata to English", async () => {
    render(<App />);

    await screen.findByRole("heading", { name: "多资产投资组合优化" });
    fireEvent.click(screen.getByRole("button", { name: "EN" }));

    expect(
      screen.getByRole("heading", { name: "Multi-asset Portfolio Optimization" }),
    ).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Scenario View" })).toBeTruthy();
    expect(document.title).toBe("CASColdAtom Financial Quantum Workbench");
    expect(screen.getByRole("button", { name: "RUN" })).toBeTruthy();
  });
});
