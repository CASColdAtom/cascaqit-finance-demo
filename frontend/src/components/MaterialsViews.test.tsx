// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type {
  MaterialsAnalysisPayload,
  MaterialsRunPayload,
} from "../types";
import { I18nProvider } from "../i18n";
import { MaterialsView } from "./MaterialsViews";

const analysis = {
  kind: "materials",
  caseId: "defect_adsorption",
  executionFamily: "problem",
  implementationStatus: "available",
  analysisHash: "analysis-hash",
  dataset: {
    id: "materials.fixture",
    version: "1",
    manifestHash: "manifest-hash",
    sourceKind: "project_generated",
    license: "project_generated",
    limitations: ["offline model"],
  },
  problem: {
    id: "materials.qubo",
    type: "qubo",
    hash: "problem-hash",
    variables: ["defect.d0", "ads.a0", "ads.a1"],
    terms: [],
    termGroups: [
      {
        group_id: "local_conflicts",
        label: "同位点与取向互斥",
        kind: "pairwise_conflict",
        variables: [],
        pairs: [["ads.a0", "ads.a1"]],
      },
    ],
    coefficientLedger: {
      balanced: true,
      contributionCount: 3,
      canonicalTermCount: 3,
      rows: [],
    },
  },
  resource: { logical_variables: 3 },
  decision: {
    recommendedMode: "hybrid",
    reason: "verified local conflict block",
    modes: [
      {
        mode: "hybrid",
        algorithm: "qaoa",
        status: "recommended",
        reason: "verified",
        analogTermCount: 2,
        digitalTermCount: 5,
      },
    ],
  },
  domain: {
    kind: "defect_adsorption",
    modelLevel: "joint model",
    surface: "CeO2(111)",
    nodes: [
      { id: "site.0", label: "S1", x: 14, y: 22, role: "lattice_site" },
    ],
    adsorbates: [
      { id: "ads.a0", site: "site.0", label: "CO", orientation: "top" },
    ],
    localConflictPairs: [["ads.a0", "ads.a1"]],
    limitations: ["offline model"],
  },
} as MaterialsAnalysisPayload;

const solution = {
  source: "complete_enumeration",
  bitstring: "110",
  selectedDefectIds: ["defect.d0"],
  selectedAdsorptionIds: ["ads.a0"],
  modelObjective: -1.2,
  physicalModelEnergy: -1.2,
  energyComponents: { adsorption: -1.2 },
  feasible: true,
  checks: [
    {
      id: "coverage",
      label: "吸附覆盖度",
      passed: true,
      actual: 1,
      expected: 1,
    },
  ],
};

const run = {
  kind: "materials",
  analysis,
  domain: {
    kind: "defect_adsorption_result",
    quantumStatus: "quantum_not_observed",
    quantumCandidate: null,
    bestObservedRaw: { ...solution, feasible: false, source: "quantum_observed_raw" },
    classicOptimum: solution,
    offlineReference: { ...solution, source: "offline_reference" },
    topObservedFeasible: [],
    observedFeasibleCount: 0,
    feasibleShotRatio: 0,
    interpretation: "离散模型边界",
  },
  quantum: {
    kind: "problem_qaoa",
    mode: "hybrid",
    algorithm: "qaoa",
    topology: "hybrid",
    layerCount: 1,
    blocks: ["digital", "analog", "digital"],
    layers: ["H", "A", "M"],
    circuit: { qubits: ["q0"], gates: [], depth: 0 },
    atoms: [{ id: "q0", x: 0, y: 0, selected: false }],
    waveforms: { rabi: [], detuning: [], phase: [] },
    counts: [{ state: "000", count: 32, rank: 1 }],
    parameterHistory: [
      { index: 0, objective: 0.4, parameters: { gamma_0: 0.2 }, selected: true },
    ],
    termMapping: [],
    summary: { analogTerms: 2, digitalTerms: 5, qubits: 3, shots: 32, evaluations: 1 },
  },
  audit: {
    domainId: "materials",
    caseId: "defect_adsorption",
    datasetId: "materials.fixture",
    datasetVersion: "1",
    manifestHash: "manifest-hash",
    domainInputHash: "input-hash",
    problemHash: "problem-hash",
    analysisHash: "analysis-hash",
    compileHash: "compile-hash",
    executionHash: "execution-hash",
    resultHash: "result-hash",
    reportHash: "report-hash",
    backendHash: "backend-hash",
    configurationHash: "configuration-hash",
    outcomeHash: "outcome-hash",
    seed: 23,
    shots: 32,
    hardwareExecution: false,
    cloudExecution: false,
    networkAccessed: false,
    wallTimeSeconds: 0.2,
    optimalityClaim: "not_claimed",
    claimBoundary: "packaged model",
  },
} as MaterialsRunPayload;

afterEach(cleanup);

function renderMaterials(view: "comparison" | "quantum") {
  return render(
    <I18nProvider initialLanguage="zh">
      <MaterialsView analysis={analysis} run={run} view={view} />
    </I18nProvider>,
  );
}

describe("MaterialsViews", () => {
  it("keeps a missing quantum candidate separate from classic references", () => {
    renderMaterials("comparison");

    expect(screen.getByText("NOT OBSERVED")).toBeTruthy();
    expect(screen.getByText("EXACT ENUMERATION")).toBeTruthy();
    expect(screen.getByText("OFFLINE REFERENCE")).toBeTruthy();
    expect(screen.getByText("不以经典结果回填")).toBeTruthy();
  });

  it("renders Hybrid analog and Digital residual evidence", () => {
    renderMaterials("quantum");

    expect(screen.getAllByText("HYBRID").length).toBeGreaterThan(0);
    expect(screen.getByText("构型位串 counts")).toBeTruthy();
    expect(screen.getByText("独立 Rydberg 编译坐标")).toBeTruthy();
    expect(screen.queryByText("材料 QUBO 执行链尚未开放")).toBeNull();
  });
});
