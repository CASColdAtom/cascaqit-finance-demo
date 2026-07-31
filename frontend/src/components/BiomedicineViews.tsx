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
  Scale,
} from "lucide-react";
import type {
  ActiveCenterRunPayload,
  BiomedicineAnalysisPayload,
  BiomedicineRunPayload,
  BiomedicineStructureEdge,
  BiomedicineStructureNode,
  DockingRunPayload,
  DockingSolutionPayload,
  ElectronicStructureRunPayload,
  Mode,
  PeptideRunPayload,
  ProteinDynamicsRunPayload,
  ProteinPathSolutionPayload,
  RNARunPayload,
  RNAStructureSolutionPayload,
} from "../types";
import { compactId, MODE_LABELS } from "../utils";
import { AtomChart, CountsChart, ParameterChart, WaveformChart } from "./charts/Charts";
import { QuantumText } from "./QuantumText";

function isDockingRun(run: BiomedicineRunPayload): run is DockingRunPayload {
  return run.domain.kind === "docking_match_result";
}

function isActiveCenterRun(run: BiomedicineRunPayload): run is ActiveCenterRunPayload {
  return run.domain.kind === "active_center_result";
}

function isPeptideRun(run: BiomedicineRunPayload): run is PeptideRunPayload {
  return run.domain.kind === "peptide_landscape_result";
}

function isRnaRun(run: BiomedicineRunPayload): run is RNARunPayload {
  return run.domain.kind === "rna_structure_result";
}

function isProteinRun(run: BiomedicineRunPayload): run is ProteinDynamicsRunPayload {
  return run.domain.kind === "protein_dynamics_result";
}

function QuantumTerm({ short, title }: { short: string; title: string }) {
  return <abbr className="quantum-term" title={title}>{short}</abbr>;
}

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

function RNAArcDiagram({
  sequence,
  structure,
  label,
}: {
  sequence: string;
  structure: RNAStructureSolutionPayload;
  label: string;
}) {
  const denominator = Math.max(1, sequence.length - 1);
  const xFor = (position: number) => 6 + ((position - 1) * 88) / denominator;
  return (
    <div className="rna-arc-diagram" role="img" aria-label={label}>
      <svg viewBox="0 0 100 56" preserveAspectRatio="xMidYMid meet">
        <line className="rna-backbone" x1="6" y1="43" x2="94" y2="43" />
        {structure.pairs.map((pair, index) => {
          const left = xFor(pair.left);
          const right = xFor(pair.right);
          const height = Math.min(33, 7 + (pair.right - pair.left) * 2.25);
          return (
            <path
              className="rna-pair-arc"
              data-layer={index % 4}
              d={`M ${left} 43 Q ${(left + right) / 2} ${43 - height} ${right} 43`}
              key={pair.id}
            />
          );
        })}
        {[...sequence].map((nucleotide, index) => {
          const x = xFor(index + 1);
          return (
            <g className="rna-nucleotide" key={`${nucleotide}-${index}`}>
              <circle cx={x} cy="43" r="2.8" />
              <text x={x} y="44" textAnchor="middle">{nucleotide}</text>
              <text className="rna-position" x={x} y="51" textAnchor="middle">{index + 1}</text>
            </g>
          );
        })}
      </svg>
      <div><code>{structure.dotBracket}</code><span>{structure.pairCount} pairs · {structure.unpairedCount} unpaired</span></div>
    </div>
  );
}

function nodeRadius(node: BiomedicineStructureNode) {
  if (node.role === "spin_site" || node.role === "effective_spin_site") return 8;
  if (node.element === "H") return 7;
  return 6;
}

function EdgeTable({ edges }: { edges: BiomedicineStructureEdge[] }) {
  if (!edges.length) return null;
  return (
    <div className="table-wrap">
      <table className="data-table compact-table">
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

function BoundaryList({ values, allowed = false }: { values: string[]; allowed?: boolean }) {
  return (
    <div className={`boundary-list ${allowed ? "allowed-list" : ""}`}>
      {values.map((value) => (
        <span key={value}>{allowed ? <CheckCircle2 size={14} aria-hidden="true" /> : <CircleAlert size={14} aria-hidden="true" />}{value}</span>
      ))}
    </div>
  );
}

function customerCapability(value: string) {
  return value.replace(/^Demonstrate\s+/i, "");
}

function customerProteinLabel(value?: string) {
  return value?.replace(/\bteaching network\b/i, "conformational network") ?? "Conformational transition network";
}

function InterpretationBoundary({ analysis }: { analysis: BiomedicineAnalysisPayload }) {
  const capabilities = (analysis.dataset.allowedClaims ?? []).map(customerCapability);
  return (
    <div className="interpretation-boundary supported-capabilities">
      <div><small>VERIFIED CAPABILITIES</small><BoundaryList values={capabilities} allowed /></div>
    </div>
  );
}

function SubproblemSummary({ analysis }: { analysis: BiomedicineAnalysisPayload }) {
  const selection = analysis.domain.subproblemSelection;
  if (!selection || selection.coverageRate >= 1) return null;
  const complete = selection.completeMatchCount
    ?? selection.completeConformationCount
    ?? selection.completeStateCount
    ?? 0;
  const active = selection.selectedMatchCount
    ?? selection.selectedConformationCount
    ?? selection.selectedStateCount
    ?? 0;
  return (
    <div className="biomed-metric-band subproblem-summary">
      <div><small>COMPLETE DOMAIN</small><strong>{complete}</strong><span>完整领域候选</span></div>
      <div><small>QUANTUM WINDOW</small><strong>{active}</strong><span>进入实时 QUBO</span></div>
      <div><small>COVERAGE</small><strong>{(selection.coverageRate * 100).toFixed(1)}%</strong><span>确定性选择</span></div>
      <div><small>EXCLUDED</small><strong>{selection.excluded.length}</strong><span>原因可审计</span></div>
    </div>
  );
}

function RNASolutionCard({
  solution,
  title,
  tone,
}: {
  solution: RNAStructureSolutionPayload;
  title: string;
  tone: "quantum" | "classic" | "reference";
}) {
  return (
    <div className="rna-solution-card" data-tone={tone} data-feasible={solution.feasible}>
      <div><small>{title}</small><span>{solution.source.replaceAll("_", " ").toUpperCase()}</span></div>
      <strong>{solution.dotBracket}</strong>
      <dl>
        <div><dt>STRUCTURE SCORE</dt><dd>{solution.energy.toFixed(3)}</dd></div>
        <div><dt>PAIR COUNT</dt><dd>{solution.pairCount}</dd></div>
        <div><dt>REFERENCE OVERLAP</dt><dd>{(solution.referenceOverlapRate * 100).toFixed(1)}%</dd></div>
        <div><dt>CONSTRAINTS</dt><dd>{solution.feasible ? "PASS" : "FAIL"}</dd></div>
      </dl>
      <div className="rna-pair-token-list">
        {solution.pairs.map((pair) => <span key={pair.id}>{pair.left}-{pair.right} {pair.pairType}</span>)}
      </div>
    </div>
  );
}

function RNAAnalysisView({ analysis }: { analysis: BiomedicineAnalysisPayload }) {
  const reference = analysis.domain.referenceStructure;
  return (
    <div className="view-stack biomed-view rna-analysis-view">
      <section className="data-section">
        <div className="subsection-head">
          <div><span className="section-kicker"><GitBranch size={14} /> VERSIONED PAIR SET</span><h3>{analysis.domain.sequence}</h3></div>
          <span className="data-chip source-quantum">AVAILABLE</span>
        </div>
        {reference ? <RNAArcDiagram sequence={analysis.domain.sequence ?? ""} structure={reference} label="RNA 数据集参考二级结构" /> : null}
        <div className="rna-model-strip">
          <div><small>CANDIDATE PAIRS</small><strong>{analysis.domain.candidatePairs?.length ?? 0}</strong></div>
          <div><small>MINIMUM LOOP</small><strong>{analysis.domain.minimumLoop ?? "-"} nt</strong></div>
          <div><small>PSEUDOKNOT POLICY</small><strong>{analysis.domain.pseudoknotPolicy ?? "-"}</strong></div>
          <div><small>MODEL UNITS</small><strong>{analysis.domain.energyModel?.units ?? "-"}</strong></div>
        </div>
      </section>
      <InterpretationBoundary analysis={analysis} />
    </div>
  );
}

function ProteinNetworkDiagram({
  analysis,
  path = [],
  activeOnly = false,
  label,
}: {
  analysis: BiomedicineAnalysisPayload;
  path?: string[];
  activeOnly?: boolean;
  label: string;
}) {
  const nodes = activeOnly
    ? analysis.domain.activeNodes ?? []
    : analysis.domain.stateNodes ?? [];
  const transitions = activeOnly
    ? analysis.domain.activeEdges ?? []
    : analysis.domain.transitions ?? [];
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  const activeIds = new Set(
    analysis.domain.subproblemSelection?.activeNodeIds ?? [],
  );
  const pathEdges = new Set(
    path.slice(0, -1).map((nodeId, index) => `${nodeId}>${path[index + 1]}`),
  );
  const pathIds = new Set(path);
  return (
    <div className="protein-network" role="img" aria-label={label}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
        <defs>
          <marker id="protein-arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" />
          </marker>
        </defs>
        {transitions.map((transition) => {
          const source = nodeMap.get(transition.from);
          const target = nodeMap.get(transition.to);
          if (!source || !target) return null;
          const edgeId = `${transition.from}>${transition.to}`;
          return (
            <g
              className="protein-transition"
              data-active={activeIds.has(transition.from) && activeIds.has(transition.to)}
              data-path={pathEdges.has(edgeId)}
              key={transition.id}
            >
              <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} markerEnd="url(#protein-arrow)" />
              <text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2 - 2} textAnchor="middle">
                {transition.cost.toFixed(2)}
              </text>
            </g>
          );
        })}
        {nodes.map((node) => (
          <g
            className="protein-state"
            data-active={activeIds.has(node.id)}
            data-path={pathIds.has(node.id)}
            data-endpoint={node.id === analysis.domain.startState || node.id === analysis.domain.targetState}
            key={node.id}
          >
            <circle cx={node.x} cy={node.y} r="6.8" />
            <text x={node.x} y={node.y + 1} textAnchor="middle">{node.label}</text>
            <text className="protein-basin" x={node.x} y={node.y + 10} textAnchor="middle">{node.basin}</text>
          </g>
        ))}
      </svg>
      <div className="protein-network-legend">
        <span data-kind="active"><i />QUBO active</span>
        <span data-kind="path"><i />selected path</span>
        <span><i />complete network</span>
      </div>
    </div>
  );
}

