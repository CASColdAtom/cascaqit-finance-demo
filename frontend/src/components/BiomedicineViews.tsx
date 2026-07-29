import {
  Activity,
  Atom,
  Beaker,
  Binary,
  CheckCircle2,
  CircleAlert,
  FileJson,
  GitBranch,
  Radio,
} from "lucide-react";
import type {
  BiomedicineAnalysisPayload,
  BiomedicineRunPayload,
  BiomedicineStructureEdge,
  BiomedicineStructureNode,
  Mode,
} from "../types";
import { compactId, MODE_LABELS } from "../utils";
import { useI18n } from "../i18n";
import { CountsChart, ParameterChart } from "./charts/Charts";

function StructureDiagram({ analysis }: { analysis: BiomedicineAnalysisPayload }) {
  const domain = analysis.domain;
  const nodes = domain.atoms ?? domain.nodes ?? [];
  const edges = domain.bonds ?? domain.edges ?? [];
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  return (
    <div className="biomed-structure-canvas" role="img" aria-label={domain.modelLevel ?? domain.kind}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
        {edges.map((edge, index) => {
          const source = nodeMap.get(edge.source);
          const target = nodeMap.get(edge.target);
          if (!source || !target) return null;
          return (
            <line
              className={`structure-edge edge-${edge.kind ?? "bond"}`}
              key={`${edge.source}-${edge.target}-${index}`}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
            />
          );
        })}
        {nodes.map((node) => (
          <g className={`structure-node node-${node.role ?? node.element ?? "default"}`} key={node.id}>
            <circle cx={node.x} cy={node.y} r={nodeRadius(node)} />
            <text x={node.x} y={node.y + 1.7} textAnchor="middle">
              {node.element ?? node.label ?? node.id}
            </text>
          </g>
        ))}
      </svg>
      <div className="structure-legend">
        {[...new Set(nodes.map((node) => node.group ?? node.element).filter(Boolean))].map(
          (group) => (
            <span key={group}>
              <i /> {group}
            </span>
          ),
        )}
      </div>
    </div>
  );
}

function nodeRadius(node: BiomedicineStructureNode) {
  if (node.role === "spin_site") return 8;
  if (node.element === "H") return 7;
  return 6;
}

