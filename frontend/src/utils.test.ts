import { describe, expect, it } from "vitest";
import { executionSignature, termShares } from "./utils";

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
      executionSignature("portfolio", {
        ...base,
        values: { risk_weight: 0.5, selected_count: 4 },
      }),
    ).toBe(
      executionSignature("portfolio", {
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
    const base = executionSignature("portfolio", request);

    expect(
      executionSignature("portfolio", {
        ...request,
        layers: 2,
        search_strategy: "seeded_sample",
      }),
    ).not.toBe(base);
    expect(
      executionSignature("portfolio", {
        ...request,
        search_strategy: "grid",
        parameter_budget: 8,
      }),
    ).not.toBe(base);
  });
});

describe("termShares", () => {
  it("normalizes Analog and Digital term counts to one track", () => {
    expect(termShares(3, 5)).toEqual({ analog: 37.5, digital: 62.5 });
    expect(termShares(0, 0)).toEqual({ analog: 0, digital: 0 });
  });
});