function ProteinPathCard({
  path,
  title,
  tone,
}: {
  path: ProteinPathSolutionPayload | null;
  title: string;
  tone: "quantum" | "classic";
}) {
  return (
    <div className="protein-path-card" data-tone={tone} data-feasible={path?.feasible ?? false}>
      <div><small>{title}</small><span>{path?.source.replaceAll("_", " ").toUpperCase() ?? "QUANTUM NOT OBSERVED"}</span></div>
      <strong>{path?.stateIds.join(" → ") ?? "未观测到可行路径"}</strong>
      <dl>
        <div><dt>PATH COST</dt><dd>{path?.pathCost?.toFixed(3) ?? "N/A"}</dd></div>
        <div><dt>STEPS</dt><dd>{path?.pathLength ?? "-"}</dd></div>
        <div><dt>PATH OVERLAP</dt><dd>{path?.pathOverlap === undefined ? "-" : `${(path.pathOverlap * 100).toFixed(1)}%`}</dd></div>
        <div><dt>CONSTRAINTS</dt><dd>{path?.feasible ? "PASS" : "NO FALLBACK"}</dd></div>
      </dl>
    </div>
  );
}

function ProteinAnalysisView({ analysis }: { analysis: BiomedicineAnalysisPayload }) {
  const selection = analysis.domain.subproblemSelection;
  return (
    <div className="view-stack biomed-view protein-analysis-view">
      <div className="biomed-metric-band">
        <div><small>COMPLETE STATES</small><strong>{selection?.completeStateCount ?? 0}</strong><span>versioned network</span></div>
        <div><small>QUBO ACTIVE STATES</small><strong>{selection?.selectedStateCount ?? 0}</strong><span>connectivity preserved</span></div>
        <div><small>COMPLETE PATHS</small><strong>{selection?.completePathCount ?? 0}</strong><span>bounded simple paths</span></div>
        <div><small>ACTIVE PATHS</small><strong>{selection?.activePathCount ?? 0}</strong><span>start-to-target</span></div>
      </div>
      <section className="data-section">
        <div className="subsection-head"><div><span className="section-kicker"><GitBranch size={14} /> CONFORMATION NETWORK</span><h3>{customerProteinLabel(analysis.domain.proteinLabel)}</h3></div><span className="data-chip source-quantum">AVAILABLE</span></div>
        <ProteinNetworkDiagram analysis={analysis} label="完整蛋白构象状态网络与量子活动子图" />
        <div className="protein-model-strip">
          <div><small>START</small><strong>{analysis.domain.startState}</strong></div>
          <div><small>TARGET</small><strong>{analysis.domain.targetState}</strong></div>
          <div><small>WEIGHT PROFILE</small><strong>{analysis.domain.weightProfile}</strong></div>
          <div><small>MAX STEPS</small><strong>{analysis.domain.maximumSteps}</strong></div>
        </div>
      </section>
      <InterpretationBoundary analysis={analysis} />
    </div>
  );
}

function ProteinResultView({
  analysis,
  run,
}: {
  analysis: BiomedicineAnalysisPayload;
  run: ProteinDynamicsRunPayload;
}) {
  const candidate = run.domain.quantumCandidate;
  return (
    <div className="view-stack biomed-view protein-result-view">
      <div className="biomed-metric-band">
        <div data-pass={candidate?.feasible ?? false}><small>QUANTUM PATH</small><strong>{candidate ? "OBSERVED" : "NONE"}</strong><span>{candidate ? `${candidate.pathLength} transitions` : "no classic fallback"}</span></div>
        <div><small>FEASIBLE SHOT RATE</small><strong>{(run.domain.observedFeasibleRate * 100).toFixed(1)}%</strong><span>finite observed counts</span></div>
        <div><small>PATH COST</small><strong>{candidate?.pathCost?.toFixed(3) ?? "N/A"}</strong><span>dimensionless model cost</span></div>
        <div><small>CLASSIC OVERLAP</small><strong>{candidate ? `${((candidate.pathOverlap ?? 0) * 100).toFixed(1)}%` : "N/A"}</strong><span>directed-edge Jaccard</span></div>
      </div>
      <section className="data-section">
        <div className="subsection-head"><div><span className="section-kicker"><GitBranch size={14} /> OBSERVED TRANSITION PATH</span><h3>量子观测活动子图路径</h3></div><span className={`data-chip ${candidate ? "source-quantum" : "status-preview"}`}>{candidate ? "OBSERVED FEASIBLE" : "NO FALLBACK"}</span></div>
        <ProteinNetworkDiagram analysis={analysis} path={candidate?.stateIds ?? []} activeOnly label="量子观测蛋白构象转变路径" />
      </section>
      <section className="data-section">
        <div className="subsection-head"><div><span className="section-kicker">OBSERVED / CLASSIC BOUNDED DIJKSTRA</span><h3>量子路径与经典最短路</h3></div><span className="data-chip">DIMENSIONLESS COST</span></div>
        <div className="protein-path-grid">
          <ProteinPathCard path={candidate} title="量子观测候选" tone="quantum" />
          <ProteinPathCard path={run.domain.classicShortestPath} title="经典完整网络基线" tone="classic" />
        </div>
        <p className="subsection-note rna-count-warning"><CircleAlert size={14} /> {run.domain.interpretation}</p>
      </section>
      <InterpretationBoundary analysis={analysis} />
    </div>
  );
}

