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

const analogAnalysis = {
  ...analysis,
  caseId: "rydberg_dynamics",
  executionFamily: "analog_ahs",
  problem: {
    id: "materials.ahs.single_vacancy",
    type: "analog_experiment_definition",
    hash: "analog-problem-hash",
    variables: ["q0", "q1", "q2", "q3"],
    terms: [],
  },
  resource: { analogSites: 4, sampleCount: 3 },
  decision: {
    recommendedMode: "analog",
    reason: "complete AHS mapping",
    modes: [{ mode: "analog", algorithm: "qaa", status: "recommended", reason: "AHS" }],
  },
  domain: {
    kind: "rydberg_dynamics",
    modelLevel: "four-site effective model",
    nodes: [
      { id: "site.0", label: "S1", x: 14, y: 22, role: "lattice_site", inActiveWindow: true },
      { id: "site.1", label: "S2", x: 38, y: 22, role: "vacancy", inActiveWindow: false },
    ],
    rydbergLayout: [
      { id: "q0", sourceSite: "site.0", x: 0, y: 0, active: true },
      { id: "q1", sourceSite: "site.2", x: 5.6, y: 0, active: true },
      { id: "q2", sourceSite: "site.3", x: 11.2, y: 0, active: true },
      { id: "q3", sourceSite: "site.4", x: 16.8, y: 0, active: true },
    ],
    sampleTimes: [0, 0.6, 1.2],
    pulse: { duration: 1.2, rabiPeak: 2.4, detuningStart: -2, detuningEnd: 2 },
    pulseSchedule: {
      duration: 1.2,
      timeUnit: "us",
      rabi: { times: [0, 0.3, 0.9, 1.2], values: [0, 2.4, 2.4, 0], unit: "rad/us" },
      detuning: { times: [0, 1.2], values: [-2, 2], unit: "rad/us" },
      localDetuning: { amplitude: 0, weights: [0, 0, 0, 0], unit: "rad/us" },
      phase: 0,
    },
    initialState: {
      bitstring: "1000",
      basis: "ground_rydberg_occupation",
      atomOrder: ["q0", "q1", "q2", "q3"],
      stateHash: "initial-state-hash",
      source: "declared_fixture",
    },
    pureAnalogEvidence: {
      status: "verified",
      digitalGateCount: 0,
      digitalResidualCount: 0,
      hybridBlockCount: 0,
      declaredHamiltonianTermCount: 5,
      mappedHamiltonianTermCount: 5,
      missingTermIds: [],
      unexpectedTermIds: [],
    },
    limitations: ["four-site effective model"],
  },
} as MaterialsAnalysisPayload;

const analogPoints = [0, 0.6, 1.2].map((time, index) => ({
  requestedTime: time,
  actualTime: time,
  timeUnit: "us",
  programHash: index === 0 ? null : `program-${index}`,
  stateHash: `state-${index}`,
  resultHash: `result-${index}`,
  probabilityNorm: 1,
  occupation: { q0: 1 - index * 0.2, q1: index * 0.1, q2: index * 0.05, q3: index * 0.05 },
  meanExcitation: 0.25,
  magnetizationZ: -0.5,
  correlations: { "q0,q1": -0.4 },
  counts: [{ state: "1000", count: 24 - index * 2 }],
  diagnosticCodes: [index === 0 ? "DECLARED_INITIAL_STATE" : "SIMULATION_COMPLETED"],
  solver: index === 0 ? "declared_initial_state" : "cascaqit.AnalogStateVectorKernel.reference_rk4",
}));

const analogRun = {
  kind: "materials",
  analysis: analogAnalysis,
  domain: {
    kind: "rydberg_dynamics_result",
    analogStatus: "completed",
    classicReference: {
      source: "independent_scipy_dop853",
      method: "DOP853",
      rtol: 1e-10,
      atol: 1e-12,
      resultHash: "classic-hash",
      timeSeries: analogPoints.map(({ programHash: _program, stateHash: _state, counts: _counts, diagnosticCodes: _codes, solver: _solver, ...point }) => point),
    },
    comparison: {
      maxOccupationAbsoluteError: 0.00001,
      maxCorrelationAbsoluteError: 0.00002,
      terminalStateFidelity: 0.99999999,
      maxAnalogNormError: 1e-15,
      maxClassicNormError: 1e-14,
    },
    interpretation: "effective model only",
  },
  quantum: {
    kind: "analog_ahs",
    experimentKind: "analog_ahs",
    mode: "analog",
    algorithm: "ahs_time_evolution",
    atomOrder: ["q0", "q1", "q2", "q3"],
    initialState: analogAnalysis.domain.initialState,
    pulseSchedule: analogAnalysis.domain.pulseSchedule,
    sampleTimes: [0, 0.6, 1.2],
    timeSeries: analogPoints,
    terminalCounts: [{ state: "1000", count: 20 }, { state: "0100", count: 12 }],
    pureAnalogEvidence: analogAnalysis.domain.pureAnalogEvidence,
    summary: {
      analogSites: 4,
      sampleCount: 3,
      shotsPerTime: 32,
      prefixProgramCount: 2,
      timeStepsAtTerminal: 120,
      digitalGateCount: 0,
      digitalResidualCount: 0,
      hybridBlockCount: 0,
    },
  },
  audit: {
    ...run.audit,
    caseId: "rydberg_dynamics",
    trajectoryHash: "trajectory-hash",
    classicReferenceHash: "classic-hash",
    initialStateHash: "initial-state-hash",
    pulseScheduleHash: "pulse-hash",
    rydbergLayoutHash: "layout-hash",
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

function renderAnalog(view: "business" | "comparison" | "quantum") {
  return render(
    <I18nProvider initialLanguage="zh">
      <MaterialsView analysis={analogAnalysis} run={analogRun} view={view} />
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

  it("renders completed Pure Analog dynamics without a Digital circuit", () => {
    renderAnalog("quantum");

    expect(screen.getByText("逐位点 Rydberg 占据")).toBeTruthy();
    expect(screen.getByText("终态位串 counts")).toBeTruthy();
    expect(screen.getByText("3 TIME POINTS")).toBeTruthy();
    expect(screen.queryByText("数字量子线路")).toBeNull();
    expect(screen.queryByText("QAOA 参数目标值")).toBeNull();
  });

  it("keeps the independent DOP853 reference in the comparison view", () => {
    renderAnalog("comparison");

    expect(screen.getByText("AHS RK4 与 DOP853 对照")).toBeTruthy();
    expect(screen.getByText("CLASSIC REFERENCE")).toBeTruthy();
    expect(screen.getByText("DOP853")).toBeTruthy();
    expect(screen.getByText("虚线：独立经典参考")).toBeTruthy();
  });

  it("shows Pure Analog completion and zero Digital residuals", () => {
    renderAnalog("business");

    expect(screen.getByText("AHS COMPLETED")).toBeTruthy();
    expect(screen.getByText("有效晶格量子淬火结果")).toBeTruthy();
    expect(screen.getByText("Digital residual")).toBeTruthy();
    expect(screen.getByText("COMPLETE")).toBeTruthy();
  });
});
