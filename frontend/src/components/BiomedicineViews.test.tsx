// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type {
  ActiveCenterRunPayload,
  BiomedicineAnalysisPayload,
  DockingRunPayload,
  DockingSolutionPayload,
  ElectronicStructureRunPayload,
  PeptideRunPayload,
  ProteinDynamicsRunPayload,
  ProteinPathSolutionPayload,
  RNARunPayload,
  RNAStructureSolutionPayload,
} from "../types";
import { I18nProvider } from "../i18n";
import {
  BiomedicineMappingView,
  BiomedicineQuantumView,
  BiomedicineResultView,
  BiomedicineAuditView,
  BiomedicineComparisonView,
} from "./BiomedicineViews";
import { QuantumText } from "./QuantumText";

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
    exactFirstGapMeV: 0.0548,
    exactFirstGapSource: "classical_exact_diagonalization",
    absoluteErrorMeV: 0.0001,
    magnetization: [
      { siteId: "spin.m1", expectation: -0.25, standardError: 0.04 },
      { siteId: "spin.m2", expectation: 0.25, standardError: 0.04 },
    ],
    correlations: [
      { pathId: "exchange", leftSiteId: "spin.m1", rightSiteId: "spin.m2", operator: "XX", expectation: -0.97, standardError: 0.02 },
      { pathId: "exchange", leftSiteId: "spin.m1", rightSiteId: "spin.m2", operator: "YY", expectation: -0.96, standardError: 0.02 },
      { pathId: "exchange", leftSiteId: "spin.m1", rightSiteId: "spin.m2", operator: "ZZ", expectation: -1, standardError: 0 },
    ],
    sectorOccupancy: { "Mz=+1": 0, "Mz=+0": 1, "Mz=-1": 0 },
    declaredSector: "total_magnetization_z",
    interpretation: "有效自旋模型。",
  },
  comparison: {
    hamiltonianHash: "same-hash",
    vqeHamiltonianHash: "same-hash",
    exactFirstGapMeV: 0.0548,
    exactFirstGapSource: "classical_exact_diagonalization",
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

const peptideRun = {
  kind: "biomedicine",
  analysis: { ...analysis, caseId: "peptide_landscape" },
  domain: {
    kind: "peptide_landscape_result",
    quantumCandidate: { bitstring: "010", conformationId: "c2", energy: -1.5, contactCount: 2, coordinates: [], contacts: [], feasible: true },
    topObservedFeasible: [],
    observedFeasibleCount: 1,
    classicGroundConformations: [{ id: "c1", coordinates: [], contacts: [], energy: -2, contactCount: 3 }],
    fullLandscape: [
      { id: "c1", coordinates: [], contacts: [], energy: -2, contactCount: 3 },
      { id: "c2", coordinates: [], contacts: [], energy: -1.5, contactCount: 2 },
    ],
    energyGapFromGround: 0.5,
    interpretation: "有限构象库。",
  },
  quantum: {},
  audit: {},
} as unknown as PeptideRunPayload;

const rnaAnalysis: BiomedicineAnalysisPayload = {
  ...analysis,
  caseId: "rna_structure",
  decision: {
    recommendedMode: "digital",
    reason: "RNA pairing QUBO",
    modes: [{ mode: "digital", algorithm: "qaoa", status: "recommended", reason: "complete QUBO" }],
  },
  domain: {
    kind: "rna_structure",
    modelLevel: "短 RNA 候选二级结构集合",
    sequence: "GGACUUCGGUCC",
    minimumLoop: 3,
    pseudoknotPolicy: "forbidden",
    energyModel: {
      id: "canonical-pairing.educational.v1",
      units: "dimensionless educational score",
      unpairedPenalty: 0.15,
      stackingBonus: -0.4,
      hardPenalty: 8,
      interpretation: "Educational score only.",
    },
    candidatePairs: [],
    referenceStructure: rnaSolution("dataset_reference"),
    nodes: [],
    edges: [],
    limitations: ["Counts are not base-pair probabilities"],
  },
};

function rnaSolution(
  source: RNAStructureSolutionPayload["source"],
  dotBracket = "((((....))))",
): RNAStructureSolutionPayload {
  const pairs = [
    { id: "pair.01.12", left: 1, right: 12, pairType: "GC", score: -3, sourceRule: "reference" },
    { id: "pair.02.11", left: 2, right: 11, pairType: "GC", score: -3, sourceRule: "reference" },
  ];
  return {
    source,
    bitstring: "11000000",
    pairIds: pairs.map((pair) => pair.id),
    pairs,
    pairCount: pairs.length,
    unpairedCount: 8,
    dotBracket,
    energy: -6.2,
    feasible: true,
    referenceOverlap: 2,
    referenceOverlapRate: 0.5,
    checks: [],
  };
}

const rnaRun = {
  kind: "biomedicine",
  analysis: rnaAnalysis,
  domain: {
    kind: "rna_structure_result",
    quantumCandidate: { ...rnaSolution("quantum_observed"), count: 21 },
    topObservedFeasible: [{ ...rnaSolution("quantum_observed"), count: 21 }],
    observedFeasibleCount: 4,
    observedFeasibleRate: 0.72,
    lowEnergyCoverage: 0.55,
    structureDiversity: 3,
    classicExact: rnaSolution("classic_exact_enumeration"),
    classicDynamicProgramming: rnaSolution("classic_dynamic_programming"),
    referenceStructure: {
      ...rnaSolution("dataset_reference"),
      sourceId: "PDB:1ZIH",
      declaredDotBracket: "((((....))))",
    },
    interpretation: "QAOA counts 仅表示本次有限 shots 的观测频率，不是热力学概率或碱基配对概率。",
  },
  quantum: {
    kind: "problem_qaoa",
    mode: "digital",
    algorithm: "qaoa",
    summary: { qubits: 8, shots: 64, evaluations: 8, feasibleObserved: 4 },
    circuit: { qubits: ["q0"], gates: [{ depth: 0, name: "H", targets: ["q0"], controls: [], parameters: {} }], depth: 1 },
    counts: [{ state: "11000000", count: 21, rank: 1 }],
    parameterHistory: [{ index: 0, objective: -4.2, parameters: {}, selected: true }],
  },
  audit: {
    manifestHash: "rna-manifest",
    domainInputHash: "rna-input",
    problemHash: "rna-problem",
    hamiltonianHash: "rna-hamiltonian",
    analysisHash: "rna-analysis",
    ansatzHash: "rna-ansatz",
    compileHash: "rna-compile",
    backendHash: "rna-backend",
    configurationHash: "rna-config",
    executionHash: "rna-execution",
    resultHash: "rna-result",
    outcomeHash: "rna-outcome",
    reportHash: "rna-report",
  },
} as unknown as RNARunPayload;

const proteinStates = [
  { id: "state.open", label: "Open", basin: "open", x: 8, y: 50, structureSource: { kind: "public", identifier: "4AKE", method: "endpoint" } },
  { id: "state.hinge", label: "Hinge", basin: "intermediate", x: 35, y: 28, structureSource: { kind: "curated", identifier: "hinge-v1", method: "centroid" } },
  { id: "state.alt", label: "Alt", basin: "alternate", x: 35, y: 76, structureSource: { kind: "curated", identifier: "alt-v1", method: "centroid" } },
  { id: "state.preclosed", label: "Pre-closed", basin: "intermediate", x: 66, y: 45, structureSource: { kind: "curated", identifier: "pre-v1", method: "centroid" } },
  { id: "state.closed", label: "Closed", basin: "closed", x: 92, y: 50, structureSource: { kind: "public", identifier: "1AKE", method: "endpoint" } },
];

const proteinTransitions = [
  ["tr.open_hinge", "state.open", "state.hinge", 1.1],
  ["tr.open_alt", "state.open", "state.alt", 1.4],
  ["tr.hinge_pre", "state.hinge", "state.preclosed", 0.9],
  ["tr.alt_pre", "state.alt", "state.preclosed", 0.8],
  ["tr.pre_closed", "state.preclosed", "state.closed", 0.6],
].map(([id, from, to, cost]) => ({
  id: String(id),
  from: String(from),
  to: String(to),
  structuralCost: Number(cost) / 2,
  barrierProfiles: { baseline: Number(cost) / 2 },
  barrierProfile: "baseline",
  barrierComponent: Number(cost) / 2,
  cost: Number(cost),
  unit: "dimensionless_model_cost" as const,
  sourceMethod: "project-authored teaching score",
}));

const proteinPath: ProteinPathSolutionPayload = {
  source: "quantum_observed",
  bitstring: "100100100001",
  stateIds: ["state.open", "state.hinge", "state.preclosed", "state.closed"],
  transitionIds: ["tr.open_hinge", "tr.hinge_pre", "tr.pre_closed"],
  pathLength: 3,
  pathCost: 2.6,
  costUnit: "dimensionless_model_cost",
  modelObjective: 2.6,
  feasible: true,
  pathOverlap: 1,
  failureReasons: [],
  count: 18,
  checks: [],
};

const proteinAnalysis: BiomedicineAnalysisPayload = {
  ...rnaAnalysis,
  caseId: "protein_dynamics",
  dataset: {
    id: "protein.adenylate-kinase.conformation-network.teaching-v1",
    version: "1",
    manifestHash: "protein-manifest",
    sourceKind: "project_curated_teaching_network",
    license: "project-authored",
    allowedClaims: ["Finite state-network path search"],
    limitations: ["Path cost is not time, rate, or residence time"],
  },
  problem: { ...rnaAnalysis.problem, id: "protein-path-qubo", variables: Array.from({ length: 12 }, (_, index) => `q${index}`) },
  domain: {
    kind: "protein_dynamics",
    modelLevel: "版本化粗粒化构象状态网络",
    proteinLabel: "Adenylate kinase open/closed teaching network",
    startState: "state.open",
    targetState: "state.closed",
    maximumSteps: 3,
    barrierWeight: 1,
    weightProfile: "baseline",
    edgeWeight: { meaning: "structural + barrier", unit: "dimensionless_model_cost", sourceMethod: "teaching score" },
    stateNodes: proteinStates,
    transitions: proteinTransitions,
    activeNodes: proteinStates,
    activeEdges: proteinTransitions,
    classicShortestPath: { ...proteinPath, source: "classic_bounded_dijkstra", scope: "complete_network" },
    classicActivePath: { ...proteinPath, source: "classic_bounded_dijkstra", scope: "active_subgraph" },
    subproblemSelection: {
      ruleVersion: "connectivity-first-v1",
      selectionHash: "protein-selection",
      completeStateCount: 7,
      selectedStateCount: 5,
      completePathCount: 11,
      activePathCount: 2,
      activeNodeIds: proteinStates.map((item) => item.id),
      activeTransitionIds: proteinTransitions.map((item) => item.id),
      lockedPath: proteinPath.stateIds,
      connectivityPreserved: true,
      startPreserved: true,
      targetPreserved: true,
      coverageRate: 5 / 7,
      excluded: [{ id: "state.lid", reason: "outside active window" }],
    },
    limitations: ["Path cost is not time, rate, or residence time"],
  },
};

const proteinRun = {
  kind: "biomedicine",
  analysis: proteinAnalysis,
  domain: {
    kind: "protein_dynamics_result",
    quantumStatus: "observed_feasible",
    quantumCandidate: proteinPath,
    topObservedFeasible: [proteinPath],
    observedFeasibleCount: 1,
    observedFeasibleRate: 0.28125,
    classicShortestPath: { ...proteinPath, source: "classic_bounded_dijkstra", scope: "complete_network" },
    classicActivePath: { ...proteinPath, source: "classic_bounded_dijkstra", scope: "active_subgraph" },
    failureReasons: [{ id: "flow_conservation", shotCount: 10 }],
    interpretation: "pathCost 是无量纲离散模型代价，不表示真实时间、速率或驻留时间。",
  },
  quantum: rnaRun.quantum,
  audit: {
    ...rnaRun.audit,
    caseId: "protein_dynamics",
    conformationSetHash: "states-hash",
    transitionNetworkHash: "network-hash",
    selectionHash: "selection-hash",
    pathQuboHash: "path-qubo-hash",
  },
} as unknown as ProteinDynamicsRunPayload;

afterEach(cleanup);

describe("Biomedicine terminology", () => {
  it("provides Chinese explanations for the published quantum abbreviations", () => {
    render(<QuantumText text="HF VQE QWC QAOA QUBO D-A-D QAA AHS" />);
    for (const title of [
      "Hartree-Fock 平均场参考",
      "变分量子本征求解器",
      "逐量子比特可对易测量分组",
      "量子近似优化算法",
      "二次无约束二元优化",
      "数字-模拟-数字混合执行序列",
      "量子绝热算法",
      "模拟 Hamiltonian 仿真",
    ]) {
      expect(screen.getByTitle(title)).toBeTruthy();
    }
  });
});

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
    expect(screen.getByRole("heading", { name: "QUBO 贡献账本" })).toBeTruthy();
    expect(screen.getAllByTitle("二次无约束二元优化").length).toBeGreaterThan(0);
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
    expect(screen.getByText("exchange / XX")).toBeTruthy();
    expect(screen.getByText(/classic gap 0\.0548 meV/)).toBeTruthy();
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
    expect(screen.getByTitle("变分量子本征求解器")).toBeTruthy();
    expect(screen.getByTitle("逐量子比特可对易测量分组")).toBeTruthy();
  });
});