function RNAResultView({
  analysis,
  run,
}: {
  analysis: BiomedicineAnalysisPayload;
  run: RNARunPayload;
}) {
  const candidate = run.domain.quantumCandidate;
  const sequence = analysis.domain.sequence ?? "";
  return (
    <div className="view-stack biomed-view rna-result-view">
      <div className="biomed-metric-band">
        <div data-pass={candidate.feasible}><small>QUANTUM OBSERVED</small><strong>{candidate.feasible ? candidate.dotBracket : "NONE"}</strong><span>{candidate.feasible ? `${candidate.pairCount} base pairs` : "no classic fallback"}</span></div>
        <div><small>FEASIBLE SHOT RATE</small><strong>{(run.domain.observedFeasibleRate * 100).toFixed(1)}%</strong><span>finite observed counts</span></div>
        <div><small>LOW-SCORE COVERAGE</small><strong>{(run.domain.lowEnergyCoverage * 100).toFixed(1)}%</strong><span>within exact + 1.0</span></div>
        <div><small>STRUCTURE DIVERSITY</small><strong>{run.domain.structureDiversity}</strong><span>unique observed dot-brackets</span></div>
      </div>
      <section className="data-section">
        <div className="subsection-head"><div><span className="section-kicker"><GitBranch size={14} /> OBSERVED STRUCTURE</span><h3>量子观测二级结构</h3></div><span className={`data-chip ${candidate.feasible ? "source-quantum" : "status-preview"}`}>{candidate.feasible ? "OBSERVED FEASIBLE" : "NO FALLBACK"}</span></div>
        <RNAArcDiagram sequence={sequence} structure={candidate} label="量子观测 RNA 二级结构" />
      </section>
      <section className="data-section rna-comparison-section">
        <div className="subsection-head"><div><span className="section-kicker">OBSERVED / ENUMERATED / REFERENCE</span><h3>量子候选、经典最优与数据集参考</h3></div><span className="data-chip">DIMENSIONLESS SCORE</span></div>
        <div className="rna-solution-grid">
          <RNASolutionCard solution={candidate} title="量子观测候选" tone="quantum" />
          <RNASolutionCard solution={run.domain.classicExact} title="经典精确枚举" tone="classic" />
          <RNASolutionCard solution={run.domain.referenceStructure} title="数据集参考结构" tone="reference" />
        </div>
      </section>
      <section className="data-section">
        <div className="subsection-head"><div><span className="section-kicker">TOP-K OBSERVED FEASIBLE</span><h3>已观测低评分结构集合</h3></div><span className="data-chip">{run.domain.topObservedFeasible.length} STRUCTURES</span></div>
        <div className="table-wrap"><table className="data-table compact-table"><thead><tr><th>Rank</th><th>Dot-bracket</th><th>Score</th><th>Count</th><th>Reference overlap</th></tr></thead><tbody>{run.domain.topObservedFeasible.map((item, index) => <tr key={`${item.bitstring}-${index}`}><td>{index + 1}</td><td className="mono">{item.dotBracket}</td><td>{item.energy.toFixed(3)}</td><td>{item.count ?? 0}</td><td>{(item.referenceOverlapRate * 100).toFixed(1)}%</td></tr>)}</tbody></table></div>
        <p className="subsection-note rna-count-warning"><CircleAlert size={14} /> {run.domain.interpretation}</p>
      </section>
      <InterpretationBoundary analysis={analysis} />
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
    if (analysis.domain.kind === "rna_structure") {
      return <RNAAnalysisView analysis={analysis} />;
    }
    if (analysis.domain.kind === "protein_dynamics") {
      return <ProteinAnalysisView analysis={analysis} />;
    }
    return (
      <div className="view-stack biomed-view">
        <section className="data-section biomed-overview">
          <div className="subsection-head">
            <div><span className="section-kicker"><Beaker size={14} /> DOMAIN MODEL</span><h3>{analysis.domain.modelLevel ?? analysis.domain.geometryLabel ?? analysis.domain.kind}</h3></div>
            <span className={`data-chip status-${analysis.implementationStatus}`}>{analysis.implementationStatus.toUpperCase()}</span>
          </div>
          <SubproblemSummary analysis={analysis} />
          <StructureDiagram analysis={analysis} />
        </section>
        <InterpretationBoundary analysis={analysis} />
      </div>
    );
  }
  if (isDockingRun(run)) return <DockingResultView analysis={analysis} run={run} />;
  if (isActiveCenterRun(run)) return <ActiveCenterResultView analysis={analysis} run={run} />;
  if (isPeptideRun(run)) return <PeptideResultView analysis={analysis} run={run} />;
  if (isRnaRun(run)) return <RNAResultView analysis={analysis} run={run} />;
  if (isProteinRun(run)) return <ProteinResultView analysis={analysis} run={run} />;
  const result = run.domain;
  const accuracyApplies = result.withinChemicalAccuracy !== null;
  const energyRows: Array<[string, number]> = [
    ["Hartree-Fock", run.comparison.hartreeFockEnergy],
    ["VQE objective", run.comparison.vqeExactEnergy],
    ["Ideal QWC", run.comparison.vqeSampledEnergy],
    ["Exact", run.comparison.exactGroundEnergy],
  ];
  if (run.comparison.vqeNoisySampledEnergy !== null) {
    energyRows.splice(3, 0, ["Noisy QWC", run.comparison.vqeNoisySampledEnergy]);
  }
  return (
    <div className="view-stack biomed-view">
      <div className="biomed-metric-band">
        <div><small>{result.molecule} / <QuantumTerm short="VQE" title="变分量子本征求解器" /> OBJECTIVE</small><strong>{result.exactOptimizedEnergy.toFixed(6)}</strong><span>Hartree</span></div>
        <div><small>IDEAL <QuantumTerm short="QWC" title="逐量子比特可对易测量分组" /></small><strong>{result.sampledConfirmationEnergy.toFixed(6)}</strong><span>± {result.sampledStandardError.toFixed(4)}</span></div>
        {result.noisySampledConfirmationEnergy !== null ? <div><small>READOUT-NOISE QWC</small><strong>{result.noisySampledConfirmationEnergy.toFixed(6)}</strong><span>± {result.noisySampledStandardError?.toFixed(4)}</span></div> : null}
        <div><small>EXACT REFERENCE</small><strong>{result.referenceEnergy.toFixed(6)}</strong><span>Hartree</span></div>
        <div data-pass={result.withinChemicalAccuracy ?? undefined}><small>ABSOLUTE ERROR</small><strong>{(result.absoluteErrorHartree * 1000).toFixed(3)}</strong><span>{(result.relativeError * 100).toFixed(4)}%</span></div>
      </div>
      <section className="data-section energy-comparison">
        <div className="subsection-head">
          <div><span className="section-kicker"><Activity size={14} /> ENERGY EVIDENCE</span><h3>基态能量对照</h3></div>
          <span className={`data-chip ${result.withinChemicalAccuracy === true ? "source-quantum" : accuracyApplies ? "status-preview" : ""}`}>
            {result.withinChemicalAccuracy === true ? <CheckCircle2 size={13} /> : accuracyApplies ? <CircleAlert size={13} /> : null}
            {accuracyApplies ? result.withinChemicalAccuracy ? "≤ 1.6 mHa" : "> 1.6 mHa" : "ERROR REPORTED"}
          </span>
        </div>
        <div className="energy-axis">
          {energyRows.map(([label, value]) => (
            <div key={label} style={{ "--energy-position": `${energyPosition(value, run)}%` } as React.CSSProperties}>
              <i /><strong>{label}</strong><span>{value.toFixed(6)} Ha</span>
            </div>
          ))}
        </div>
        <p className="subsection-note">{result.estimatorNote}</p>
      </section>
      {analysis.domain.bondScanReference?.length ? (
        <section className="data-section bond-scan-reference">
          <div className="subsection-head"><div><span className="section-kicker">H2 BOND SCAN / CLASSIC REFERENCE</span><h3>固定几何能量趋势</h3></div><span className="data-chip">3 POINTS</span></div>
          <div className="bond-scan-points">
            {analysis.domain.bondScanReference.map((point) => (
              <div key={point.dataset} data-selected={point.selected}>
                <small>{point.bondLengthAngstrom.toFixed(3)} Å</small>
                <strong>{point.exactGroundEnergy.toFixed(6)}</strong>
                <span><QuantumTerm short="HF" title="Hartree-Fock 平均场参考" /> {point.hartreeFockEnergy.toFixed(6)} Ha</span>
              </div>
            ))}
          </div>
          <p className="subsection-note">三点均来自各自固化 Pauli Hamiltonian 的经典精确对角化；当前 VQE 只执行选中的几何点。</p>
        </section>
      ) : null}
      <InterpretationBoundary analysis={analysis} />
    </div>
  );
}

