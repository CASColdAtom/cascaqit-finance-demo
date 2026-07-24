// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
  it("grows with the number of logical qubits", () => {
    const { rerender } = render(
      <I18nProvider initialLanguage="zh">
        <CircuitDiagram quantum={payload(2)} />
      </I18nProvider>,
    );
    const small = screen.getByRole("img", { name: /参数化通用门线路/ });
    expect(small.getAttribute("height")).toBe("260");

    rerender(
      <I18nProvider initialLanguage="zh">
        <CircuitDiagram quantum={payload(12)} />
      </I18nProvider>,
    );

    expect(
      screen.getByRole("img", { name: /参数化通用门线路/ }).getAttribute("height"),
    ).toBe("548");
  });

  it("switches to the QAOA logical layer representation", () => {
    render(
      <I18nProvider initialLanguage="zh">
        <CircuitDiagram quantum={payload(4)} />
      </I18nProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "逻辑层" }));

    expect(screen.getByRole("img", { name: "digital 逻辑层" })).toBeTruthy();
    expect(screen.getByText("U1")).toBeTruthy();
    expect(screen.getByText("RX1")).toBeTruthy();
  });
});
