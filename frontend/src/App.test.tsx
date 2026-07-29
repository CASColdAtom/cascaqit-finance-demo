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
vi.mock("./components/charts/Charts", () => ({
  AtomChart: () => null,
  BusinessChart: () => null,
  CountsChart: () => null,
  MatrixHeatmap: () => null,
  ParameterChart: () => null,
  LayerObjectiveChart: () => null,
  ScenarioChart: () => null,
  WaveformChart: () => null,
}));

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
  vi.resetAllMocks();
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
    expect((screen.getByLabelText("变分层数") as HTMLSelectElement).value).toBe("2");
    expect((screen.getByLabelText("Shots") as HTMLSelectElement).value).toBe("128");
    expect(screen.getByText("推荐执行配置")).toBeTruthy();
    expect(screen.queryByRole("option", { name: "VQE" })).toBeNull();
  });

  it("does not publish collateral VQE before calibration passes", async () => {
    const collateralScenario: ScenarioSpec = {
      ...scenario,
      caseId: "collateral",
      shortTitle: "抵押品",
      title: "抵押品分配优化",
      values: {},
      recommendedExecution: {
        shots: 32,
        seed: 23,
        layers: 1,
        searchStrategy: "preset",
        parameterBudget: 2,
      },
    };
    const collateralAnalysis: AnalysisPayload = {
      ...analysis,
      caseId: "collateral",
      problem: {
        ...analysis.problem,
        id: "finance.collateral",
        variables: Array.from({ length: 8 }, (_, index) => `x_${index}`),
      },
      decision: {
        ...analysis.decision,
        modes: analysis.decision.modes.map((row) => ({
          ...row,
          availableAlgorithms: ["qaoa"],
        })),
      },
    };
    api.getScenarios.mockResolvedValueOnce([collateralScenario]);
    api.analyzeScenario.mockResolvedValueOnce({
      scenario: collateralScenario,
      preset: "base",
      analysis: collateralAnalysis,
    });

    render(<App />);

    await screen.findByRole("heading", { name: "抵押品分配优化" });
    await screen.findByText("资产相关性矩阵");
    expect(screen.queryByRole("option", { name: "VQE" })).toBeNull();
    expect((screen.getByLabelText("变分算法") as HTMLSelectElement).value).toBe(
      "recommended",
    );
  });

  it("switches from fixed layers to a bounded adaptive search", async () => {
    render(<App />);

    await screen.findByRole("heading", { name: "多资产投资组合优化" });
    await screen.findByText("资产相关性矩阵");
    fireEvent.change(screen.getByLabelText("层数方式"), {
      target: { value: "adaptive" },
    });

    expect(screen.queryByLabelText("变分层数")).toBeNull();
    expect((screen.getByLabelText("最大层数") as HTMLSelectElement).value).toBe("3");
    expect((screen.getByLabelText("参数搜索") as HTMLSelectElement).value).toBe(
      "continuous",
    );
    expect((screen.getByLabelText("参数搜索") as HTMLSelectElement).disabled).toBe(
      true,
    );
  });

  it("uses a safe profile when an older catalog omits recommendedExecution", async () => {
    const legacyScenario = { ...scenario, recommendedExecution: undefined };
    api.getScenarios.mockResolvedValueOnce([legacyScenario]);
    api.analyzeScenario.mockResolvedValueOnce({
      scenario: legacyScenario,
      preset: "base",
      analysis,
    });

    render(<App />);

    await screen.findByRole("heading", { name: "多资产投资组合优化" });
    expect((screen.getByLabelText("Shots") as HTMLSelectElement).value).toBe("32");
    expect((screen.getByLabelText("变分层数") as HTMLSelectElement).value).toBe("1");
  });

  it("keeps Problem mapping usable with the previous analysis schema", async () => {
    const legacyAnalysis = {
      ...analysis,
      problem: {
        ...analysis.problem,
        coefficientLedger: undefined,
        termGroups: [
          {
            group_id: "legacy-group",
            label: "旧版业务分组",
            kind: "objective",
          },
        ],
      },
      decision: {
        ...analysis.decision,
        modes: analysis.decision.modes.map((row) => ({
          mode: row.mode,
          algorithm: row.algorithm,
          status: row.status,
          compilerFeasible: row.compilerFeasible,
          businessSuitable: row.businessSuitable,
          reason: row.reason,
          diagnosticCodes: row.diagnosticCodes,
          analogTermCount: row.analogTermCount,
          digitalTermCount: row.digitalTermCount,
          analogBusinessPairs: row.analogBusinessPairs,
        })),
      },
    } as unknown as AnalysisPayload;
    api.analyzeScenario.mockResolvedValue({
      scenario: { ...scenario, recommendedExecution: undefined },
      preset: "base",
      analysis: legacyAnalysis,
    });

    render(<App />);

    await screen.findByText("资产相关性矩阵");
    fireEvent.click(screen.getByRole("tab", { name: "Problem 映射" }));
    expect(await screen.findByText("PROBLEM HASH")).toBeTruthy();
    expect(document.querySelector(".term-groups")?.textContent).toContain("旧版业务分组");
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