function EdgeTable({ edges }: { edges: BiomedicineStructureEdge[] }) {
  if (!edges.length) return null;
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr><th>Source</th><th>Target</th><th>Relation</th><th>Value</th></tr>
        </thead>
        <tbody>
          {edges.map((edge, index) => (
            <tr key={`${edge.source}-${edge.target}-${index}`}>
              <td className="mono">{edge.source}</td>
              <td className="mono">{edge.target}</td>
              <td>{edge.kind ?? "bond"}</td>
              <td>{edge.lengthAngstrom ?? edge.score ?? edge.order ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BoundaryList({ values }: { values: string[] }) {
  return (
    <div className="boundary-list">
      {values.map((value) => (
        <span key={value}><CircleAlert size={14} aria-hidden="true" />{value}</span>
      ))}
    </div>
  );
}

export function BiomedicineResultView({
  analysis,
  run,
}: {
  analysis: BiomedicineAnalysisPayload;
  run: BiomedicineRunPayload | null;
}) {
  if (!run) {
    return (
      <div className="view-stack biomed-view">
        <section className="data-section biomed-overview">
          <div className="subsection-head">
            <div><span className="section-kicker"><Beaker size={14} /> DOMAIN MODEL</span><h3>{analysis.domain.modelLevel ?? analysis.domain.geometryLabel ?? analysis.domain.kind}</h3></div>
            <span className={`data-chip status-${analysis.implementationStatus}`}>{analysis.implementationStatus.toUpperCase()}</span>
          </div>
          <StructureDiagram analysis={analysis} />
        </section>
        <BoundaryList values={analysis.dataset.limitations} />
      </div>
    );
  }
  const result = run.domain;
  return (
    <div className="view-stack biomed-view">
      <div className="biomed-metric-band">
        <div><small>VQE EXACT OBJECTIVE</small><strong>{result.exactOptimizedEnergy.toFixed(6)}</strong><span>Hartree</span></div>
        <div><small>QWC CONFIRMATION</small><strong>{result.sampledConfirmationEnergy.toFixed(6)}</strong><span>± {result.sampledStandardError.toFixed(4)}</span></div>
        <div><small>EXACT REFERENCE</small><strong>{result.referenceEnergy.toFixed(6)}</strong><span>Hartree</span></div>
        <div data-pass={result.withinChemicalAccuracy}><small>ABSOLUTE ERROR</small><strong>{(result.absoluteErrorHartree * 1000).toFixed(3)}</strong><span>mHa</span></div>
      </div>
      <section className="data-section energy-comparison">
        <div className="subsection-head">
          <div><span className="section-kicker"><Activity size={14} /> ENERGY EVIDENCE</span><h3>基态能量对照</h3></div>
          <span className={`data-chip ${result.withinChemicalAccuracy ? "source-quantum" : "status-preview"}`}>
            {result.withinChemicalAccuracy ? <CheckCircle2 size={13} /> : <CircleAlert size={13} />}
            {result.withinChemicalAccuracy ? "≤ 1.6 mHa" : "> 1.6 mHa"}
          </span>
        </div>
        <div className="energy-axis">
          {[
            ["Hartree-Fock", run.comparison.hartreeFockEnergy],
            ["VQE", run.comparison.vqeExactEnergy],
            ["Exact", run.comparison.exactGroundEnergy],
          ].map(([label, value]) => (
            <div key={label as string} style={{ "--energy-position": `${energyPosition(value as number, run)}%` } as React.CSSProperties}>
              <i /><strong>{label}</strong><span>{(value as number).toFixed(6)} Ha</span>
            </div>
          ))}
        </div>
        <p className="subsection-note">{result.estimatorNote}</p>
      </section>
      <BoundaryList values={analysis.dataset.limitations} />
    </div>
  );
}

function energyPosition(value: number, run: BiomedicineRunPayload) {
  const values = [run.comparison.hartreeFockEnergy, run.comparison.exactGroundEnergy];
  const minimum = Math.min(...values) - 0.005;
  const maximum = Math.max(...values) + 0.005;
  return ((value - minimum) / (maximum - minimum)) * 100;
}

export function BiomedicineStructureView({ analysis }: { analysis: BiomedicineAnalysisPayload }) {
  const edges = analysis.domain.bonds ?? analysis.domain.edges ?? [];
  return (
    <div className="view-stack biomed-view">
      <section className="data-section">
        <div className="subsection-head">
          <div><span className="section-kicker"><Atom size={14} /> DOMAIN STRUCTURE</span><h3>{analysis.domain.molecule ?? analysis.domain.sequence ?? analysis.domain.modelLevel ?? "场景结构"}</h3></div>
          <span className="data-chip">{analysis.problem.variables.length} OBJECTS</span>
        </div>
        <StructureDiagram analysis={analysis} />
      </section>
      <section className="data-section">
        <div className="subsection-head"><div><span className="section-kicker">RELATIONSHIP EVIDENCE</span><h3>结构关系</h3></div></div>
        <EdgeTable edges={edges} />
      </section>
      <BoundaryList values={analysis.domain.limitations} />
    </div>
  );
}

export function BiomedicineMappingView({ analysis }: { analysis: BiomedicineAnalysisPayload }) {
  return (
    <div className="view-stack biomed-view">
      <div className="mapping-summary">
        <div><span>IR / HAMILTONIAN</span><strong>{analysis.problem.id}</strong><small>{analysis.problem.type.toUpperCase()}</small></div>
        <div><span>IDENTITY</span><strong className="mono">{compactId(analysis.problem.hash, 18)}</strong><small>SHA-256</small></div>
        <div><span>EXECUTION FAMILY</span><strong>{analysis.executionFamily.toUpperCase()}</strong><small>{analysis.decision.recommendedMode.toUpperCase()}</small></div>
      </div>
      <section className="data-section">
        <div className="subsection-head">
          <div><span className="section-kicker"><GitBranch size={14} /> OPERATOR MAPPING</span><h3>{analysis.problem.type === "pauli_hamiltonian" ? "Pauli Hamiltonian 项" : "领域映射设计"}</h3></div>
          <span className="data-chip">{analysis.problem.terms.length} TERMS</span>
        </div>
        {analysis.problem.terms.length ? (
          <div className="table-scroll"><table><thead><tr><th>Term</th><th>Operator</th><th>Targets</th><th>Coefficient</th></tr></thead><tbody>{analysis.problem.terms.map((term) => <tr key={term.id}><td className="mono">{term.id}</td><td>{term.operator}</td><td className="mono">{term.targets.join(" · ")}</td><td>{term.coefficient.toFixed(9)}</td></tr>)}</tbody></table></div>
        ) : (
          <div className="preview-contract"><Binary size={22} /><strong>执行映射尚未发布</strong><span>当前页面只展示领域结构，不生成虚构的 Hamiltonian 或 QUBO 系数。</span></div>
        )}
      </section>
      {analysis.problem.measurementGroups?.length ? (
        <section className="data-section measurement-groups">
          <div className="subsection-head"><div><span className="section-kicker">QWC MEASUREMENT</span><h3>Pauli 测量分组</h3></div><span className="data-chip">{compactId(analysis.problem.measurementPlanHash ?? "", 18)}</span></div>
          <div className="group-grid">{analysis.problem.measurementGroups.map((group) => <div key={group.index}><small>GROUP {group.index + 1}</small><strong>{Object.entries(group.basis).map(([qubit, basis]) => `${basis}(${qubit})`).join(" · ")}</strong><span>{group.termIds.join(" / ")}</span></div>)}</div>
        </section>
      ) : null}
    </div>
  );
}

export function BiomedicineQuantumView({
  run,
  mode,
}: {
  run: BiomedicineRunPayload | null;
  mode: Mode;
}) {
  if (!run) return <div className="preview-contract quantum-empty"><Radio size={22} /><strong>{MODE_LABELS[mode]}</strong><span>运行可用场景后展示真实线路、QWC counts 和参数历史。</span></div>;
  const counts = Object.entries(run.quantum.counts)
    .sort((left, right) => right[1] - left[1])
    .map(([state, count], index) => ({ state, count, rank: index + 1 }));
  const best = Math.min(...run.quantum.parameterHistory.map((item) => item.objective));
  const history = run.quantum.parameterHistory.map((item) => ({ ...item, selected: item.objective === best }));
  return (
    <div className="view-stack biomed-view">
      <div className="experiment-banner"><div className="experiment-mode"><span className="mode-pulse" /><div><small>VQE / HARDWARE-EFFICIENT</small><strong>DIGITAL</strong></div></div><div className="experiment-telemetry"><span><small>QUBITS</small><strong>{run.quantum.summary.qubits}</strong></span><span><small>PAULI TERMS</small><strong>{run.quantum.summary.pauliTerms}</strong></span><span><small>QWC GROUPS</small><strong>{run.quantum.summary.measurementGroups}</strong></span><span><small>SHOTS / GROUP</small><strong>{run.quantum.summary.shotsPerGroup}</strong></span></div></div>
      <section className="data-section circuit-gate-table"><div className="subsection-head"><div><span className="section-kicker"><Atom size={14} /> DIGITAL CIRCUIT</span><h3>实际绑定 Ansatz 线路</h3></div><span className="data-chip">DEPTH {run.quantum.circuit.depth}</span></div><div className="gate-sequence">{run.quantum.circuit.gates.map((gate) => <div key={`${gate.depth}-${gate.name}`}><small>{String(gate.depth + 1).padStart(2, "0")}</small><strong>{gate.name}</strong><span>{gate.targets.join(" · ")}</span></div>)}</div></section>
      <div className="split-layout sampling-split">
        <section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Radio size={14} /> FINAL SAMPLING</span><h3>末端采样分布</h3></div></div><CountsChart counts={counts} /></section>
        <section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Activity size={14} /> OBJECTIVE HISTORY</span><h3>VQE 参数目标值</h3></div></div><ParameterChart history={history} /></section>
      </div>
    </div>
  );
}

export function BiomedicineAuditView({
  analysis,
  run,
}: {
  analysis: BiomedicineAnalysisPayload;
  run: BiomedicineRunPayload | null;
}) {
  const audit = run?.audit;
  const rows = audit
    ? [
        ["Manifest", audit.manifestHash],
        ["Hamiltonian", audit.hamiltonianHash],
        ["Analysis", audit.analysisHash],
        ["Ansatz", audit.ansatzHash],
        ["Measurement", audit.measurementPlanHash],
        ["Execution", audit.executionHash],
        ["Result", audit.resultHash],
      ]
    : [
        ["Manifest", analysis.dataset.manifestHash],
        ["Problem", analysis.problem.hash],
        ["Analysis", analysis.analysisHash ?? "not-executed"],
      ];
  return (
    <div className="view-stack biomed-view audit-view">
      <div className="audit-grid">
        <section className="audit-section"><span className="section-kicker">DATASET CONTEXT</span><dl><div><dt>Dataset</dt><dd>{analysis.dataset.id}</dd></div><div><dt>Version</dt><dd>{analysis.dataset.version}</dd></div><div><dt>Source</dt><dd>{analysis.dataset.sourceKind}</dd></div><div><dt>License</dt><dd>{analysis.dataset.license}</dd></div></dl></section>
        <section className="audit-section"><span className="section-kicker">SOURCE HASH CHAIN</span><div className="hash-chain">{rows.map(([label, value], index) => <div key={label}><span>{String(index + 1).padStart(2, "0")}</span><small>{label}</small><code>{value}</code></div>)}</div></section>
      </div>
      <section className="audit-json-section"><div className="subsection-head"><div><span className="section-kicker"><FileJson size={14} /> MACHINE EVIDENCE</span><h3>结构化审计载荷</h3></div></div><pre>{JSON.stringify(run?.audit ?? { dataset: analysis.dataset, analysisHash: analysis.analysisHash, execution: "not_run" }, null, 2)}</pre></section>
    </div>
  );
}
