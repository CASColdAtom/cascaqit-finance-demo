import { ChevronLeft, ChevronRight, CircuitBoard } from "lucide-react";
import { useMemo, useState } from "react";
import type { QuantumPayload } from "../types";
import { useI18n } from "../i18n";

const gateColors: Record<string, string> = {
  H: "#27d9e7",
  RX: "#4ade80",
  RZ: "#9a7bd8",
  CX: "#f0b94c",
  M: "#8a9b94",
};

function short(value: string) {
  return value.length > 18 ? `${value.slice(0, 14)}…` : value;
}

export function CircuitDiagram({ quantum }: { quantum: QuantumPayload }) {
  const { t, tx } = useI18n();
  const [view, setView] = useState<"gates" | "layers">("gates");
  const [start, setStart] = useState(0);
  const windowSize = 26;
  const gates = quantum.circuit.gates.slice(start, start + windowSize);
  const qubits = quantum.circuit.qubits;
  const height = Math.max(260, 92 + qubits.length * 38);
  const width = Math.max(760, 150 + gates.length * 42);
  const yByQubit = useMemo(
    () => new Map(qubits.map((qubit, index) => [qubit, 64 + index * 38])),
    [qubits],
  );
  const maximumStart = Math.max(0, quantum.circuit.gates.length - windowSize);

  return (
    <section className="circuit-workspace" aria-label={t("digitalCircuit")}>
      <div className="subsection-head">
        <div>
          <span className="section-kicker">
            <CircuitBoard size={14} aria-hidden="true" /> CIRCUIT IR
          </span>
          <h3>{view === "gates" ? t("parameterizedCircuit") : t("logicalLayers")}</h3>
        </div>
        <div className="circuit-tools">
          <div className="view-switch" role="group" aria-label={t("circuitRepresentation")}>
            <button type="button" aria-pressed={view === "gates"} onClick={() => setView("gates")}>
              {t("universalGates")}
            </button>
            <button type="button" aria-pressed={view === "layers"} onClick={() => setView("layers")}>
              {t("logicalLayer")}
            </button>
          </div>
          {view === "gates" && quantum.circuit.depth > windowSize ? (
            <div className="depth-nav">
              <button
                className="icon-button"
                type="button"
                onClick={() => setStart(Math.max(0, start - windowSize))}
                disabled={start === 0}
                aria-label={t("previousCircuit")}
              >
                <ChevronLeft size={16} aria-hidden="true" />
              </button>
              <span>
                {start + 1}–{Math.min(start + windowSize, quantum.circuit.depth)} / {quantum.circuit.depth}
              </span>
              <button
                className="icon-button"
                type="button"
                onClick={() => setStart(Math.min(maximumStart, start + windowSize))}
                disabled={start >= maximumStart}
                aria-label={t("nextCircuit")}
              >
                <ChevronRight size={16} aria-hidden="true" />
              </button>
            </div>
          ) : null}
        </div>
      </div>

      {view === "layers" ? (
        <div className="layer-rail" role="img" aria-label={`${quantum.mode} ${t("logicalLayer")}`}>
          {quantum.layers.map((layer, index) => (
            <div className={`layer-node layer-${layer.toLowerCase()}`} key={`${layer}-${index}`}>
              <small>{String(index + 1).padStart(2, "0")}</small>
              <strong>{layer}</strong>
              <span>{layer === "A" || layer === "AHS" ? "ANALOG" : layer === "M" || layer === "MEASURE" ? "READOUT" : "DIGITAL"}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="circuit-scroll">
          <svg
            className="circuit-svg"
            width={width}
            height={height}
            viewBox={`0 0 ${width} ${height}`}
            role="img"
            aria-labelledby="circuit-title circuit-desc"
          >
            <title id="circuit-title">{t("parameterizedCircuit")}</title>
            <desc id="circuit-desc">{t("circuitDescription")(qubits.length, gates.length)}</desc>
            {qubits.map((qubit) => {
              const y = yByQubit.get(qubit) ?? 0;
              return (
                <g key={qubit}>
                  <text x={8} y={y + 4} className="wire-label">
                    {short(tx(qubit))}
                  </text>
                  <line x1={132} x2={width - 18} y1={y} y2={y} className="wire-line" />
                </g>
              );
            })}
            {gates.map((gate, index) => {
              const x = 158 + index * 42;
              const involved = [...gate.controls, ...gate.targets];
              const ys = involved.map((qubit) => yByQubit.get(qubit) ?? 0);
              const color = gateColors[gate.name] ?? "#27d9e7";
              return (
                <g key={`${gate.depth}-${gate.name}-${index}`}>
                  {ys.length > 1 ? (
                    <line x1={x} x2={x} y1={Math.min(...ys)} y2={Math.max(...ys)} className="gate-link" />
                  ) : null}
                  {gate.controls.map((qubit) => (
                    <circle key={`c-${qubit}`} cx={x} cy={yByQubit.get(qubit)} r={4} fill={color} />
                  ))}
                  {gate.targets.map((qubit) => {
                    const y = yByQubit.get(qubit) ?? 0;
                    return (
                      <g key={`t-${qubit}`}>
                        <rect x={x - 14} y={y - 14} width={28} height={28} rx={4} fill="#101817" stroke={color} strokeWidth={1.5} />
                        <text x={x} y={y + 4} className="gate-label" fill={color}>
                          {gate.name}
                        </text>
                      </g>
                    );
                  })}
                </g>
              );
            })}
          </svg>
        </div>
      )}
    </section>
  );
}
