// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AnalysisPayload,
  BiomedicineAnalysisPayload,
  MaterialsAnalysisPayload,
  ScenarioSpec,
} from "./types";

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

const biomedicineScenario: ScenarioSpec = {
  domainId: "biomedicine",
  caseId: "electronic_structure",
  shortTitle: "电子结构",
  title: "小分子活性空间基态能量估计",
  eyebrow: "PAULI HAMILTONIAN / DIGITAL VQE",
  description: "从可审计的 H2 Hamiltonian 出发。",
  icon: "atom",
  accent: "emerald",
  presets: [{ value: "h2_equilibrium", label: "H2 / 0.735 Å" }],
  controls: [],
  values: {},
  recommendedMode: "digital",
  executionFamily: "pauli_vqe",
  implementationStatus: "available",
  recommendedExecution: {
    shots: 64,
    seed: 23,
    algorithm: "vqe",
    layers: 1,
    maxLayers: 1,
    searchStrategy: "continuous",
    parameterBudget: 40,
    optimizerStarts: 2,
  },
};

const biomedicineAnalysis: BiomedicineAnalysisPayload = {
  kind: "biomedicine",
  caseId: "electronic_structure",
  executionFamily: "pauli_vqe",
  implementationStatus: "available",
  analysisHash: "analysis-hash",
  dataset: {
    id: "electronic.h2.sto3g.0735",
    version: "1",
    manifestHash: "manifest-hash",
    sourceKind: "project_generated_benchmark",
    license: "project_generated",
    limitations: ["Local simulation only"],
  },
  problem: {
    id: "electronic.h2.sto3g.0735",
    type: "pauli_hamiltonian",
    hash: "hamiltonian-hash",
    variables: ["q0", "q1"],
    terms: [],
  },
  resource: { logicalQubits: 2 },
  decision: {
    recommendedMode: "digital",
    reason: "Digital VQE",
    modes: [
      {
        mode: "digital",
        algorithm: "vqe",
        availableAlgorithms: ["vqe"],
        status: "recommended",
        reason: "Digital VQE",
      },
    ],
  },
  domain: {
    kind: "electronic_structure",
    molecule: "H2",
    geometryLabel: "平衡键长基准",
    atoms: [
      { id: "H1", element: "H", x: 24, y: 50 },
      { id: "H2", element: "H", x: 76, y: 50 },
    ],
    bonds: [{ source: "H1", target: "H2", order: 1 }],
    limitations: ["Local simulation only"],
  },
};

const materialsScenario: ScenarioSpec = {
  domainId: "materials",
  caseId: "rydberg_dynamics",
  shortTitle: "Rydberg 动力学",
  title: "材料缺陷晶格中的 Rydberg 动力学与量子淬火",
  eyebrow: "NATIVE AHS / PURE ANALOG",
  description: "演化材料有效晶格对应的原生 Rydberg Hamiltonian。",
  icon: "activity",
  accent: "emerald",
  presets: [{ value: "single_vacancy", label: "单空位传播" }],
  controls: [],
  values: {},
  recommendedMode: "analog",
  executionFamily: "analog_ahs",
  implementationStatus: "available",
  recommendedExecution: {
    shots: 128,
    seed: 23,
    algorithm: "qaa",
    layers: 1,
    maxLayers: 1,
    searchStrategy: "preset",
    parameterBudget: 2,
  },
};

