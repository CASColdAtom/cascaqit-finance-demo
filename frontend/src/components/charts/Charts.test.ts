import { describe, expect, it } from "vitest";
import { waveformDisplaySeries } from "./Charts";

describe("waveformDisplaySeries", () => {
  it("keeps all three physical channels visible when values overlap at zero", () => {
    const zero = [
      { time: 0, value: 0, raw: 0 },
      { time: 0.5, value: 0, raw: 0 },
    ];
    const series = waveformDisplaySeries({
      rabi: zero,
      detuning: zero,
      phase: zero,
    });

    expect(series.map((item) => item.name)).toEqual(["Rabi", "Detuning", "Phase"]);
    expect(series.map((item) => item.data[0][1])).toEqual([2, 0, -2]);
    expect(series.map((item) => item.lineStyle.type)).toEqual([
      "solid",
      "dashed",
      "dotted",
    ]);
    expect(series.every((item) => item.data.length === 2)).toBe(true);
  });
});