describe("Biomedicine comparison view", () => {
  it("keeps the four scenario comparison contracts explicit", () => {
    const { rerender } = render(
      <BiomedicineComparisonView analysis={electronicAnalysis} run={electronicRun} />,
    );
    expect(screen.getByText("小分子基态能量对照")).toBeTruthy();
    expect(screen.getByText("读出噪声 QWC")).toBeTruthy();
    expect(screen.getByTitle("变分量子本征求解器")).toBeTruthy();

    rerender(<BiomedicineComparisonView analysis={analysis} run={activeCenterRun} />);
    expect(screen.getByText("有效自旋 Hamiltonian 对照")).toBeTruthy();
    expect(screen.getByText("HASH MATCH")).toBeTruthy();

    rerender(<BiomedicineComparisonView analysis={analysis} run={run} />);
    expect(screen.getByText("构象匹配三方对照")).toBeTruthy();
    expect(screen.getByText("共晶派生参考")).toBeTruthy();

    rerender(<BiomedicineComparisonView analysis={analysis} run={peptideRun} />);
    expect(screen.getByText("小肽候选与完整能景对照")).toBeTruthy();
    expect(screen.getByText("完整能景位置")).toBeTruthy();
    expect(screen.getByTitle("量子近似优化算法")).toBeTruthy();

    rerender(<BiomedicineComparisonView analysis={rnaAnalysis} run={rnaRun} />);
    expect(screen.getByText("RNA 二级结构四方对照")).toBeTruthy();
    expect(screen.getByText("经典动态规划")).toBeTruthy();
    expect(screen.getByText("PDB:1ZIH")).toBeTruthy();
  });

  it("does not fabricate a comparison before execution", () => {
    render(<BiomedicineComparisonView analysis={analysis} run={null} />);
    expect(screen.getByText("执行后生成独立对照")).toBeTruthy();
    expect(screen.getByText(/不预填运行结论/)).toBeTruthy();
  });
});