const materialsAnalysis: MaterialsAnalysisPayload = {
  kind: "materials",
  caseId: "rydberg_dynamics",
  executionFamily: "analog_ahs",
  implementationStatus: "available",
  analysisHash: "materials-analysis-hash",
  dataset: {
    id: "materials.preview.rydberg",
    version: "design-1",
    manifestHash: "materials-manifest-hash",
    sourceKind: "project_generated_design_preview",
    license: "project_generated",
    limitations: ["不执行 AHS 时间演化"],
  },
  problem: {
    id: "materials.preview.rydberg",
    type: "analog_experiment_definition",
    hash: "materials-problem-hash",
    variables: ["site.0", "site.1"],
    terms: [],
  },
  resource: { logicalQubits: 1 },
  decision: {
    recommendedMode: "analog",
    reason: "完整有效 Hamiltonian 已通过 Pure Analog AHS 门禁。",
    modes: [
      { mode: "analog", algorithm: "qaa", status: "recommended", reason: "纯 Analog" },
    ],
  },
  domain: {
    kind: "rydberg_dynamics",
    modelLevel: "材料有效多体晶格 / 原生 AHS",
    nodes: [
      { id: "site.0", label: "S1", x: 14, y: 22, role: "lattice_site" },
      { id: "site.1", label: "S2", x: 38, y: 22, role: "vacancy" },
    ],
    rydbergLayout: [
      { id: "atom.0", sourceSite: "site.0", x: 10, y: 10, active: true },
      { id: "atom.1", sourceSite: "site.1", x: 15.6, y: 10, active: false },
    ],
    sampleTimes: [0, 0.6, 1.2],
    pulse: { duration: 1.2, rabiPeak: 2.4, detuningStart: -2, detuningEnd: 2 },
    pureAnalogEvidence: {
      digitalGateCount: 0,
      digitalResidualCount: 0,
      hybridBlockCount: 0,
      status: "verified",
    },
    limitations: ["四位点材料派生有效模型"],
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
  it("opens the executable materials Analog scenario without a digital circuit", async () => {
    api.getScenarios.mockImplementation((domainId?: string) =>
      Promise.resolve(domainId === "materials" ? [materialsScenario] : [scenario]),
    );
    api.analyzeScenario.mockImplementation((caseId: string) =>
      Promise.resolve(
        caseId === "rydberg_dynamics"
          ? {
              scenario: materialsScenario,
              preset: "single_vacancy",
              analysis: materialsAnalysis,
            }
          : { scenario, preset: "base", analysis },
      ),
    );

    render(<App />);
    await screen.findByRole("heading", { name: "多资产投资组合优化" });
    fireEvent.click(screen.getByRole("button", { name: "材料科学" }));

    expect(
      await screen.findByRole("heading", {
        name: "材料缺陷晶格中的 Rydberg 动力学与量子淬火",
      }),
    ).toBeTruthy();
    expect(await screen.findByText("周期晶格与缺陷")).toBeTruthy();
    expect(screen.getByText("前沿探索价值")).toBeTruthy();
    expect(screen.getByText(/当前量子计算尚不能替代成熟经典计算流程/)).toBeTruthy();
    expect(
      (screen.getByRole("button", { name: "运行" }) as HTMLButtonElement).disabled,
    ).toBe(false);
    expect(screen.queryByText("数字量子线路")).toBeNull();
    expect(screen.queryByText("digital")).toBeNull();
    expect(screen.queryByText("hybrid")).toBeNull();
    expect(screen.queryByText("QUBO")).toBeNull();
    expect(window.location.pathname).toBe("/materials/rydberg_dynamics");
  });

  it("switches domains without mixing finance and biomedicine navigation", async () => {
    api.getScenarios.mockImplementation((domainId?: string) =>
      Promise.resolve(domainId === "biomedicine" ? [biomedicineScenario] : [scenario]),
    );
    api.analyzeScenario.mockImplementation((caseId: string) =>
      Promise.resolve(
        caseId === "electronic_structure"
          ? {
              scenario: biomedicineScenario,
              preset: "h2_equilibrium",
              analysis: biomedicineAnalysis,
            }
          : { scenario, preset: "base", analysis },
      ),
    );

    render(<App />);
    await screen.findByRole("heading", { name: "多资产投资组合优化" });
    fireEvent.click(screen.getByRole("button", { name: "生物医药" }));

    expect(
      await screen.findByRole("heading", { name: "小分子活性空间基态能量估计" }),
    ).toBeTruthy();
    expect(screen.queryByText("投资组合")).toBeNull();
    expect(screen.getAllByText("电子结构").length).toBeGreaterThan(0);
    expect(screen.getByText("前沿探索价值")).toBeTruthy();
    expect(screen.getByText(/量子计算进入真实科研流程的前景/)).toBeTruthy();
    expect(screen.getByRole("tab", { name: "对照分析" })).toBeTruthy();
    expect(screen.getByTitle("变分量子本征求解器")).toBeTruthy();
    expect(window.location.pathname).toBe("/biomedicine/electronic_structure");
    await waitFor(() => {
      expect(api.analyzeScenario).toHaveBeenLastCalledWith(
        "electronic_structure",
        { preset: "h2_equilibrium", values: {} },
        expect.any(AbortSignal),
        "biomedicine",
      );
    });
  });

  it("loads the catalog, analyzes the default input, and resolves the deferred view", async () => {
    render(<App />);

    expect(screen.getByText("正在连接实验服务")).toBeTruthy();
    expect(
      await screen.findByRole("heading", { name: "多资产投资组合优化" }),
    ).toBeTruthy();
    expect(screen.queryByText("前沿探索价值")).toBeNull();
    expect(
      screen.getByRole("img", { name: "CASColdAtom 中科酷原" }).getAttribute("src"),
    ).toBe("/cascoldatom-logo-transparent.png");
    expect(await screen.findByText("资产相关性矩阵")).toBeTruthy();
    expect(
      screen.getByRole("tab", { name: "场景结构" }).getAttribute("aria-selected"),
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
    expect(screen.queryByRole("tab", { name: "对照分析" })).toBeNull();
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
    fireEvent.click(screen.getByRole("tab", { name: "Problem / Hamiltonian 映射" }));
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
    expect(screen.getByRole("tab", { name: "Scenario Structure" })).toBeTruthy();
    expect(document.title).toBe("CASColdAtom Industry Quantum Workbench");
    expect(screen.getByRole("button", { name: "RUN" })).toBeTruthy();
  });
});
