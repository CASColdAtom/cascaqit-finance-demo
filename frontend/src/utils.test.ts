import { describe, expect, it } from "vitest";
import { executionSignature, termShares } from "./utils";

describe("executionSignature", () => {
  it("is stable when control insertion order changes", () => {
    const base = {
      preset: "base",
      mode: "digital" as const,
      shots: 32,
      seed: 23,
      parameter_points: 2,
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
});

describe("termShares", () => {
  it("normalizes Analog and Digital term counts to one track", () => {
    expect(termShares(3, 5)).toEqual({ analog: 37.5, digital: 62.5 });
    expect(termShares(0, 0)).toEqual({ analog: 0, digital: 0 });
  });
});
