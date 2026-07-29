// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type {
  ActiveCenterRunPayload,
  BiomedicineAnalysisPayload,
  DockingRunPayload,
  DockingSolutionPayload,
  ElectronicStructureRunPayload,
} from "../types";
import { I18nProvider } from "../i18n";
import {
  BiomedicineMappingView,
  BiomedicineQuantumView,
  BiomedicineResultView,
  BiomedicineAuditView,
} from "./BiomedicineViews";

const analysis = {
  kind: "biomedicine",
  caseId: "docking_match",
  executionFamily: "problem",
  implementationStatus: "available",
  analysisHash: "analysis-hash",
  dataset: {
    id: "docking.1hsg.indinavir.discrete-match",
    version: "1",
    manifestHash: "manifest-hash",
    sourceKind: "RCSB_PDB_derived",
    license: "CC0-1.0",
    allowedClaims: ["Discrete matching demonstration"],
    limitations: ["Local simulation only"],
  },
  problem: {
    id: "biomedicine.docking.1hsg.reference_pose",
    type: "qubo",
    hash: "problem-hash",
    variables: ["match.c0", "select.crystal", "slack.coverage"],
    terms: [{ id: "linear.match.c0", operator: "linear", targets: ["match.c0"], coefficient: -1 }],
    termGroups: [{ group_id: "conflicts", label: "冲突", kind: "pairwise_conflict", variables: [], pairs: [["match.c0", "match.c1"]] }],
    coefficientLedger: {
      balanced: true,
      contributionCount: 1,
      canonicalTermCount: 1,
      rows: [{ contributionId: "reward:c0", groupId: "objective", sourceRule: "match", role: "objective", termKind: "linear", targets: ["match.c0"], coefficient: -1, canonicalTermId: "linear.match.c0" }],
    },
  },
  resource: { logical_variables: 3 },
  decision: {
    recommendedMode: "hybrid",
    reason: "Hybrid split",
    modes: [{ mode: "hybrid", algorithm: "qaoa", status: "recommended", reason: "verified", analogTermCount: 2, digitalTermCount: 4, geometryStatus: "verified" }],
  },
  domain: {
    kind: "docking_match",
    modelLevel: "离散匹配",
    minimumCoverage: 2,
    nodes: [],
    edges: [],
    limitations: ["No binding affinity claim"],
  },
} satisfies BiomedicineAnalysisPayload;

function solution(
  source: DockingSolutionPayload["source"],
  feasible = true,
): DockingSolutionPayload {
  return {
    source,
    bitstring: "101",
    poseId: "pose.crystal",
    selectedMatchIds: ["match.c0", "match.c2"],
    modelObjective: -2.076,
    domainScore: 2.076,
    coverage: 2,
    referenceOverlap: 2,
    feasible,
    checks: [{ id: "single_pose", label: "单一构象", passed: feasible, actual: 1, expected: 1 }],
  };
}

const run = {
  kind: "biomedicine",
  analysis,
  domain: {
    kind: "docking_match_result",
    quantumCandidate: solution("quantum_observed"),
    classicOptimum: solution("complete_enumeration"),
    coCrystalReference: solution("co_crystal_reference"),
    topObservedFeasible: [solution("quantum_observed")],
    observedFeasibleCount: 1,
    interpretation: "无量纲离散匹配评分。",
  },
  quantum: {},
  audit: {},
} as unknown as DockingRunPayload;

const activeCenterRun = {
  kind: "biomedicine",
  analysis,
  domain: {
    kind: "active_center_result",
    vqeExactEnergyMeV: -0.921,
    sampledEnergyMeV: -0.919,
    sampledStandardErrorMeV: 0.01,
    exactGroundEnergyMeV: -0.9211,
    absoluteErrorMeV: 0.0001,
    magnetization: [
      { siteId: "spin.m1", expectation: -0.25, standardError: 0.04 },
      { siteId: "spin.m2", expectation: 0.25, standardError: 0.04 },
    ],
    correlations: [
      { operator: "XX", expectation: -0.97, standardError: 0.02 },
      { operator: "YY", expectation: -0.96, standardError: 0.02 },
      { operator: "ZZ", expectation: -1, standardError: 0 },
    ],
    sectorOccupancy: { "Mz=+1": 0, "Mz=+0": 1, "Mz=-1": 0 },
    declaredSector: "total_magnetization_z",
    interpretation: "有效自旋模型。",
  },
  comparison: {
    hamiltonianHash: "same-hash",
    vqeHamiltonianHash: "same-hash",
  },
  audit: { hamiltonianHash: "same-hash" },
} as unknown as ActiveCenterRunPayload;

