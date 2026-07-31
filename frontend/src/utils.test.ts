import { describe, expect, it } from "vitest";
import {
  estimateExecutionSeconds,
  executionSignature,
  scenarioControlValues,
  termShares,
} from "./utils";

describe("scenarioControlValues", () => {
  it("keeps editable controls and drops resolved read-only domain values", () => {
    expect(
      scenarioControlValues({
        controls: [
          {
            key: "minimum_loop",
            label: "最小环长",
            kind: "range",
            minimum: 3,
            maximum: 6,
            step: 1,
            options: [],
            unit: " nt",
          },
        ],
        values: { sequence: "GGACUUCGGUCC", minimum_loop: 3 },
      }),
    ).toEqual({ minimum_loop: 3 });
  });
});

describe("executionSignature", () => {
  it("is stable when control insertion order changes", () => {
    const base = {
      preset: "base",
      mode: "digital" as const,
      algorithm: "qaoa" as const,
      layer_policy: "fixed" as const,
      shots: 32,
      seed: 23,
      layers: 2,
      max_layers: 3,
      min_improvement: 0,
      search_strategy: "seeded_sample" as const,
      parameter_budget: 8,
    };
    expect(
      executionSignature("finance", "portfolio", {
        ...base,
        values: { risk_weight: 0.5, selected_count: 4 },
      }),
    ).toBe(
      executionSignature("finance", "portfolio", {
        ...base,
        values: { selected_count: 4, risk_weight: 0.5 },
      }),
    );
  });

  it("changes when the QAOA search configuration changes", () => {
    const request = {
      preset: "base",
      values: { risk_weight: 0.5 },
      mode: "digital" as const,
      algorithm: "qaoa" as const,
      layer_policy: "fixed" as const,
      shots: 32,
      seed: 23,
      layers: 1,
      max_layers: 3,
      min_improvement: 0,
      search_strategy: "preset" as const,
      parameter_budget: 2,
    };
    const base = executionSignature("finance", "portfolio", request);

    expect(
      executionSignature("finance", "portfolio", {
        ...request,
        layers: 2,
        search_strategy: "seeded_sample",
      }),
    ).not.toBe(base);
    expect(
      executionSignature("finance", "portfolio", {
        ...request,
        search_strategy: "grid",
        parameter_budget: 8,
      }),
    ).not.toBe(base);
    expect(executionSignature("biomedicine", "portfolio", request)).not.toBe(base);
  });

  it("invalidates cached runs when data or execution identity changes", () => {
    const request = {
      preset: "base",
      values: {},
      mode: "digital" as const,
      algorithm: "vqe" as const,
      layer_policy: "fixed" as const,
      shots: 64,
      seed: 23,
      layers: 1,
      max_layers: 1,
      min_improvement: 0,
      search_strategy: "continuous" as const,
      parameter_budget: 40,
    };
    const base = executionSignature("biomedicine", "electronic_structure", request, {
      datasetVersion: "1",
      manifestHash: "manifest-a",
      executionFamily: "pauli_vqe",
    });
    expect(executionSignature("biomedicine", "electronic_structure", request, {
      datasetVersion: "1",
      manifestHash: "manifest-b",
      executionFamily: "pauli_vqe",
    })).not.toBe(base);
    expect(executionSignature("biomedicine", "electronic_structure", request, {
      datasetVersion: "1",
      manifestHash: "manifest-a",
      executionFamily: "problem",
    })).not.toBe(base);
  });
});

describe("estimateExecutionSeconds", () => {
  it("scales the calibrated local baseline with requested work", () => {
    expect(estimateExecutionSeconds({
      shots: 64,
      seed: 23,
      layers: 1,
      searchStrategy: "continuous",
      parameterBudget: 40,
      optimizerStarts: 1,
      repeats: 1,
      estimatedSeconds: 2,
    }, {
      shots: 128,
      layers: 1,
      max_layers: 1,
      layer_policy: "fixed",
      parameter_budget: 80,
      optimizer_starts: 2,
      repeats: 3,
    })).toBe(48);
  });
});

describe("termShares", () => {
  it("normalizes Analog and Digital term counts to one track", () => {
    expect(termShares(3, 5)).toEqual({ analog: 37.5, digital: 62.5 });
    expect(termShares(0, 0)).toEqual({ analog: 0, digital: 0 });
  });
});