describe("Biomedicine RNA views", () => {
  it("renders the pairing arc, separated references, and Top-K observations", () => {
    render(<BiomedicineResultView analysis={rnaAnalysis} run={rnaRun} />);
    expect(screen.getByRole("img", { name: "量子观测 RNA 二级结构" })).toBeTruthy();
    expect(screen.getByText("量子观测候选")).toBeTruthy();
    expect(screen.getByText("经典精确枚举")).toBeTruthy();
    expect(screen.getByText("数据集参考结构")).toBeTruthy();
    expect(screen.getByText("已观测低评分结构集合")).toBeTruthy();
    expect(screen.getByText(/不是热力学概率或碱基配对概率/)).toBeTruthy();
  });

  it("labels QAOA counts as observation frequency and exposes the RNA audit", () => {
    const { rerender } = render(
      <I18nProvider>
        <BiomedicineQuantumView run={rnaRun} mode="digital" />
      </I18nProvider>,
    );
    expect(screen.getByText("有限 shots 观测分布")).toBeTruthy();
    expect(screen.getByText(/Counts 不是热力学概率/)).toBeTruthy();

    rerender(<BiomedicineAuditView analysis={rnaAnalysis} run={rnaRun} />);
    expect(screen.getByText("Hamiltonian")).toBeTruthy();
    expect(screen.getByText("rna-report")).toBeTruthy();
  });
});