const electronicAnalysis = {
  ...analysis,
  caseId: "electronic_structure",
  executionFamily: "pauli_vqe",
  dataset: {
    id: "electronic.h2o.sto3g.equilibrium.active-2e-3o",
    version: "1",
    manifestHash: "manifest-hash",
    sourceKind: "project_generated_ab_initio_fixture",
    license: "project_generated",
    limitations: ["Fixed active-space teaching fixture"],
  },
  problem: {
    id: "electronic.h2o.sto3g.equilibrium.active-2e-3o",
    type: "pauli_hamiltonian",
    hash: "hamiltonian-hash",
    variables: ["q0", "q1", "q2", "q3"],
    terms: [{ id: "pauli.z0", operator: "Z(q0)", targets: ["q0"], coefficient: 1 }],
  },
  resource: { logicalQubits: 4 },
  decision: {
    recommendedMode: "digital",
    reason: "Digital VQE",
    modes: [{ mode: "digital", algorithm: "vqe", status: "recommended", reason: "Pauli" }],
  },
  domain: {
    kind: "electronic_structure",
    molecule: "H2O",
    atoms: [],
    bonds: [],
    limitations: ["Fixed active-space teaching fixture"],
    bondScanReference: [
      { dataset: "h2-0500", bondLengthAngstrom: 0.5, exactGroundEnergy: -1.05, hartreeFockEnergy: -1.04, selected: false },
      { dataset: "h2-0735", bondLengthAngstrom: 0.735, exactGroundEnergy: -1.13, hartreeFockEnergy: -1.11, selected: true },
      { dataset: "h2-1500", bondLengthAngstrom: 1.5, exactGroundEnergy: -0.99, hartreeFockEnergy: -0.91, selected: false },
    ],
  },
} satisfies BiomedicineAnalysisPayload;

const electronicRun = {
  kind: "biomedicine",
  analysis: electronicAnalysis,
  domain: {
    kind: "ground_state_energy",
    molecule: "H2O",
    datasetKey: "h2o_sto3g_equilibrium",
    exactOptimizedEnergy: -74.964,
    sampledConfirmationEnergy: -74.961,
    sampledStandardError: 0.002,
    noisySampledConfirmationEnergy: -74.75,
    noisySampledStandardError: 0.01,
    referenceEnergy: -74.965,
    absoluteErrorHartree: 0.001,
    relativeError: 0.000013,
    chemicalAccuracyThresholdHartree: null,
    withinChemicalAccuracy: null,
    accuracyClaim: "error_report_only",
    estimatorNote: "Same optimized point, separate QWC evidence.",
  },
  comparison: {
    referenceMethod: "exact diagonalization",
    hartreeFockEnergy: -74.963,
    exactGroundEnergy: -74.965,
    vqeExactEnergy: -74.964,
    vqeSampledEnergy: -74.961,
    vqeNoisySampledEnergy: -74.75,
  },
  quantum: {
    summary: { qubits: 4, pauliTerms: 27, measurementGroups: 7, shotsPerGroup: 32, totalMeasurementShots: 224, evaluations: 40, noiseModel: "readout_demo" },
    counts: { "1111": 20, "1101": 12 },
    circuit: { qubits: ["q0", "q1", "q2", "q3"], gates: [], depth: 0 },
    parameterHistory: [{ index: 0, objective: -74.964, parameters: {}, selected: true }],
    measurement: {
      planHash: "plan-hash",
      groups: [{ index: 0, basis: { q0: "Z" }, shots: 32, counts: { "1111": 32 } }],
      noisyGroups: [{ index: 0, basis: { q0: "Z" }, shots: 32, counts: { "1111": 26, "0111": 6 } }],
      noiseModelHash: "noise-hash",
    },
  },
  audit: {},
} as unknown as ElectronicStructureRunPayload;

