import {
  Activity,
  Atom,
  Binary,
  Check,
  CircleOff,
  Cpu,
  FileJson,
  Gauge,
  GitBranch,
  Network,
  Radio,
  ShieldCheck,
  X,
} from "lucide-react";
import type { AnalysisPayload, BusinessPayload, Mode, RunPayload } from "../types";
import { compactId, MODE_LABELS, numericResource, termShares } from "../utils";
import { useI18n } from "../i18n";
import { CircuitDiagram } from "./CircuitDiagram";
import {
  AtomChart,
  BusinessChart,
  CountsChart,
  MatrixHeatmap,
  ParameterChart,
  ScenarioChart,
  WaveformChart,
} from "./charts/Charts";

function EmptyRun({ mode }: { mode: Mode }) {
  const { t } = useI18n();
  return (
    <div className="empty-run">
      <Radio size={28} strokeWidth={1.4} aria-hidden="true" />
      <strong>{MODE_LABELS[mode]} READY</strong>
      <span>{t("waitingResult")}</span>
    </div>
  );
}

function MetricBand({ business }: { business: BusinessPayload }) {
  const { tx } = useI18n();
  return (
    <div className="metric-band-react">
      {business.metrics.map((metric, index) => (
        <div className="metric-cell" key={metric.label}>
          <span>{tx(metric.label)}</span>
          <strong>{tx(metric.value)}</strong>
          <small>
            {String(index + 1).padStart(2, "0")} / {tx(metric.context)}
          </small>
        </div>
      ))}
    </div>
  );
}