function PeptideResultView({ analysis, run }: { analysis: BiomedicineAnalysisPayload; run: PeptideRunPayload }) {
  const candidate = run.domain.quantumCandidate;
  const minimum = run.domain.classicGroundConformations[0]?.energy ?? 0;
  const maximum = Math.max(...run.domain.fullLandscape.map((item) => item.energy));
  const span = Math.max(0.1, maximum - minimum);
  return (
    <div className="view-stack biomed-view peptide-result-view">
      <SubproblemSummary analysis={analysis} />
      <div className="biomed-metric-band">
        <div data-pass={candidate.feasible}><small>QUANTUM CANDIDATE</small><strong>{candidate.conformationId ?? "NONE"}</strong><span>{candidate.feasible ? "observed feasible" : "no classic fallback"}</span></div>
        <div><small>COARSE ENERGY</small><strong>{candidate.energy?.toFixed(3) ?? "N/A"}</strong><span>dimensionless</span></div>
        <div><small>GROUND DEGENERACY</small><strong>{run.domain.classicGroundConformations.length}</strong><span>{run.domain.classicGroundConformations.map((item) => item.id).join(" / ")}</span></div>
        <div data-pass={run.domain.energyGapFromGround === 0}><small>GAP FROM GROUND</small><strong>{run.domain.energyGapFromGround?.toFixed(3) ?? "N/A"}</strong><span>observed vs enumeration</span></div>
      </div>
      <section className="data-section">
        <div className="subsection-head"><div><span className="section-kicker"><Activity size={14} /> COMPLETE CLASSIC LANDSCAPE</span><h3>量子候选与完整离散能景</h3></div><span className="data-chip source-quantum">{run.domain.observedFeasibleCount} OBSERVED</span></div>
        <div className="peptide-landscape-list">
          {run.domain.fullLandscape.slice(0, 24).map((item) => (
            <div key={item.id} data-selected={item.id === candidate.conformationId} data-ground={item.energy === minimum}>
              <strong>{item.id}</strong><i><b style={{ width: `${Math.max(3, ((maximum - item.energy) / span) * 100)}%` }} /></i><span>{item.energy.toFixed(3)}</span><small>{item.contactCount} contacts</small>
            </div>
          ))}
        </div>
        {run.domain.fullLandscape.length > 24 ? <p className="subsection-note">完整能景共 {run.domain.fullLandscape.length} 个构象；图中显示按能量排序的前 24 个，活动窗口与排除账本保留在分析证据中。</p> : null}
        <p className="subsection-note">{run.domain.interpretation}</p>
      </section>
      <InterpretationBoundary analysis={analysis} />
    </div>
  );
}

function ActiveCenterResultView({
  analysis,
  run,
}: {
  analysis: BiomedicineAnalysisPayload;
  run: ActiveCenterRunPayload;
}) {
  const result = run.domain;
  const hashesMatch =
    run.comparison.hamiltonianHash === run.comparison.vqeHamiltonianHash;
  return (
    <div className="view-stack biomed-view active-center-result-view">
      <div className="biomed-metric-band">
        <div><small><QuantumTerm short="VQE" title="变分量子本征求解器" /> EXACT OBJECTIVE</small><strong>{result.vqeExactEnergyMeV.toFixed(5)}</strong><span>meV</span></div>
        <div><small><QuantumTerm short="QWC" title="逐量子比特可对易测量分组" /> CONFIRMATION</small><strong>{result.sampledEnergyMeV.toFixed(5)}</strong><span>± {result.sampledStandardErrorMeV.toFixed(4)} meV</span></div>
        <div><small>EXACT REFERENCE</small><strong>{result.exactGroundEnergyMeV.toFixed(5)}</strong><span>classic gap {result.exactFirstGapMeV.toFixed(4)} meV</span></div>
        <div data-pass={hashesMatch}><small>HAMILTONIAN IDENTITY</small><strong>{hashesMatch ? "MATCH" : "MISMATCH"}</strong><span>{compactId(run.audit.hamiltonianHash, 14)}</span></div>
      </div>
      <div className="split-layout spin-observable-split">
        <section className="data-section">
          <div className="subsection-head"><div><span className="section-kicker"><Activity size={14} /> BACKEND OBSERVABLES</span><h3>局域磁化与两点自旋关联</h3></div><span className="data-chip source-quantum">QWC COUNTS</span></div>
          <div className="spin-observable-grid">
            {result.magnetization.map((item) => (
              <div key={item.siteId}><small>LOCAL Z / {item.siteId}</small><strong>{item.expectation.toFixed(4)}</strong><span>± {item.standardError.toFixed(4)}</span></div>
            ))}
            {result.correlations.map((item) => (
              <div key={`${item.pathId}-${item.operator}`}><small>{item.pathId} / {item.operator}</small><strong>{item.expectation.toFixed(4)}</strong><span>{item.leftSiteId} · {item.rightSiteId} / ± {item.standardError.toFixed(4)}</span></div>
            ))}
          </div>
        </section>
        <section className="data-section">
          <div className="subsection-head"><div><span className="section-kicker">DECLARED SPIN SECTOR</span><h3>总磁化扇区占据</h3></div><span className="data-chip">{result.declaredSector}</span></div>
          <div className="sector-occupancy-list">
            {Object.entries(result.sectorOccupancy).map(([sector, occupancy]) => (
              <div key={sector}><span>{sector}</span><i><b style={{ width: `${Math.max(2, occupancy * 100)}%` }} /></i><strong>{(occupancy * 100).toFixed(1)}%</strong></div>
            ))}
          </div>
          <p className="subsection-note">{result.interpretation}</p>
        </section>
      </div>
      <InterpretationBoundary analysis={analysis} />
    </div>
  );
}

function DockingSolution({
  solution,
  title,
  tone,
}: {
  solution: DockingSolutionPayload;
  title: string;
  tone: string;
}) {
  return (
    <div className="docking-solution" data-tone={tone} data-feasible={solution.feasible}>
      <div>
        <small>{title}</small>
        <span>{solution.source.replaceAll("_", " ").toUpperCase()}</span>
      </div>
      <strong>{solution.poseId ?? "NO CONSISTENT POSE"}</strong>
      <dl>
        <div><dt>MODEL OBJECTIVE</dt><dd>{solution.modelObjective.toFixed(4)}</dd></div>
        <div><dt>FEATURE COVERAGE</dt><dd>{solution.coverage}</dd></div>
        <div><dt>REFERENCE OVERLAP</dt><dd>{solution.referenceOverlap}</dd></div>
        <div><dt>CONSTRAINTS</dt><dd>{solution.feasible ? "PASS" : "FAIL"}</dd></div>
      </dl>
      <div className="match-token-list">
        {solution.selectedMatchIds.map((matchId) => <span key={matchId}>{matchId}</span>)}
      </div>
    </div>
  );
}

function DockingResultView({
  analysis,
  run,
}: {
  analysis: BiomedicineAnalysisPayload;
  run: DockingRunPayload;
}) {
  const candidate = run.domain.quantumCandidate;
  return (
    <div className="view-stack biomed-view docking-result-view">
      <SubproblemSummary analysis={analysis} />
      <div className="biomed-metric-band">
        <div data-pass={candidate.feasible}><small>QUANTUM CANDIDATE</small><strong>{candidate.feasible ? "FEASIBLE" : "INFEASIBLE"}</strong><span>observed samples only</span></div>
        <div><small>SELECTED POSE</small><strong>{candidate.poseId ?? "NONE"}</strong><span>single-pose check</span></div>
        <div><small>FEATURE COVERAGE</small><strong>{candidate.coverage}</strong><span>minimum {analysis.domain.minimumCoverage}</span></div>
        <div><small>OBSERVED FEASIBLE</small><strong>{run.domain.observedFeasibleCount}</strong><span>unique Top-K pool</span></div>
      </div>
      <section className="data-section docking-comparison">
        <div className="subsection-head">
          <div><span className="section-kicker"><Activity size={14} /> CANDIDATE SEPARATION</span><h3>量子候选、经典最优与共晶参考</h3></div>
          <span className={`data-chip ${candidate.feasible ? "source-quantum" : "status-preview"}`}>
            {candidate.feasible ? <CheckCircle2 size={13} /> : <CircleAlert size={13} />}
            {candidate.feasible ? "QUANTUM FEASIBLE" : "NO QUANTUM FALLBACK"}
          </span>
        </div>
        <div className="docking-solution-grid">
          <DockingSolution solution={candidate} title="量子观测候选" tone="quantum" />
          <DockingSolution solution={run.domain.classicOptimum} title="经典枚举最优" tone="classic" />
          <DockingSolution solution={run.domain.coCrystalReference} title="共晶派生参考" tone="reference" />
        </div>
      </section>
      <section className="data-section">
        <div className="subsection-head"><div><span className="section-kicker">DOMAIN VALIDATION</span><h3>量子候选约束复核</h3></div></div>
        <div className="docking-check-grid">
          {candidate.checks.map((check) => (
            <div key={check.id} data-pass={check.passed}>
              {check.passed ? <CheckCircle2 size={15} /> : <CircleAlert size={15} />}
              <strong>{check.label}</strong><span>{String(check.actual)} / {String(check.expected)}</span>
            </div>
          ))}
        </div>
        <p className="subsection-note">{run.domain.interpretation}</p>
      </section>
      <InterpretationBoundary analysis={analysis} />
    </div>
  );
}

function energyPosition(value: number, run: ElectronicStructureRunPayload) {
  const values = [
    run.comparison.hartreeFockEnergy,
    run.comparison.exactGroundEnergy,
    run.comparison.vqeExactEnergy,
    run.comparison.vqeSampledEnergy,
    ...(run.comparison.vqeNoisySampledEnergy === null ? [] : [run.comparison.vqeNoisySampledEnergy]),
  ];
  const minimum = Math.min(...values) - 0.005;
  const maximum = Math.max(...values) + 0.005;
  return Math.max(0, Math.min(100, ((value - minimum) / (maximum - minimum)) * 100));
}

