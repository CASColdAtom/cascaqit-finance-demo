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

function InterpretationBoundary({ analysis }: { analysis: BiomedicineAnalysisPayload }) {
  return (
    <div className="interpretation-boundary">
      <div><small>SUPPORTED INTERPRETATION</small><BoundaryList values={analysis.dataset.allowedClaims ?? []} allowed /></div>
      <div><small>LIMITATIONS</small><BoundaryList values={analysis.dataset.limitations} /></div>
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
        <InterpretationBoundary analysis={analysis} />
      </div>
    );
  }
  if (isDockingRun(run)) return <DockingResultView analysis={analysis} run={run} />;
  if (isActiveCenterRun(run)) return <ActiveCenterResultView analysis={analysis} run={run} />;
  if (isPeptideRun(run)) return <PeptideResultView analysis={analysis} run={run} />;
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
      <div className="biomed-metric-band">
        <div data-pass={candidate.feasible}><small>QUANTUM CANDIDATE</small><strong>{candidate.conformationId ?? "NONE"}</strong><span>{candidate.feasible ? "observed feasible" : "no classic fallback"}</span></div>
        <div><small>COARSE ENERGY</small><strong>{candidate.energy?.toFixed(3) ?? "N/A"}</strong><span>dimensionless</span></div>
        <div><small>GROUND DEGENERACY</small><strong>{run.domain.classicGroundConformations.length}</strong><span>{run.domain.classicGroundConformations.map((item) => item.id).join(" / ")}</span></div>
        <div data-pass={run.domain.energyGapFromGround === 0}><small>GAP FROM GROUND</small><strong>{run.domain.energyGapFromGround?.toFixed(3) ?? "N/A"}</strong><span>observed vs enumeration</span></div>
      </div>
      <section className="data-section">
        <div className="subsection-head"><div><span className="section-kicker"><Activity size={14} /> COMPLETE CLASSIC LANDSCAPE</span><h3>量子候选与完整离散能景</h3></div><span className="data-chip source-quantum">{run.domain.observedFeasibleCount} OBSERVED</span></div>
        <div className="peptide-landscape-list">
          {run.domain.fullLandscape.map((item) => (
            <div key={item.id} data-selected={item.id === candidate.conformationId} data-ground={item.energy === minimum}>
              <strong>{item.id}</strong><i><b style={{ width: `${Math.max(3, ((maximum - item.energy) / span) * 100)}%` }} /></i><span>{item.energy.toFixed(3)}</span><small>{item.contactCount} contacts</small>
            </div>
          ))}
        </div>
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
          ...(run.comparison.vqeNoisySampledEnergy === null ? [] : [{ source: "读出噪声 QWC", candidate: "readout-demo groups", value: run.comparison.vqeNoisySampledEnergy.toFixed(6), evidence: `标准误 ${run.domain.noisySampledStandardError?.toFixed(4) ?? "N/A"}` }]),
          { source: "经典精确对角化", candidate: run.comparison.referenceMethod, value: run.comparison.exactGroundEnergy.toFixed(6), evidence: `绝对误差 ${run.domain.absoluteErrorHartree.toFixed(6)} Ha` },
        ]} />
      </section>
      <InterpretationBoundary analysis={analysis} />
    </div>
  );
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
        <div className="subsection-head"><div><span className="section-kicker">QWC EXECUTION EVIDENCE</span><h3>理想与带噪测量组</h3></div><span className="data-chip">{(run.quantum.summary.noiseModel ?? "ideal").toUpperCase()}</span></div>
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
      : isPeptideRun(run)
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
  return (
    <div className="view-stack biomed-view audit-view">
      <div className="audit-grid">
        <section className="audit-section"><span className="section-kicker">DATASET CONTEXT</span><dl><div><dt>Dataset</dt><dd>{analysis.dataset.id}</dd></div><div><dt>Version</dt><dd>{analysis.dataset.version}</dd></div><div><dt>Source</dt><dd>{analysis.dataset.sourceKind}</dd></div><div><dt>License</dt><dd>{analysis.dataset.license}</dd></div></dl></section>
        <section className="audit-section"><span className="section-kicker">SOURCE HASH CHAIN</span><div className="hash-chain">{rows.filter((row) => typeof row[1] === "string" && row[1].length > 0).map(([label, value], index) => <div key={label}><span>{String(index + 1).padStart(2, "0")}</span><small>{label}</small><code>{value}</code></div>)}</div></section>
      </div>
      <section className="audit-json-section"><div className="subsection-head"><div><span className="section-kicker"><FileJson size={14} /> MACHINE EVIDENCE</span><h3>结构化审计载荷</h3></div></div><pre>{JSON.stringify(run?.audit ?? { dataset: analysis.dataset, analysisHash: analysis.analysisHash, execution: "not_run" }, null, 2)}</pre></section>
    </div>
  );
}