export function BusinessView({ run, mode }: { run: RunPayload | null; mode: Mode }) {
  const { t, tx } = useI18n();
  if (!run) return <EmptyRun mode={mode} />;
  return (
    <div className="view-stack">
      <MetricBand business={run.business} />
      <div className="split-layout business-split">
        <section className="data-section chart-section">
          <div className="subsection-head">
            <div>
              <span className="section-kicker"><Activity size={14} aria-hidden="true" /> BUSINESS SPACE</span>
              <h3>{tx(run.business.chart.title)}</h3>
            </div>
            <span className="data-chip">{run.business.chart.points.length} POINTS</span>
          </div>
          <BusinessChart business={run.business} />
        </section>
        <section className="data-section selection-section">
          <div className="subsection-head">
            <div>
              <span className="section-kicker"><ShieldCheck size={14} aria-hidden="true" /> CONSTRAINT CHECK</span>
              <h3>{t("currentSolution")}</h3>
            </div>
            <span className={`data-chip source-${run.business.displayedSource}`}>{run.business.displayedSource}</span>
          </div>
          <div className="selection-list">
            {run.business.selection.map((item) => (
              <div className="selection-row" data-selected={item.selected} key={item.id}>
                <span className="selection-state">{item.selected ? <Check size={14} /> : <CircleOff size={14} />}</span>
                <span><strong>{tx(item.label)}</strong><small>{tx(item.group)} · {tx(item.detail)}</small></span>
                <span className="selection-reason">{tx(item.reason)}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
      <section className="constraint-strip" aria-label={t("businessConstraintReview")}>
        {run.business.checks.map((check) => (
          <div data-pass={check.passed} key={check.name}>
            {check.passed ? <Check size={15} aria-hidden="true" /> : <X size={15} aria-hidden="true" />}
            <span>{tx(check.name)}</span>
            <strong>{tx(check.actual)}</strong>
            <small>{tx(check.expected)}</small>
          </div>
        ))}
      </section>
    </div>
  );
}

export function ScenarioView({ analysis, run }: { analysis: AnalysisPayload; run: RunPayload | null }) {
  const { t, tx } = useI18n();
  const selectedIds =
    run?.business.selection
      .filter((item) => item.selected)
      .map((item) => item.id) ?? [];
  const visual = analysis.scenarioVisual;
  const structureLabels = {
    "portfolio-correlation": tx("相关性格点"),
    "settlement-network": tx("交易节点"),
    "fraud-entity-network": tx("告警 / 实体节点"),
    "collateral-flow": tx("分配流节点"),
    "liquidity-timeline": tx("日内动作"),
    "credit-capital-map": tx("授信候选"),
    "derivatives-pnl-surface": tx("压力情景"),
  } as const;
  const structureSize =
    visual.nodes.length || visual.points.length || visual.matrix.cells.length;
  return (
    <div className="view-stack">
      <div className="scenario-analysis-rail" aria-label={t("scenarioSituation")}>
        <div><span>BUSINESS OBJECTS</span><strong>{analysis.inputRows.length}</strong><small>{t("inputRecords")}</small></div>
        <div><span>STRUCTURE</span><strong>{structureSize}</strong><small>{structureLabels[visual.kind]}</small></div>
        <div><span>PROBLEM VARIABLES</span><strong>{analysis.problem.variables.length}</strong><small>{analysis.problem.type.toUpperCase()}</small></div>
        <div><span>RECOMMENDED PATH</span><strong>{MODE_LABELS[analysis.decision.recommendedMode]}</strong><small>{analysis.decision.modes.find((item) => item.mode === analysis.decision.recommendedMode)?.algorithm.toUpperCase()}</small></div>
      </div>
      <div className="split-layout scenario-split">
        <section className="data-section">
          <div className="subsection-head">
            <div>
              <span className="section-kicker"><Binary size={14} aria-hidden="true" /> SYNTHETIC INPUT</span>
              <h3>{t("scenarioInputSlice")}</h3>
            </div>
            <span className="data-chip">{analysis.inputRows.length} RECORDS</span>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>{t("businessObject")}</th><th>{t("group")}</th><th>{t("primaryMetric")}</th><th>{t("secondaryMetric")}</th><th>{t("description")}</th></tr></thead>
              <tbody>
                {analysis.inputRows.map((row) => (
                  <tr key={row.id}><td><strong>{tx(row.label)}</strong></td><td>{tx(row.group)}</td><td>{tx(row.primary)}</td><td>{tx(row.secondary)}</td><td>{tx(row.detail)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <section className="data-section chart-section">
          <div className="subsection-head">
            <div>
              <span className="section-kicker"><Network size={14} aria-hidden="true" /> STRUCTURE</span>
              <h3>{tx(visual.title)}</h3>
              <p className="subsection-note">{tx(visual.subtitle)}</p>
            </div>
            <span className="data-chip">{visual.kind.replaceAll("-", " ")}</span>
          </div>
          <ScenarioChart visual={visual} selectedIds={selectedIds} />
        </section>
      </div>
    </div>
  );
}

export function MappingView({ analysis, run }: { analysis: AnalysisPayload; run: RunPayload | null }) {
  const { t, tx } = useI18n();
  const resource = analysis.resource;
  const ledger = analysis.problem.coefficientLedger;
  return (
    <div className="view-stack">
      <div className="mapping-readout">
        <div><span>PROBLEM</span><strong>{analysis.problem.id}</strong><small>{analysis.problem.type.toUpperCase()}</small></div>
        <div><span>LOGICAL VARIABLES</span><strong>{numericResource(resource, "logical_variables")}</strong><small>{numericResource(resource, "state_vector_dimension").toLocaleString()} {t("stateDimension")}</small></div>
        <div><span>LOGICAL TERMS</span><strong>{numericResource(resource, "logical_terms")}</strong><small>{analysis.problem.termGroups.length} {t("businessGroups")}</small></div>
        <div><span>PROBLEM HASH</span><strong className="mono">{compactId(analysis.problem.hash, 18)}</strong><small>{t("canonicalIdentity")}</small></div>
      </div>
      <section className="mode-decision-grid" aria-label={t("modeDecision")}>
        {analysis.decision.modes.map((row) => {
          const shares = termShares(row.analogTermCount, row.digitalTermCount);
          return (
            <div className={`mode-decision mode-${row.mode}`} data-status={row.status} key={row.mode}>
              <div className="mode-decision-head"><span>{MODE_LABELS[row.mode]}</span><strong>{row.status === "recommended" ? t("recommended") : row.status === "comparable" ? t("comparable") : t("unsuitable")}</strong></div>
              <div className="mode-term-track" aria-label={`Analog ${shares.analog.toFixed(1)}%，Digital ${shares.digital.toFixed(1)}%`}><i style={{ width: `${shares.analog}%` }} /><i style={{ width: `${shares.digital}%` }} /></div>
              <div className="mode-numbers"><span>ANALOG <strong>{row.analogTermCount}</strong></span><span>DIGITAL <strong>{row.digitalTermCount}</strong></span></div>
              {row.mode !== "digital" ? (
                <div className="mode-evidence">
                  <span>{t("coreCoverage")} <strong>{row.coveredContributionCount}/{row.declaredContributionCount}</strong></span>
                  <span>{t("geometryEvidence")} <strong>{row.geometryStatus === "verified" ? t("verified") : tx(row.geometryStatus)}</strong></span>
                  <span>{t("missingEvidence")} <strong>{row.missingContributionIds.length}</strong></span>
                  <span>{t("unexpectedEvidence")} <strong>{row.unexpectedAnalogTermIds.length + row.unexpectedInteractionPairs.length}</strong></span>
                  <small>{tx(row.geometrySource ?? "not_applicable")} · {tx(row.layoutPolicy)}</small>
                </div>
              ) : null}
              <p>{row.diagnosticCodes.length ? row.diagnosticCodes.join(" · ") : tx(row.reason)}</p>
            </div>
          );
        })}
      </section>
      <section className="data-section chart-section">
        <div className="subsection-head"><div><span className="section-kicker"><Cpu size={14} /> HAMILTONIAN</span><h3>{t("graphMatrix")}</h3></div></div>
        <MatrixHeatmap variables={analysis.problem.matrix.variables} cells={analysis.problem.matrix.cells} />
      </section>
      <section className="data-section">
        <div className="subsection-head">
          <div>
            <span className="section-kicker"><GitBranch size={14} /> PROVENANCE</span>
            <h3>{ledger.applicability === "qubo" ? t("coefficientLedger") : t("termAssignment")}</h3>
            {ledger.applicability === "qubo" ? <p className="subsection-note">{run ? t("ledgerExecutedNote") : t("ledgerAnalysisNote")}</p> : null}
          </div>
          {ledger.applicability === "qubo" ? <span className="data-chip">{ledger.contributionCount} {t("contributions")} · {ledger.balanced && ledger.hamiltonianBalanced ? t("conserved") : t("notConserved")}</span> : null}
        </div>
        {ledger.applicability === "qubo" ? (
          <div className="table-wrap coefficient-ledger-wrap">
            <table className="data-table compact-table coefficient-ledger-table">
              <thead><tr><th>{t("businessRule")}</th><th>{t("contributionId")}</th><th>{t("sourceCoefficient")}</th><th>{t("canonicalTerm")}</th><th>{t("canonicalCoefficient")}</th><th>{t("hamiltonianImplementation")}</th><th>{t("conservation")}</th></tr></thead>
              <tbody>
                {ledger.rows.map((row) => (
                  <tr key={row.contributionId}>
                    <td className="ledger-rule"><strong>{tx(row.groupLabel)}</strong><span>{tx(row.sourceRuleLabel)}</span></td>
                    <td className="mono ledger-id">{row.contributionId}</td>
                    <td className="mono">{row.contributionCoefficient.toPrecision(5)}</td>
                    <td><strong className="mono">{row.canonicalTermId}</strong><small className="ledger-targets">{row.targets.map((target) => compactId(tx(target), 18)).join(" · ") || t("constantOffset")}</small></td>
                    <td className="mono">{row.canonicalCoefficient.toPrecision(5)}</td>
                    <td className="ledger-hamiltonian">
                      {row.hamiltonianTerms.length ? row.hamiltonianTerms.map((term) => (
                        <div key={term.termId}>
                          <strong className="mono">{term.operator.toUpperCase()} · {term.targets.map((target) => compactId(tx(target), 14)).join(" · ")}</strong>
                          <small className="mono">Δ {term.contributionEffect.toPrecision(4)} · LΣ {term.logical.toPrecision(4)} · A {term.analog === null ? "--" : term.analog.toPrecision(4)} · D {term.digital === null ? "--" : term.digital.toPrecision(4)} · {tx(term.implementationLabel)}</small>
                        </div>
                      )) : <span className="ledger-offset">{t("noPhysicalTerm")}</span>}
                    </td>
                    <td><span className={row.conserved ? "ledger-conserved" : "ledger-broken"}>{row.conserved ? <Check size={13} aria-hidden="true" /> : <X size={13} aria-hidden="true" />}{row.conserved ? t("conserved") : t("notConserved")}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="term-groups">{analysis.problem.termGroups.map((group) => <div key={group.group_id}><span>{tx(group.kind)}</span><strong>{tx(group.label)}</strong><small>{group.variables.length} {t("variables")} · {group.pairs.length} {t("pairs")}</small></div>)}</div>
        )}
      </section>
    </div>
  );
}

function ExperimentHeader({ run }: { run: RunPayload }) {
  return (
    <div className="experiment-header">
      <div className="experiment-mode"><span className="mode-pulse" /><div><small>{run.quantum.algorithm.toUpperCase()} / {run.quantum.topology?.toUpperCase() ?? "NATIVE"}</small><strong>{MODE_LABELS[run.quantum.mode]}</strong></div></div>
      <div className="experiment-telemetry"><span><small>QUBITS / SITES</small><strong>{run.quantum.summary.qubits}</strong></span><span><small>ANALOG TERMS</small><strong>{run.quantum.summary.analogTerms}</strong></span><span><small>DIGITAL TERMS</small><strong>{run.quantum.summary.digitalTerms}</strong></span><span><small>SHOTS</small><strong>{run.quantum.summary.shots}</strong></span></div>
    </div>
  );
}

export function QuantumView({ run, mode }: { run: RunPayload | null; mode: Mode }) {
  const { t } = useI18n();
  if (!run) return <EmptyRun mode={mode} />;
  const hasAnalog = run.quantum.mode !== "digital";
  const hasCircuit = run.quantum.mode !== "analog";
  return (
    <div className="view-stack quantum-view">
      <ExperimentHeader run={run} />
      {run.quantum.blocks.length ? <div className="dad-timeline" aria-label={t("dadTimeline")}>{run.quantum.blocks.map((block, index) => <div key={`${block}-${index}`} data-kind={block}><small>{String(index + 1).padStart(2, "0")}</small><strong>{block.toUpperCase()}</strong></div>)}</div> : null}
      {hasAnalog ? (
        <div className="split-layout quantum-pair-react">
          <section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Atom size={14} /> ATOM REGISTER</span><h3>{t("atomRegister")}</h3></div><span className="data-chip">{run.quantum.atoms.length} SITES</span></div><AtomChart atoms={run.quantum.atoms} /></section>
          <section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Activity size={14} /> AHS CONTROL</span><h3>{t("controlWaveforms")}</h3><p className="subsection-note">{t("waveformNote")}</p></div></div><WaveformChart waveforms={run.quantum.waveforms} /></section>
        </div>
      ) : null}
      {hasCircuit ? <CircuitDiagram quantum={run.quantum} /> : null}
      <div className="split-layout sampling-split">
        <section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Radio size={14} /> FINAL SAMPLING</span><h3>{t("finalSampling")}</h3></div></div><CountsChart counts={run.quantum.counts} /></section>
        <section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Gauge size={14} /> PARAMETER SCAN</span><h3>{t("parameterObjective")}</h3></div></div><ParameterChart history={run.quantum.parameterHistory} /></section>
      </div>
    </div>
  );
}

export function AuditView({ run, mode }: { run: RunPayload | null; mode: Mode }) {
  const { t } = useI18n();
  if (!run) return <EmptyRun mode={mode} />;
  const audit = run.audit;
  const rows = [
    ["Execution", audit.executionHash], ["Compile", audit.compileHash], ["Analysis", audit.analysisHash], ["Problem", audit.problemHash],
  ];
  return (
    <div className="view-stack audit-view">
      <div className="audit-boundary"><ShieldCheck size={22} /><div><strong>{t("localSimulationEvidence")}</strong><span>{t("executionBoundary")}</span></div><span className="verified-mark">{t("verified")}</span></div>
      <div className="audit-grid">
        <section className="audit-section"><span className="section-kicker">EXECUTION CONTEXT</span><dl><div><dt>Mode</dt><dd>{audit.mode.toUpperCase()}</dd></div><div><dt>Backend</dt><dd>{audit.backend}</dd></div><div><dt>Target</dt><dd>{audit.targetId}</dd></div><div><dt>Seed</dt><dd>{audit.seed}</dd></div><div><dt>Shots</dt><dd>{audit.shots}</dd></div><div><dt>Wall time</dt><dd>{audit.wallTimeSeconds.toFixed(3)}s</dd></div></dl></section>
        <section className="audit-section"><span className="section-kicker">SOURCE HASH CHAIN</span><div className="hash-chain">{rows.map(([label, value], index) => <div key={label}><span>{String(index + 1).padStart(2, "0")}</span><small>{label}</small><code>{value}</code></div>)}</div></section>
      </div>
      <section className="audit-json-section"><div className="subsection-head"><div><span className="section-kicker"><FileJson size={14} /> MACHINE EVIDENCE</span><h3>{t("structuredAudit")}</h3></div></div><pre>{JSON.stringify(audit, null, 2)}</pre></section>
    </div>
  );
}
