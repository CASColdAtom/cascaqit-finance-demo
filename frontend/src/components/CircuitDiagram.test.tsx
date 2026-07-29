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

    expect(screen.getByRole("img", { name: "digital QAOA 变分逻辑层" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "通用门" })).toBeNull();
    expect(document.querySelector(".circuit-svg")).toBeNull();
    expect(screen.getByText("U1")).toBeTruthy();
    expect(screen.getByText("RX1")).toBeTruthy();
  });

  it("shows the actual VQE ansatz instead of QAOA layers", () => {
    const quantum = payload(4);
    quantum.algorithm = "vqe";
    quantum.layers = ["|0>", "RY", "CX", "M"];
    quantum.ansatz = {
      kind: "hardware_efficient",
      layers: 1,
      parameterNames: ["theta_0", "theta_1", "theta_2", "theta_3"],
      parameterCount: 4,
      circuitHash: "circuit-hash",
      ansatzHash: "ansatz-hash",
      definition: {
        definition_kind: "hardware_efficient",
        entanglement: "linear",
        rotation_axes: ["ry"],
        schema_version: "1.0",
      },
    };

    render(
      <I18nProvider initialLanguage="zh">
        <CircuitDiagram quantum={quantum} />
      </I18nProvider>,
    );

    expect(screen.getByRole("img", { name: "digital VQE 变分逻辑层" })).toBeTruthy();
    expect(screen.getByText("|0>")).toBeTruthy();
    expect(screen.getByText("RY")).toBeTruthy();
    expect(screen.getByText("CX")).toBeTruthy();
    expect(screen.getByText(/4 参数/)).toBeTruthy();
    expect(screen.queryByText("U1")).toBeNull();
  });
});