describe("Biomedicine protein-path views", () => {
  it("renders the complete network, active subgraph, and observed path", () => {
    const { rerender } = render(
      <BiomedicineResultView analysis={proteinAnalysis} run={null} />,
    );
    expect(screen.getByRole("img", { name: "完整蛋白构象状态网络与量子活动子图" })).toBeTruthy();
    expect(screen.getByText("COMPLETE PATHS")).toBeTruthy();
    expect(screen.getByText("ACTIVE PATHS")).toBeTruthy();

    rerender(<BiomedicineResultView analysis={proteinAnalysis} run={proteinRun} />);
    expect(screen.getByRole("img", { name: "量子观测蛋白构象转变路径" })).toBeTruthy();
    expect(screen.getByText("量子观测候选")).toBeTruthy();
    expect(screen.getByText("经典完整网络基线")).toBeTruthy();
    expect(screen.getByText(/不表示真实时间、速率或驻留时间/)).toBeTruthy();
  });

  it("keeps a missing quantum path empty instead of displaying the classic path", () => {
    const noObservation = {
      ...proteinRun,
      domain: {
        ...proteinRun.domain,
        quantumStatus: "quantum_not_observed",
        quantumCandidate: null,
        topObservedFeasible: [],
        observedFeasibleCount: 0,
        observedFeasibleRate: 0,
      },
    } as ProteinDynamicsRunPayload;
    render(<BiomedicineResultView analysis={proteinAnalysis} run={noObservation} />);
    expect(screen.getAllByText("NO FALLBACK").length).toBeGreaterThan(0);
    expect(screen.getByText("未观测到可行路径")).toBeTruthy();
    expect(screen.getByText("经典完整网络基线")).toBeTruthy();
  });

  it("labels path counts and classic comparisons without kinetic claims", () => {
    const { rerender } = render(
      <I18nProvider>
        <BiomedicineQuantumView run={proteinRun} mode="digital" />
      </I18nProvider>,
    );
    expect(screen.getByText("有限 shots 路径编码分布")).toBeTruthy();
    expect(screen.getByText(/Counts 不是转移概率、速率或驻留时间/)).toBeTruthy();

    rerender(
      <BiomedicineComparisonView analysis={proteinAnalysis} run={proteinRun} />,
    );
    expect(screen.getByText("构象转变路径三方对照")).toBeTruthy();
    expect(screen.getByText("经典完整网络")).toBeTruthy();
    expect(screen.getByText("经典活动子图")).toBeTruthy();
  });
});
