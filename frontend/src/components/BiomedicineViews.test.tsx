// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type {
  ActiveCenterRunPayload,
  BiomedicineAnalysisPayload,
  DockingRunPayload,
  DockingSolutionPayload,
} from "../types";
import { BiomedicineMappingView, BiomedicineResultView } from "./BiomedicineViews";

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

afterEach(cleanup);

describe("Biomedicine docking views", () => {
  it("keeps quantum, classic, and co-crystal results visibly separate", () => {
    render(<BiomedicineResultView analysis={analysis} run={run} />);
    expect(screen.getByText("量子观测候选")).toBeTruthy();
    expect(screen.getByText("经典枚举最优")).toBeTruthy();
    expect(screen.getByText("共晶派生参考")).toBeTruthy();
    expect(screen.getByText("QUANTUM FEASIBLE")).toBeTruthy();
    expect(screen.queryByText("VQE EXACT OBJECTIVE")).toBeNull();
  });

  it("shows the QUBO ledger and verified Hybrid gate", () => {
    render(<BiomedicineMappingView analysis={analysis} />);
    expect(screen.getByText("QUBO 贡献账本")).toBeTruthy();
    expect(screen.getByText("BALANCED")).toBeTruthy();
    expect(screen.getByText(/2 A \/ 4 D/)).toBeTruthy();
    expect(screen.getByText(/verified/)).toBeTruthy();
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
