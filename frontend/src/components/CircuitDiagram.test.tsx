// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { QuantumPayload } from "../types";
import { I18nProvider } from "../i18n";
import { CircuitDiagram } from "./CircuitDiagram";

afterEach(cleanup);

function payload(qubitCount: number): QuantumPayload {
  const qubits = Array.from({ length: qubitCount }, (_, index) => `q${index}`);
  return {
    mode: "digital",
    algorithm: "qaoa",
    topology: null,
    layerCount: 1,
    searchStrategy: "preset",
    evaluationCount: 0,
    selectedEvaluationIndex: 0,
    blocks: [],
    layers: ["U1", "U2", "RX1", "M"],
    circuit: {
      qubits,
      depth: 1,
      gates: [
        {
          depth: 0,
          name: "H",
          targets: [qubits[0]],
          controls: [],
          parameters: {},
        },
      ],
    },
    atoms: [],
    waveforms: { rabi: [], detuning: [], phase: [] },
    counts: [],
    parameterHistory: [],
    termMapping: [],
    summary: { analogTerms: 0, digitalTerms: 1, qubits: qubitCount, shots: 16 },
  };
}

describe("CircuitDiagram", () => {
  it("shows only the QAOA logical layer representation", () => {
    render(
      <I18nProvider initialLanguage="zh">
        <CircuitDiagram quantum={payload(4)} />
      </I18nProvider>,
    );

    expect(screen.getByRole("img", { name: "digital QAOA 逻辑层" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "通用门" })).toBeNull();
    expect(document.querySelector(".circuit-svg")).toBeNull();
    expect(screen.getByText("U1")).toBeTruthy();
    expect(screen.getByText("RX1")).toBeTruthy();
  });
});