function ComparisonTable({
  rows,
}: {
  rows: Array<{ source: string; candidate: string; value: string; evidence: string }>;
}) {
  return (
    <div className="table-wrap">
      <table className="data-table comparison-table">
        <thead><tr><th>对照来源</th><th>候选 / 方法</th><th>结果</th><th>证据边界</th></tr></thead>
        <tbody>{rows.map((row) => (
          <tr key={`${row.source}-${row.candidate}`}>
            <td>{row.source}</td><td className="mono">{row.candidate}</td><td className="mono">{row.value}</td><td>{row.evidence}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

export function BiomedicineComparisonView({
  analysis,
  run,
}: {
  analysis: BiomedicineAnalysisPayload;
  run: BiomedicineRunPayload | null;
}) {
  if (!run) {
    return (
      <div className="view-stack biomed-view">
        <section className="data-section comparison-empty">
          <Scale aria-hidden="true" />
          <h3>执行后生成独立对照</h3>
          <p>对照视图只使用本次量子观测、固化经典基线与数据集参考，不预填运行结论。</p>
        </section>
        <InterpretationBoundary analysis={analysis} />
      </div>
    );
  }
  if (isDockingRun(run)) {
    return (
      <div className="view-stack biomed-view">
        <section className="data-section docking-comparison">
          <div className="subsection-head"><div><span className="section-kicker">OBSERVED / ENUMERATED / REFERENCE</span><h3>构象匹配三方对照</h3></div><span className="data-chip">DISCRETE SCORE</span></div>
          <div className="docking-solution-grid">
            <DockingSolution solution={run.domain.quantumCandidate} title="量子观测候选" tone="quantum" />
            <DockingSolution solution={run.domain.classicOptimum} title="经典枚举最优" tone="classic" />
            <DockingSolution solution={run.domain.coCrystalReference} title="共晶派生参考" tone="reference" />
          </div>
        </section>
        <InterpretationBoundary analysis={analysis} />
      </div>
    );
  }
  if (isPeptideRun(run)) {
    const groundIds = run.domain.classicGroundConformations.map((item) => item.id).join(" / ");
    return (
      <div className="view-stack biomed-view">
        <section className="data-section">
          <div className="subsection-head"><div><span className="section-kicker"><QuantumTerm short="QAOA" title="量子近似优化算法" /> / COMPLETE ENUMERATION</span><h3>小肽候选与完整能景对照</h3></div><span className="data-chip">{run.domain.fullLandscape.length} CONFORMATIONS</span></div>
          <ComparisonTable rows={[
            { source: "量子观测", candidate: run.domain.quantumCandidate.conformationId ?? "NONE", value: run.domain.quantumCandidate.energy?.toFixed(3) ?? "N/A", evidence: run.domain.quantumCandidate.feasible ? "可行采样候选" : "未观测到可行候选" },
            { source: "经典全枚举", candidate: groundIds || "NONE", value: run.domain.classicGroundConformations[0]?.energy.toFixed(3) ?? "N/A", evidence: "有限构象库最低能级" },
            { source: "完整能景位置", candidate: `${run.domain.fullLandscape.findIndex((item) => item.id === run.domain.quantumCandidate.conformationId) + 1}/${run.domain.fullLandscape.length}`, value: run.domain.energyGapFromGround?.toFixed(3) ?? "N/A", evidence: "候选相对基态能隙" },
          ]} />
        </section>
        <InterpretationBoundary analysis={analysis} />
      </div>
    );
  }
  if (isRnaRun(run)) {
    return (
      <div className="view-stack biomed-view rna-comparison-view">
        <section className="data-section">
          <div className="subsection-head"><div><span className="section-kicker"><QuantumTerm short="QAOA" title="量子近似优化算法" /> / EXACT / DYNAMIC PROGRAMMING</span><h3>RNA 二级结构四方对照</h3></div><span className="data-chip">STRUCTURE SCORE</span></div>
          <ComparisonTable rows={[
            { source: "量子观测", candidate: run.domain.quantumCandidate.dotBracket, value: run.domain.quantumCandidate.feasible ? run.domain.quantumCandidate.energy.toFixed(3) : "N/A", evidence: run.domain.quantumCandidate.feasible ? "本次有限 shots 已观测可行结构" : "未观测到可行结构，未使用经典回填" },
            { source: "经典精确枚举", candidate: run.domain.classicExact.dotBracket, value: run.domain.classicExact.energy.toFixed(3), evidence: "固化候选配对空间全枚举" },
            { source: "经典动态规划", candidate: run.domain.classicDynamicProgramming.dotBracket, value: run.domain.classicDynamicProgramming.energy.toFixed(3), evidence: "无假结二级结构基线" },
            { source: "数据集参考", candidate: run.domain.referenceStructure.declaredDotBracket ?? run.domain.referenceStructure.dotBracket, value: run.domain.referenceStructure.energy.toFixed(3), evidence: run.domain.referenceStructure.sourceId ?? "versioned reference" },
          ]} />
        </section>
        <p className="subsection-note rna-count-warning"><CircleAlert size={14} /> {run.domain.interpretation}</p>
        <InterpretationBoundary analysis={analysis} />
      </div>
    );
  }
  if (isProteinRun(run)) {
    const candidate = run.domain.quantumCandidate;
    return (
      <div className="view-stack biomed-view protein-comparison-view">
        <section className="data-section">
          <div className="subsection-head"><div><span className="section-kicker"><QuantumTerm short="QAOA" title="量子近似优化算法" /> / BOUNDED DIJKSTRA</span><h3>构象转变路径三方对照</h3></div><span className="data-chip">DIMENSIONLESS COST</span></div>
          <ComparisonTable rows={[
            { source: "量子观测", candidate: candidate?.stateIds.join(" → ") ?? "NONE", value: candidate?.pathCost?.toFixed(3) ?? "N/A", evidence: candidate ? `本次有限 shots 可行路径；重合度 ${((candidate.pathOverlap ?? 0) * 100).toFixed(1)}%` : "未观测到可行路径，未使用经典回填" },
            { source: "经典完整网络", candidate: run.domain.classicShortestPath.stateIds.join(" → "), value: run.domain.classicShortestPath.pathCost?.toFixed(3) ?? "N/A", evidence: "版本化完整网络的有界 Dijkstra 基线" },
            { source: "经典活动子图", candidate: run.domain.classicActivePath.stateIds.join(" → "), value: run.domain.classicActivePath.pathCost?.toFixed(3) ?? "N/A", evidence: "与量子 QUBO 相同活动状态集合" },
          ]} />
        </section>
        <p className="subsection-note rna-count-warning"><CircleAlert size={14} /> {run.domain.interpretation}</p>
        <InterpretationBoundary analysis={analysis} />
      </div>
    );
  }
  if (isActiveCenterRun(run)) {
    const hashesMatch = run.comparison.hamiltonianHash === run.comparison.vqeHamiltonianHash;
    return (
      <div className="view-stack biomed-view">
        <section className="data-section">
          <div className="subsection-head"><div><span className="section-kicker"><QuantumTerm short="VQE" title="变分量子本征求解器" /> / EXACT DIAGONALIZATION</span><h3>有效自旋 Hamiltonian 对照</h3></div><span className={`data-chip ${hashesMatch ? "source-quantum" : "status-preview"}`}>{hashesMatch ? "HASH MATCH" : "HASH MISMATCH"}</span></div>
          <ComparisonTable rows={[
            { source: "VQE 目标", candidate: "optimized state", value: `${run.domain.vqeExactEnergyMeV.toFixed(5)} meV`, evidence: "同一固化 Hamiltonian" },
            { source: "QWC 采样", candidate: "measurement groups", value: `${run.domain.sampledEnergyMeV.toFixed(5)} ± ${run.domain.sampledStandardErrorMeV.toFixed(4)} meV`, evidence: "有限 shots 统计量" },
            { source: "经典精确对角化", candidate: run.comparison.referenceMethod, value: `${run.domain.exactGroundEnergyMeV.toFixed(5)} meV`, evidence: `绝对误差 ${run.domain.absoluteErrorMeV.toFixed(5)} meV` },
            { source: "经典第一能隙", candidate: "exact diagonalization", value: `${run.domain.exactFirstGapMeV.toFixed(5)} meV`, evidence: "经典参考，不是 VQD 结果" },
            { source: "关联对照", candidate: "XX / YY / ZZ", value: run.domain.correlations.map((item) => `${item.operator}=${item.expectation.toFixed(3)}`).join(" · "), evidence: "有效自旋模型内解释" },
          ]} />
        </section>
        <InterpretationBoundary analysis={analysis} />
      </div>
    );
  }
  return (
    <div className="view-stack biomed-view">
      <section className="data-section">
        <div className="subsection-head"><div><span className="section-kicker"><QuantumTerm short="VQE" title="变分量子本征求解器" /> / CLASSIC REFERENCES</span><h3>小分子基态能量对照</h3></div><span className="data-chip">HARTREE</span></div>
        <ComparisonTable rows={[
          { source: "Hartree-Fock", candidate: "mean-field baseline", value: run.comparison.hartreeFockEnergy.toFixed(6), evidence: "数据集固化参考" },
          { source: "VQE 目标", candidate: "optimized statevector", value: run.comparison.vqeExactEnergy.toFixed(6), evidence: "优化点精确目标值" },
          { source: "理想 QWC", candidate: "finite-shot groups", value: run.comparison.vqeSampledEnergy.toFixed(6), evidence: `标准误 ${run.domain.sampledStandardError.toFixed(4)}` },
          ...(run.comparison.vqeNoisySampledEnergy === null ? [] : [{ source: "读出噪声 QWC", candidate: "readout-noise groups", value: run.comparison.vqeNoisySampledEnergy.toFixed(6), evidence: `标准误 ${run.domain.noisySampledStandardError?.toFixed(4) ?? "N/A"}` }]),
          { source: "经典精确对角化", candidate: run.comparison.referenceMethod, value: run.comparison.exactGroundEnergy.toFixed(6), evidence: `绝对误差 ${run.domain.absoluteErrorHartree.toFixed(6)} Ha` },
        ]} />
      </section>
      <InterpretationBoundary analysis={analysis} />
    </div>
  );
}

export function BiomedicineStructureView({ analysis }: { analysis: BiomedicineAnalysisPayload }) {
  if (analysis.domain.kind === "protein_dynamics") {
    return (
      <div className="view-stack biomed-view protein-structure-view">
        <section className="data-section">
          <div className="subsection-head"><div><span className="section-kicker"><GitBranch size={14} /> COMPLETE / ACTIVE NETWORK</span><h3>{customerProteinLabel(analysis.domain.proteinLabel)}</h3></div><span className="data-chip">{analysis.domain.stateNodes?.length ?? 0} STATES</span></div>
          <ProteinNetworkDiagram analysis={analysis} label="完整构象状态网络与活动子图" />
        </section>
        <section className="data-section">
          <div className="subsection-head"><div><span className="section-kicker">TRANSITION PROVENANCE</span><h3>允许转移、边权与来源</h3></div><span className="data-chip">{analysis.domain.transitions?.length ?? 0} EDGES</span></div>
          <div className="table-wrap"><table className="data-table compact-table"><thead><tr><th>Transition</th><th>From → To</th><th>Cost</th><th>Profile / source</th></tr></thead><tbody>{analysis.domain.transitions?.map((edge) => <tr key={edge.id}><td className="mono">{edge.id}</td><td className="mono">{edge.from} → {edge.to}</td><td>{edge.cost.toFixed(3)}</td><td>{edge.barrierProfile}<small>curated coarse-grained transition score</small></td></tr>)}</tbody></table></div>
        </section>
      </div>
    );
  }
  const edges = analysis.domain.bonds ?? analysis.domain.edges ?? [];
  const rnaReference = analysis.domain.referenceStructure;
  return (
    <div className="view-stack biomed-view">
      <section className="data-section">
        <div className="subsection-head">
          <div><span className="section-kicker"><Atom size={14} /> DOMAIN STRUCTURE</span><h3>{analysis.domain.molecule ?? analysis.domain.sequence ?? analysis.domain.modelLevel ?? "场景结构"}</h3></div>
          <span className="data-chip">{analysis.problem.variables.length} OBJECTS</span>
        </div>
        {analysis.domain.kind === "rna_structure" && rnaReference ? (
          <RNAArcDiagram sequence={analysis.domain.sequence ?? ""} structure={rnaReference} label="RNA 数据集参考二级结构" />
        ) : (
          <StructureDiagram analysis={analysis} />
        )}
      </section>
      <section className="data-section">
        <div className="subsection-head"><div><span className="section-kicker">RELATIONSHIP EVIDENCE</span><h3>结构关系</h3></div></div>
        <EdgeTable edges={edges} />
      </section>
    </div>
  );
}

export function BiomedicineMappingView({ analysis }: { analysis: BiomedicineAnalysisPayload }) {
  return (
    <div className="view-stack biomed-view">
      <div className="mapping-summary">
        <div><span>IR / HAMILTONIAN</span><strong>{analysis.problem.id}</strong><small><QuantumText text={analysis.problem.type.toUpperCase()} /></small></div>
        <div><span>IDENTITY</span><strong className="mono">{compactId(analysis.problem.hash, 18)}</strong><small>SHA-256</small></div>
        <div><span>EXECUTION FAMILY</span><strong>{analysis.executionFamily.toUpperCase()}</strong><small>{analysis.decision.recommendedMode.toUpperCase()}</small></div>
      </div>
      <section className="data-section">
        <div className="subsection-head">
          <div><span className="section-kicker"><GitBranch size={14} /> OPERATOR MAPPING</span><h3>{analysis.problem.type === "pauli_hamiltonian" ? "Pauli Hamiltonian 项" : "领域映射设计"}</h3></div>
          <span className="data-chip">{analysis.problem.terms.length} TERMS</span>
        </div>
        {analysis.problem.terms.length ? (
          <div className="table-wrap"><table className="data-table compact-table"><thead><tr><th>Term</th><th>Operator</th><th>Targets</th><th>Coefficient</th></tr></thead><tbody>{analysis.problem.terms.map((term) => <tr key={term.id}><td className="mono">{term.id}</td><td>{term.operator}</td><td className="mono">{term.targets.join(" · ")}</td><td>{term.coefficient.toFixed(9)}</td></tr>)}</tbody></table></div>
        ) : (
          <div className="preview-contract"><Binary size={22} /><strong>执行映射尚未发布</strong><span>当前页面只展示领域结构，不生成虚构的 Hamiltonian 或 QUBO 系数。</span></div>
        )}
      </section>
      {analysis.problem.termGroups?.length ? (
        <div className="split-layout docking-mapping-split">
          <section className="data-section">
            <div className="subsection-head"><div><span className="section-kicker">DOMAIN TERM GROUPS</span><h3><QuantumText text="QUBO 领域分组" /></h3></div><span className="data-chip">{analysis.problem.termGroups.length} GROUPS</span></div>
            <div className="term-groups">
              {analysis.problem.termGroups.map((group) => (
                <div key={group.group_id}><span>{group.kind}</span><strong>{group.label}</strong><small>{group.pairs.length ? `${group.pairs.length} conflict pairs` : `${group.variables.length} variables`}</small></div>
              ))}
            </div>
          </section>
          <section className="data-section">
            <div className="subsection-head"><div><span className="section-kicker">HYBRID GATE</span><h3>Analog / Digital 分配门禁</h3></div></div>
            <div className="hybrid-gate-list">
              {analysis.decision.modes.map((row) => (
                <div key={row.mode} data-status={row.status}>
                  <strong>{row.mode.toUpperCase()}</strong>
                  <span>{row.status.toUpperCase()}</span>
                  <small>{row.analogTermCount ?? 0} A / {row.digitalTermCount ?? 0} D · {row.geometryStatus ?? "n/a"}</small>
                </div>
              ))}
            </div>
          </section>
        </div>
      ) : null}
      {analysis.problem.coefficientLedger ? (
        <section className="data-section">
          <div className="subsection-head"><div><span className="section-kicker">COEFFICIENT LEDGER</span><h3><QuantumText text="QUBO 贡献账本" /></h3></div><span className={`data-chip ${analysis.problem.coefficientLedger.balanced ? "source-quantum" : "status-preview"}`}>{analysis.problem.coefficientLedger.balanced ? "BALANCED" : "MISMATCH"}</span></div>
          <div className="table-wrap"><table className="data-table compact-table"><thead><tr><th>Contribution</th><th>Group / Rule</th><th>Targets</th><th>Coefficient</th></tr></thead><tbody>{analysis.problem.coefficientLedger.rows.map((row) => <tr key={row.contributionId}><td className="mono">{row.contributionId}</td><td>{row.groupId}<small>{row.sourceRule}</small></td><td className="mono">{row.targets.join(" · ") || "offset"}</td><td>{row.coefficient.toFixed(6)}</td></tr>)}</tbody></table></div>
        </section>
      ) : null}
      {analysis.problem.measurementGroups?.length ? (
        <section className="data-section measurement-groups">
          <div className="subsection-head"><div><span className="section-kicker"><QuantumText text="QWC MEASUREMENT" /></span><h3>Pauli 测量分组</h3></div><span className="data-chip">{compactId(analysis.problem.measurementPlanHash ?? "", 18)}</span></div>
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
  if (!run) return <div className="preview-contract quantum-empty"><Radio size={22} /><strong><QuantumText text={MODE_LABELS[mode]} /></strong><span><QuantumText text="运行可用场景后展示真实线路、QWC counts 和参数历史。" /></span></div>;
  if (isDockingRun(run)) return <DockingQuantumView run={run} />;
  if (isPeptideRun(run)) return <PeptideQuantumView run={run} />;
  if (isRnaRun(run)) return <RNAQuantumView run={run} />;
  if (isProteinRun(run)) return <ProteinQuantumView run={run} />;
  const counts = Object.entries(run.quantum.counts)
    .sort((left, right) => right[1] - left[1])
    .map(([state, count], index) => ({ state, count, rank: index + 1 }));
  const best = Math.min(...run.quantum.parameterHistory.map((item) => item.objective));
  const history = run.quantum.parameterHistory.map((item) => ({ ...item, selected: item.objective === best }));
  return (
    <div className="view-stack biomed-view">
      <div className="experiment-banner"><div className="experiment-mode"><span className="mode-pulse" /><div><small><QuantumText text="VQE / HARDWARE-EFFICIENT" /></small><strong>DIGITAL</strong></div></div><div className="experiment-telemetry"><span><small>QUBITS</small><strong>{run.quantum.summary.qubits}</strong></span><span><small>PAULI TERMS</small><strong>{run.quantum.summary.pauliTerms}</strong></span><span><small><QuantumText text="QWC GROUPS" /></small><strong>{run.quantum.summary.measurementGroups}</strong></span><span><small>SHOTS / GROUP</small><strong>{run.quantum.summary.shotsPerGroup}</strong></span></div></div>
      <section className="data-section circuit-gate-table"><div className="subsection-head"><div><span className="section-kicker"><Atom size={14} /> DIGITAL CIRCUIT</span><h3>实际绑定 Ansatz 线路</h3></div><span className="data-chip">DEPTH {run.quantum.circuit.depth}</span></div><div className="gate-sequence">{run.quantum.circuit.gates.map((gate) => <div key={`${gate.depth}-${gate.name}`}><small>{String(gate.depth + 1).padStart(2, "0")}</small><strong>{gate.name}</strong><span>{gate.targets.join(" · ")}</span></div>)}</div></section>
      <div className="split-layout sampling-split">
        <section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Radio size={14} /> FINAL SAMPLING</span><h3>末端采样分布</h3></div></div><CountsChart counts={counts} /></section>
        <section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Activity size={14} /> OBJECTIVE HISTORY</span><h3>VQE 参数目标值</h3></div></div><ParameterChart history={history} /></section>
      </div>
      <section className="data-section">
        <div className="subsection-head"><div><span className="section-kicker">QWC EXECUTION EVIDENCE</span><h3>理想与带噪测量组</h3></div><span className="data-chip">{run.quantum.summary.noiseModel === "readout_demo" ? "READOUT NOISE" : "IDEAL QWC"}</span></div>
        <div className="table-wrap"><table className="data-table compact-table"><thead><tr><th>Model</th><th>Group</th><th>Basis</th><th>Shots</th><th>Top count</th></tr></thead><tbody>
          {[
            ...run.quantum.measurement.groups.map((group) => ({ ...group, model: "IDEAL" })),
            ...(run.quantum.measurement.noisyGroups ?? []).map((group) => ({ ...group, model: "READOUT NOISE" })),
          ].map((group) => {
            const top = Object.entries(group.counts).sort((left, right) => right[1] - left[1])[0];
            return <tr key={`${group.model}-${group.index}`}><td>{group.model}</td><td>{group.index + 1}</td><td className="mono">{Object.entries(group.basis).map(([qubit, basis]) => `${basis}(${qubit})`).join(" · ")}</td><td>{group.shots}</td><td className="mono">{top ? `${top[0]} / ${top[1]}` : "N/A"}</td></tr>;
          })}
        </tbody></table></div>
      </section>
    </div>
  );
}

function PeptideQuantumView({ run }: { run: PeptideRunPayload }) {
  return (
    <div className="view-stack biomed-view peptide-quantum-view">
      <div className="experiment-banner"><div className="experiment-mode"><span className="mode-pulse" /><div><small><QuantumText text="QAOA / ONE-HOT QUBO" /></small><strong>DIGITAL</strong></div></div><div className="experiment-telemetry"><span><small>QUBITS</small><strong>{run.quantum.summary.qubits}</strong></span><span><small>SHOTS</small><strong>{run.quantum.summary.shots}</strong></span><span><small>EVALUATIONS</small><strong>{run.quantum.summary.evaluations}</strong></span><span><small>FEASIBLE</small><strong>{run.quantum.summary.feasibleObserved}</strong></span></div></div>
      <section className="data-section circuit-gate-table"><div className="subsection-head"><div><span className="section-kicker"><Atom size={14} /> DIGITAL CIRCUIT</span><h3>实际绑定 QAOA 线路</h3></div><span className="data-chip">DEPTH {run.quantum.circuit.depth}</span></div><div className="gate-sequence">{run.quantum.circuit.gates.map((gate) => <div key={`${gate.depth}-${gate.name}`}><small>{String(gate.depth + 1).padStart(2, "0")}</small><strong>{gate.name}</strong><span>{gate.targets.join(" · ")}</span></div>)}</div></section>
      <div className="split-layout sampling-split"><section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Radio size={14} /> FINAL SAMPLING</span><h3>构象选择态分布</h3></div></div><CountsChart counts={run.quantum.counts} /></section><section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Activity size={14} /> OBJECTIVE HISTORY</span><h3>QAOA 参数目标值</h3></div></div><ParameterChart history={run.quantum.parameterHistory} /></section></div>
    </div>
  );
}

function RNAQuantumView({ run }: { run: RNARunPayload }) {
  return (
    <div className="view-stack biomed-view rna-quantum-view">
      <div className="experiment-banner"><div className="experiment-mode"><span className="mode-pulse" /><div><small><QuantumText text="QAOA / PAIR-SELECTION QUBO" /></small><strong>DIGITAL</strong></div></div><div className="experiment-telemetry"><span><small>QUBITS</small><strong>{run.quantum.summary.qubits}</strong></span><span><small>SHOTS</small><strong>{run.quantum.summary.shots}</strong></span><span><small>EVALUATIONS</small><strong>{run.quantum.summary.evaluations}</strong></span><span><small>FEASIBLE STATES</small><strong>{run.quantum.summary.feasibleObserved}</strong></span></div></div>
      <section className="data-section circuit-gate-table"><div className="subsection-head"><div><span className="section-kicker"><Atom size={14} /> DIGITAL CIRCUIT</span><h3>实际绑定 RNA 配对 QAOA 线路</h3></div><span className="data-chip">DEPTH {run.quantum.circuit.depth}</span></div><div className="gate-sequence">{run.quantum.circuit.gates.map((gate) => <div key={`${gate.depth}-${gate.name}`}><small>{String(gate.depth + 1).padStart(2, "0")}</small><strong>{gate.name}</strong><span>{gate.targets.join(" · ")}</span></div>)}</div></section>
      <div className="split-layout sampling-split"><section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Radio size={14} /> OBSERVATION FREQUENCY</span><h3>有限 shots 观测分布</h3></div></div><CountsChart counts={run.quantum.counts} /><p className="subsection-note rna-count-warning"><CircleAlert size={14} /> Counts 不是热力学概率或碱基配对概率。</p></section><section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Activity size={14} /> OBJECTIVE HISTORY</span><h3>QAOA 参数目标值</h3></div></div><ParameterChart history={run.quantum.parameterHistory} /></section></div>
    </div>
  );
}

function ProteinQuantumView({ run }: { run: ProteinDynamicsRunPayload }) {
  return (
    <div className="view-stack biomed-view protein-quantum-view">
      <div className="experiment-banner"><div className="experiment-mode"><span className="mode-pulse" /><div><small><QuantumText text="QAOA / TIME-SLICE PATH QUBO" /></small><strong>DIGITAL</strong></div></div><div className="experiment-telemetry"><span><small>QUBITS</small><strong>{run.quantum.summary.qubits}</strong></span><span><small>SHOTS</small><strong>{run.quantum.summary.shots}</strong></span><span><small>EVALUATIONS</small><strong>{run.quantum.summary.evaluations}</strong></span><span><small>FEASIBLE PATHS</small><strong>{run.quantum.summary.feasibleObserved}</strong></span></div></div>
      <section className="data-section circuit-gate-table"><div className="subsection-head"><div><span className="section-kicker"><Atom size={14} /> DIGITAL CIRCUIT</span><h3>实际绑定构象路径 QAOA 线路</h3></div><span className="data-chip">DEPTH {run.quantum.circuit.depth}</span></div><div className="gate-sequence">{run.quantum.circuit.gates.map((gate) => <div key={`${gate.depth}-${gate.name}`}><small>{String(gate.depth + 1).padStart(2, "0")}</small><strong>{gate.name}</strong><span>{gate.targets.join(" · ")}</span></div>)}</div></section>
      <div className="split-layout sampling-split"><section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Radio size={14} /> OBSERVATION FREQUENCY</span><h3>有限 shots 路径编码分布</h3></div></div><CountsChart counts={run.quantum.counts} /><p className="subsection-note rna-count-warning"><CircleAlert size={14} /> Counts 不是转移概率、速率或驻留时间。</p></section><section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Activity size={14} /> OBJECTIVE HISTORY</span><h3>QAOA 参数目标值</h3></div></div><ParameterChart history={run.quantum.parameterHistory} /></section></div>
    </div>
  );
}

function DockingQuantumView({ run }: { run: DockingRunPayload }) {
  const quantum = run.quantum;
  const executionBlocks = quantum.blocks.length ? quantum.blocks : ["digital", "measure"];
  return (
    <div className="view-stack biomed-view docking-quantum-view">
      <div className="experiment-banner">
        <div className="experiment-mode"><span className="mode-pulse" /><div><small><QuantumText text="QAOA / D-A-D" /></small><strong>{quantum.mode.toUpperCase()}</strong></div></div>
        <div className="experiment-telemetry">
          <span><small>QUBITS</small><strong>{quantum.summary.qubits}</strong></span>
          <span><small>ANALOG TERMS</small><strong>{quantum.summary.analogTerms}</strong></span>
          <span><small>DIGITAL TERMS</small><strong>{quantum.summary.digitalTerms}</strong></span>
          <span><small>SHOTS</small><strong>{quantum.summary.shots}</strong></span>
        </div>
      </div>
      <section className="data-section">
        <div className="subsection-head"><div><span className="section-kicker">EXECUTION BLOCKS</span><h3>{quantum.mode === "hybrid" ? "实际 D-A-D block 时间线" : "Digital QAOA 对照线路"}</h3></div><span className="data-chip">{quantum.topology?.toUpperCase() ?? "DIGITAL"}</span></div>
        <div className="dad-timeline">
          {executionBlocks.map((block, index) => <div key={`${block}-${index}`} data-kind={block}><small>{String(index + 1).padStart(2, "0")}</small><strong>{block.toUpperCase()}</strong><span>{block === "analog" ? "Rydberg interaction" : block === "measure" ? "computational basis" : "gate evolution"}</span></div>)}
        </div>
      </section>
      <div className="split-layout quantum-pair-react">
        <section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Atom size={14} /> NEUTRAL-ATOM LAYOUT</span><h3>原子布局与选择态</h3></div></div><AtomChart atoms={quantum.atoms} /></section>
        <section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Activity size={14} /> CONTROL WAVEFORMS</span><h3>Analog 控制波形</h3></div></div><WaveformChart waveforms={quantum.waveforms} /></section>
      </div>
      <div className="split-layout sampling-split">
        <section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Radio size={14} /> FINAL SAMPLING</span><h3>量子观测分布</h3></div></div><CountsChart counts={quantum.counts} /></section>
        <section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Activity size={14} /> OBJECTIVE HISTORY</span><h3>QAOA 参数目标值</h3></div></div><ParameterChart history={quantum.parameterHistory} /></section>
      </div>
      <section className="data-section">
        <div className="subsection-head"><div><span className="section-kicker">TERM MAPPING</span><h3>逻辑项的 Analog / Digital 分配</h3></div><span className="data-chip">{quantum.termMapping.length} TERMS</span></div>
        <div className="table-wrap"><table className="data-table compact-table"><thead><tr><th>Operator</th><th>Targets</th><th>Logical</th><th>Analog</th><th>Digital</th><th>Implementation</th></tr></thead><tbody>{quantum.termMapping.map((term) => <tr key={term.termId}><td>{term.operator}</td><td className="mono">{term.targets.join(" · ")}</td><td>{term.logical.toFixed(5)}</td><td>{term.analog.toFixed(5)}</td><td>{term.digital.toFixed(5)}</td><td>{term.implementation}</td></tr>)}</tbody></table></div>
      </section>
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
  const rows = run
    ? isDockingRun(run)
      ? [
          ["Manifest", run.audit.manifestHash],
          ["Domain Input", run.audit.domainInputHash],
          ["Problem", run.audit.problemHash],
          ["Analysis", run.audit.analysisHash],
          ["Compile", run.audit.compileHash],
          ["Backend", run.audit.backendHash],
          ["Configuration", run.audit.configurationHash],
          ["Execution", run.audit.executionHash],
          ["Result", run.audit.resultHash],
          ["Outcome", run.audit.outcomeHash],
          ["Presentation", run.audit.resultPresentationHash],
          ["Report", run.audit.reportHash],
        ]
      : isPeptideRun(run) || isRnaRun(run) || isProteinRun(run)
        ? [
            ["Manifest", run.audit.manifestHash],
            ["Domain Input", run.audit.domainInputHash],
            ["Problem", run.audit.problemHash],
            ["Hamiltonian", run.audit.hamiltonianHash],
            ["Analysis", run.audit.analysisHash],
            ["Ansatz", run.audit.ansatzHash],
            ["Compile", run.audit.compileHash],
            ["Backend", run.audit.backendHash],
            ["Configuration", run.audit.configurationHash],
            ["Execution", run.audit.executionHash],
            ["Result", run.audit.resultHash],
            ["Outcome", run.audit.outcomeHash],
            ["Report", run.audit.reportHash],
          ]
        : [
          ["Manifest", run.audit.manifestHash],
          ["Source Input", run.audit.sourceInputHash],
          ["Domain Input", run.audit.domainInputHash],
          ["Hamiltonian", run.audit.hamiltonianHash],
          ["Analysis", run.audit.analysisHash],
          ["Ansatz", run.audit.ansatzHash],
          ["Backend", run.audit.backendHash],
          ["Noise Model", run.audit.noiseModelHash],
          ["Measurement", run.audit.measurementPlanHash],
          ["Configuration", run.audit.configurationHash],
          ["Execution", run.audit.executionHash],
          ["Result", run.audit.resultHash],
          ["Outcome", run.audit.outcomeHash],
          ["Report", run.audit.reportHash],
        ]
    : [
        ["Manifest", analysis.dataset.manifestHash],
        ["Problem", analysis.problem.hash],
        ["Analysis", analysis.analysisHash ?? "not-executed"],
      ];
  const publicAudit = run
    ? Object.fromEntries(
        Object.entries(run.audit).filter(([key]) => ![
          "backend",
          "hardwareExecution",
          "cloudExecution",
          "networkAccessed",
          "reportPath",
          "optimalityClaim",
          "claimBoundary",
        ].includes(key)),
      )
    : {
        dataset: {
          id: `${analysis.caseId}.versioned-dataset`,
          version: analysis.dataset.version,
          manifestHash: analysis.dataset.manifestHash,
        },
        analysisHash: analysis.analysisHash,
        execution: "not_run",
      };
  return (
    <div className="view-stack biomed-view audit-view">
      <div className="audit-grid">
        <section className="audit-section"><span className="section-kicker">DATASET CONTEXT</span><dl><div><dt>Dataset</dt><dd>{analysis.caseId.toUpperCase()} DATASET</dd></div><div><dt>Version</dt><dd>{analysis.dataset.version}</dd></div><div><dt>Source</dt><dd>CURATED VERSIONED INPUT</dd></div><div><dt>License</dt><dd>{analysis.dataset.license}</dd></div></dl></section>
        <section className="audit-section"><span className="section-kicker">SOURCE HASH CHAIN</span><div className="hash-chain">{rows.filter((row) => typeof row[1] === "string" && row[1].length > 0).map(([label, value], index) => <div key={label}><span>{String(index + 1).padStart(2, "0")}</span><small>{label}</small><code>{value}</code></div>)}</div></section>
      </div>
      <section className="audit-json-section"><div className="subsection-head"><div><span className="section-kicker"><FileJson size={14} /> MACHINE EVIDENCE</span><h3>结构化审计载荷</h3></div></div><pre>{JSON.stringify(publicAudit, null, 2)}</pre></section>
    </div>
  );
}