afterEach(cleanup);

describe("Biomedicine docking views", () => {
  it("keeps quantum, classic, and co-crystal results visibly separate", () => {
    render(<BiomedicineResultView analysis={analysis} run={run} />);
    expect(screen.getByText("量子观测候选")).toBeTruthy();
    expect(screen.getByText("经典枚举最优")).toBeTruthy();
    expect(screen.getByText("共晶派生参考")).toBeTruthy();
    expect(screen.getByText("QUANTUM FEASIBLE")).toBeTruthy();
    expect(screen.getByText("SUPPORTED INTERPRETATION")).toBeTruthy();
    expect(screen.getByText("Discrete matching demonstration")).toBeTruthy();
    expect(screen.queryByText("VQE EXACT OBJECTIVE")).toBeNull();
  });

  it("shows the QUBO ledger and verified Hybrid gate", () => {
    render(<BiomedicineMappingView analysis={analysis} />);
    expect(screen.getByText("QUBO 贡献账本")).toBeTruthy();
    expect(screen.getByText("BALANCED")).toBeTruthy();
    expect(screen.getByText(/2 A \/ 4 D/)).toBeTruthy();
    expect(screen.getByText(/verified/)).toBeTruthy();
  });

  it("shows the reproducible audit hash chain", () => {
    const auditedRun = {
      ...run,
      audit: {
        manifestHash: "manifest-hash",
        domainInputHash: "domain-input-hash",
        problemHash: "problem-hash",
        analysisHash: "analysis-hash",
        compileHash: "compile-hash",
        backendHash: "backend-hash",
        configurationHash: "configuration-hash",
        executionHash: "execution-hash",
        resultHash: "result-hash",
        outcomeHash: "outcome-hash",
        resultPresentationHash: "presentation-hash",
        reportHash: "report-hash",
      },
    } as DockingRunPayload;
    render(<BiomedicineAuditView analysis={analysis} run={auditedRun} />);
    expect(screen.getByText("Domain Input")).toBeTruthy();
    expect(screen.getByText("Backend")).toBeTruthy();
    expect(screen.getByText("Configuration")).toBeTruthy();
    expect(screen.getByText("Outcome")).toBeTruthy();
    expect(screen.getByText("Report")).toBeTruthy();
  });
});

describe("Biomedicine active-center views", () => {
  it("shows backend observables, sector occupancy, and Hamiltonian identity", () => {
    render(<BiomedicineResultView analysis={analysis} run={activeCenterRun} />);
    expect(screen.getByText("局域磁化与两点自旋关联")).toBeTruthy();
    expect(screen.getByText("总磁化扇区占据")).toBeTruthy();
    expect(screen.getByText("MATCH")).toBeTruthy();
    expect(screen.getByText("CORRELATION / XX")).toBeTruthy();
  });
});

describe("Biomedicine electronic-structure views", () => {
  it("reports LiH/H2O error without making an uncalibrated accuracy claim", () => {
    render(<BiomedicineResultView analysis={electronicAnalysis} run={electronicRun} />);
    expect(screen.getByText("ERROR REPORTED")).toBeTruthy();
    expect(screen.getByText("READOUT-NOISE QWC")).toBeTruthy();
    expect(screen.getByText("固定几何能量趋势")).toBeTruthy();
    expect(screen.queryByText("≤ 1.6 mHa")).toBeNull();
  });

  it("shows ideal and noisy QWC group executions separately", () => {
    render(
      <I18nProvider>
        <BiomedicineQuantumView run={electronicRun} mode="digital" />
      </I18nProvider>,
    );
    expect(screen.getByText("理想与带噪测量组")).toBeTruthy();
    expect(screen.getByText("READOUT NOISE")).toBeTruthy();
    expect(screen.getByText("IDEAL")).toBeTruthy();
  });
});
