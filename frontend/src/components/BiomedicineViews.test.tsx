// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type {
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
