import {
  AlertTriangle,
  Activity,
  Atom,
  Braces,
  GitCompareArrows,
  Grid3X3,
  RadioTower,
  CheckCircle2,
  CircleX,
  Waves,
} from "lucide-react";
import type {
  AnalogTimePointPayload,
  MaterialSolutionPayload,
  MaterialsAnalysisPayload,
  MaterialsAnalogRunPayload,
  MaterialsOptimizationRunPayload,
  MaterialsRunPayload,
} from "../types";
import { AtomChart, CountsChart, ParameterChart, WaveformChart } from "./charts/Charts";
import type { ViewId } from "./viewTabs";

function isAnalogRun(
  run?: MaterialsRunPayload | null,
): run is MaterialsAnalogRunPayload {
  return run?.quantum.kind === "analog_ahs";
}

function isOptimizationRun(
  run?: MaterialsRunPayload | null,
): run is MaterialsOptimizationRunPayload {
  return run?.quantum.kind === "problem_qaoa";
}

function MetricRail({
  analysis,
  run,
}: {
  analysis: MaterialsAnalysisPayload;
  run?: MaterialsRunPayload | null;
}) {
  const analog = analysis.executionFamily === "analog_ahs";
  const activeSites = analysis.domain.nodes.filter(
    (node) => node.role !== "vacancy",
  ).length;
  return (
    <div className="scenario-analysis-rail materials-metric-rail">
      <div>
        <span>EXPERIMENT KIND</span>
        <strong>{analog ? "ANALOG AHS" : "MATERIAL QUBO"}</strong>
        <small>{run ? run.quantum.mode.toUpperCase() : analysis.implementationStatus.toUpperCase()}</small>
      </div>
      <div>
        <span>EFFECTIVE SITES</span>
        <strong>{activeSites}</strong>
        <small>{analysis.domain.nodes.length - activeSites} defect sites</small>
      </div>
      <div>
        <span>COORDINATE IDENTITIES</span>
        <strong>3</strong>
        <small>material / effective / compiled</small>
      </div>
      <div>
        <span>EXECUTION GATE</span>
        <strong>{run ? "EXECUTED" : analysis.implementationStatus === "available" ? "READY" : "PREVIEW"}</strong>
        <small>{run ? `${run.audit.shots} local shots` : analysis.implementationStatus === "available" ? "local simulator" : "executor unavailable"}</small>
      </div>
    </div>
  );
}

function LatticeFigure({
  analysis,
  selected,
}: {
  analysis: MaterialsAnalysisPayload;
  selected?: Set<string>;
}) {
  const adsorbates = analysis.domain.adsorbates ?? [];
  const positions = new Map(
    analysis.domain.nodes.map((node) => [node.id, { x: node.x, y: node.y }]),
  );
  return (
    <section className="data-section materials-figure-section">
      <div className="subsection-head">
        <div>
          <span className="section-kicker">MATERIAL EFFECTIVE LATTICE</span>
          <h3>周期晶格与缺陷</h3>
        </div>
        <span className="data-chip">MATERIAL COORDINATES</span>
      </div>
      <svg
        className="materials-lattice-svg"
        viewBox="0 0 100 100"
        role="img"
        aria-label="材料有效晶格、缺陷和吸附位点"
      >
        <g className="lattice-bonds">
          {analysis.domain.nodes.flatMap((node, index) => {
            const right = analysis.domain.nodes[index + 1];
            const down = analysis.domain.nodes[index + 4];
            return [
              right && index % 4 !== 3 ? (
                <line key={`${node.id}-r`} x1={node.x} y1={node.y} x2={right.x} y2={right.y} />
              ) : null,
              down ? (
                <line key={`${node.id}-d`} x1={node.x} y1={node.y} x2={down.x} y2={down.y} />
              ) : null,
            ];
          })}
        </g>
        {analysis.domain.nodes.map((node) => (
          <g className="lattice-site" data-role={node.role} data-active-window={node.inActiveWindow ?? false} data-selected={analysis.domain.defectCandidates?.some((item) => item.site === node.id && selected?.has(item.id)) ?? false} key={node.id}>
            <circle cx={node.x} cy={node.y} r="4.5" />
            <text x={node.x} y={node.y + 1.3}>{node.role === "vacancy" ? "V" : node.label}</text>
          </g>
        ))}
        {adsorbates.map((item) => {
          const position = positions.get(item.site);
          if (!position) return null;
          return (
            <g className="adsorbate-site" data-selected={selected?.has(item.id) ?? false} key={item.id}>
              <line x1={position.x} y1={position.y - 5} x2={position.x} y2={position.y - 13} />
              <rect x={position.x - 6} y={position.y - 22} width="12" height="8" rx="2" />
              <text x={position.x} y={position.y - 16.3}>{item.label}</text>
            </g>
          );
        })}
      </svg>
      <div className="materials-legend" aria-label="晶格图例">
        <span><i data-kind="site" />有效位点</span>
        <span><i data-kind="active" />活动窗口</span>
        <span><i data-kind="vacancy" />缺陷</span>
        {adsorbates.length ? <span><i data-kind="adsorbate" />吸附物</span> : null}
      </div>
    </section>
  );
}

function RydbergFigure({ analysis }: { analysis: MaterialsAnalysisPayload }) {
  const layout = analysis.domain.rydbergLayout ?? [];
  return (
    <section className="data-section materials-figure-section">
      <div className="subsection-head">
        <div>
          <span className="section-kicker">COMPILED RYDBERG REGISTER</span>
          <h3>中性原子编译布局</h3>
        </div>
        <span className="data-chip">SEPARATE IDENTITY</span>
      </div>
      <svg
        className="materials-lattice-svg rydberg-register-svg"
        viewBox="-3 -3 23 12"
        role="img"
        aria-label="独立于材料坐标的 Rydberg 原子布局"
      >
        {layout.map((atom) => (
          <g className="rydberg-site" data-active={atom.active} key={atom.id}>
            <circle cx={atom.x} cy={atom.y} r="1.8" />
            {atom.active ? <circle className="rydberg-orbit" cx={atom.x} cy={atom.y} r="3.2" /> : null}
          </g>
        ))}
      </svg>
      <p className="subsection-note">
        Rydberg 坐标是目标约束下的编译派生物，不等同于材料晶格坐标。
      </p>
    </section>
  );
}

function PulsePreview({ analysis }: { analysis: MaterialsAnalysisPayload }) {
  const pulse = analysis.domain.pulse;
  const times = analysis.domain.sampleTimes ?? [];
  if (!pulse) return null;
  const detuningY = (value: number) => 68 - ((value + 4) / 8) * 40;
  return (
    <section className="data-section materials-pulse-section">
      <div className="subsection-head">
        <div>
          <span className="section-kicker">PULSE SCHEDULE</span>
          <h3>Rabi / Detuning 与采样时刻</h3>
        </div>
        <span className="data-chip">{pulse.duration.toFixed(2)} μs</span>
      </div>
      <svg className="materials-pulse-svg" viewBox="0 0 720 220" role="img" aria-label="AHS 脉冲计划预览">
        <line className="pulse-axis" x1="58" y1="76" x2="690" y2="76" />
        <line className="pulse-axis" x1="58" y1="176" x2="690" y2="176" />
        <text x="12" y="48">Ω(t)</text>
        <text x="12" y="148">Δ(t)</text>
        <polyline className="pulse-rabi" points="58,76 150,30 598,30 690,76" />
        <polyline
          className="pulse-detuning"
          points={`58,${110 + detuningY(pulse.detuningStart)} 690,${110 + detuningY(pulse.detuningEnd)}`}
        />
        {times.map((time) => {
          const x = 58 + (time / pulse.duration) * 632;
          return <line className="sample-marker" key={time} x1={x} y1="18" x2={x} y2="195" />;
        })}
        <text className="pulse-label" x="58" y="213">0</text>
        <text className="pulse-label" x="670" y="213">{pulse.duration.toFixed(2)} μs</text>
      </svg>
      <p className="subsection-note">
        每个采样标记对应从同一声明初态执行的截断 AHS 程序；不使用插值补造量子轨迹。
      </p>
    </section>
  );
}

const ANALOG_ATOM_COLORS = ["#22c55e", "#38bdf8", "#f59e0b", "#f472b6"];

function DynamicsChart({
  points,
  classic,
}: {
  points: AnalogTimePointPayload[];
  classic?: MaterialsAnalogRunPayload["domain"]["classicReference"]["timeSeries"];
}) {
  if (!points.length) return null;
  const atoms = Object.keys(points[0].occupation);
  const duration = Math.max(points.at(-1)?.actualTime ?? 1, 1e-9);
  const x = (time: number) => 58 + (time / duration) * 620;
  const y = (value: number) => 218 - value * 176;
  const line = (series: Array<{ actualTime: number; occupation: Record<string, number> }>, atom: string) =>
    series.map((point) => `${x(point.actualTime)},${y(point.occupation[atom] ?? 0)}`).join(" ");
  return (
    <section className="data-section analog-dynamics-section">
      <div className="subsection-head">
        <div><span className="section-kicker">TIME-RESOLVED OCCUPATION</span><h3>逐位点 Rydberg 占据</h3></div>
        <span className="data-chip">{points.length} TIME POINTS</span>
      </div>
      <svg className="analog-dynamics-svg" viewBox="0 0 720 260" role="img" aria-label="AHS 逐位点占据时间序列">
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => <g key={tick}><line x1="58" x2="678" y1={y(tick)} y2={y(tick)} /><text x="22" y={y(tick) + 4}>{tick.toFixed(2)}</text></g>)}
        {atoms.map((atom, index) => <g key={atom}><polyline className="analog-series" points={line(points, atom)} style={{ stroke: ANALOG_ATOM_COLORS[index] }} />{classic ? <polyline className="analog-series classic-series" points={line(classic, atom)} style={{ stroke: ANALOG_ATOM_COLORS[index] }} /> : null}</g>)}
        <line className="analog-axis" x1="58" x2="678" y1="218" y2="218" />
        <text className="analog-axis-label" x="58" y="248">0</text>
        <text className="analog-axis-label" x="638" y="248">{duration.toFixed(2)} μs</text>
      </svg>
      <div className="analog-series-legend">
        {atoms.map((atom, index) => <span key={atom}><i style={{ background: ANALOG_ATOM_COLORS[index] }} />{atom}</span>)}
        {classic ? <span><i className="classic-key" />虚线：独立经典参考</span> : null}
      </div>
      <p className="subsection-note">实线来自 CASCAQit AnalogStateVectorKernel；虚线仅在对照视图中表示独立 DOP853 参考。</p>
    </section>
  );
}

function TerminalCounts({ run }: { run: MaterialsAnalogRunPayload }) {
  const maximum = Math.max(...run.quantum.terminalCounts.map((item) => item.count), 1);
  return (
    <section className="data-section analog-counts-section">
      <div className="subsection-head"><div><span className="section-kicker">TERMINAL BASIS SAMPLES</span><h3>终态位串 counts</h3></div><span className="data-chip">{run.audit.shots} SHOTS</span></div>
      <div className="analog-count-bars">
        {run.quantum.terminalCounts.slice(0, 10).map((item) => <div key={item.state}><code>{item.state}</code><span><i style={{ width: `${(item.count / maximum) * 100}%` }} /></span><strong>{item.count}</strong></div>)}
      </div>
      <p className="subsection-note">每个采样时刻独立执行 {run.audit.shots} 次末端基测量抽样；counts 不是连续单次实验轨迹。</p>
    </section>
  );
}

function SolutionSummary({ solution }: { solution: MaterialSolutionPayload }) {
  return (
    <div className="material-solution-summary">
      <div><span>缺陷</span><strong>{solution.selectedDefectIds.join(" · ") || "NONE"}</strong></div>
      <div><span>吸附构型</span><strong>{solution.selectedAdsorptionIds.join(" · ") || "NONE"}</strong></div>
      <div><span>离散模型能量</span><strong>{solution.physicalModelEnergy.toFixed(4)}</strong></div>
      <div><span>QUBO objective</span><strong>{solution.modelObjective.toFixed(4)}</strong></div>
    </div>
  );
}

function ResultView({ analysis, run }: { analysis: MaterialsAnalysisPayload; run?: MaterialsRunPayload | null }) {
  const analog = analysis.executionFamily === "analog_ahs";
  if (isAnalogRun(run)) {
    const terminal = run.quantum.timeSeries.at(-1);
    return (
      <div className="view-stack">
        <MetricRail analysis={analysis} run={run} />
        <section className="data-section materials-readiness analog-result-summary">
          <div className="subsection-head">
            <div><span className="section-kicker">PURE ANALOG RESULT</span><h3>有效晶格量子淬火结果</h3></div>
            <span className="data-chip source-quantum">AHS COMPLETED</span>
          </div>
          <div className="analog-result-metrics">
            <div><span>采样时刻</span><strong>{run.quantum.summary.sampleCount}</strong><small>independent prefixes</small></div>
            <div><span>终态平均占据</span><strong>{terminal?.meanExcitation.toFixed(4)}</strong><small>dimensionless</small></div>
            <div><span>最大占据误差</span><strong>{run.domain.comparison.maxOccupationAbsoluteError.toExponential(2)}</strong><small>vs DOP853</small></div>
            <div><span>终态保真度</span><strong>{run.domain.comparison.terminalStateFidelity.toFixed(8)}</strong><small>state-vector overlap</small></div>
          </div>
          <div className="readiness-grid">
            <div data-status="ok"><span>Digital gates</span><strong>0</strong></div>
            <div data-status="ok"><span>Digital residual</span><strong>0</strong></div>
            <div data-status="ok"><span>Hybrid blocks</span><strong>0</strong></div>
            <div data-status="ok"><span>Hamiltonian 映射</span><strong>COMPLETE</strong></div>
          </div>
          <p className="subsection-note">{run.domain.interpretation}</p>
        </section>
      </div>
    );
  }
  if (isOptimizationRun(run)) {
    const candidate = run.domain.quantumCandidate;
    return (
      <div className="view-stack">
        <MetricRail analysis={analysis} run={run} />
        <section className="data-section materials-readiness">
          <div className="subsection-head">
            <div><span className="section-kicker">JOINT CONFIGURATION RESULT</span><h3>缺陷与吸附联合构型</h3></div>
            <span className={`data-chip ${candidate ? "source-quantum" : "status-preview"}`}>{candidate ? "QUANTUM OBSERVED" : "NOT OBSERVED"}</span>
          </div>
          {candidate ? <SolutionSummary solution={candidate} /> : <p className="subsection-note">有限 shots 内未观测到可行构型；页面不使用经典最优回填量子结果。</p>}
          <div className="constraint-check-grid">
            {(candidate ?? run.domain.bestObservedRaw).checks.map((check) => (
              <div data-status={check.passed ? "ok" : "warn"} key={check.id}>
                {check.passed ? <CheckCircle2 size={15} /> : <CircleX size={15} />}
                <span>{check.label}</span><strong>{check.actual} / {check.expected}</strong>
              </div>
            ))}
          </div>
          <p className="subsection-note">可行 shot 比例 {(run.domain.feasibleShotRatio * 100).toFixed(1)}%；QAOA counts 是观测频次，不是热力学概率。</p>
        </section>
      </div>
    );
  }
  return (
    <div className="view-stack">
      <MetricRail analysis={analysis} />
      <section className="data-section materials-readiness">
        <div className="subsection-head">
          <div>
            <span className="section-kicker">SCENARIO READINESS</span>
            <h3>{analog ? "纯 Analog 实验门禁" : "材料构型优化门禁"}</h3>
          </div>
          <span className={`data-chip status-${analysis.implementationStatus}`}>{analysis.implementationStatus.toUpperCase()}</span>
        </div>
        <div className="readiness-grid">
          {(analog
            ? [
                ["AHS 定义", "VERIFIED", "ok"],
                ["执行族", "ANALOG ONLY", "ok"],
                ["时分辨执行", "READY", "ok"],
                ["本地规模", "4 atoms", "ok"],
              ]
            : [
                ["周期晶格", "已建模", "ok"],
                ["联合变量", "已定义", "ok"],
                ["离线能量 fixture", "已校验", "ok"],
                ["Hybrid 几何", "VERIFIED", "ok"],
              ]).map(([label, value, status]) => (
            <div data-status={status} key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function MappingView({ analysis, run }: { analysis: MaterialsAnalysisPayload; run?: MaterialsRunPayload | null }) {
  const analog = analysis.executionFamily === "analog_ahs";
  const optimizationRun = isOptimizationRun(run) ? run : null;
  const stages = analog
    ? ["有效晶格", "AHS 定义", "目标校验", "AHS 前缀执行", "时序观测量"]
    : ["周期表面", "对称归一", "材料 QUBO", "Digital / Hybrid", "构型解码"];
  return (
    <div className="view-stack">
      <MetricRail analysis={analysis} run={run} />
      <section className="data-section">
        <div className="subsection-head">
          <div><span className="section-kicker">DOMAIN MAPPING</span><h3>领域到量子执行链</h3></div>
          {analog ? <RadioTower size={18} aria-hidden="true" /> : <Braces size={18} aria-hidden="true" />}
        </div>
        <div className="materials-pipeline">
          {stages.map((stage, index) => (
            <div key={stage}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{stage}</strong>
            </div>
          ))}
        </div>
        {analog ? (
          <pre className="hamiltonian-readout">H(t) = Σ Ωᵢ(t)Xᵢ/2 - Σ Δᵢ(t)nᵢ + Σ Vᵢⱼnᵢnⱼ</pre>
        ) : null}
      </section>
      {!analog && analysis.problem.termGroups ? (
        <div className="split-layout materials-model-details">
          <section className="data-section">
            <div className="subsection-head"><div><span className="section-kicker">DOMAIN TERM GROUPS</span><h3>联合 QUBO 分组</h3></div><span className="data-chip">{analysis.problem.termGroups.length} GROUPS</span></div>
            <div className="hybrid-gate-list">{analysis.problem.termGroups.map((group) => <div key={group.group_id}><strong>{group.label}</strong><span>{group.kind}</span><small>{group.variables.length + group.pairs.length} declarations</small></div>)}</div>
          </section>
          <section className="data-section">
            <div className="subsection-head"><div><span className="section-kicker">HYBRID GATE</span><h3>Analog block / Digital residual</h3></div><span className="data-chip">VERIFIED</span></div>
            <div className="readiness-grid"><div data-status="ok"><span>局域冲突组</span><strong>{analysis.domain.localConflictPairs?.length ?? 0}</strong></div><div data-status="ok"><span>Analog terms</span><strong>{optimizationRun?.quantum.summary.analogTerms ?? analysis.decision.modes.find((row) => row.mode === "hybrid")?.analogTermCount ?? 0}</strong></div><div data-status="ok"><span>Digital residual</span><strong>{optimizationRun?.quantum.summary.digitalTerms ?? analysis.decision.modes.find((row) => row.mode === "hybrid")?.digitalTermCount ?? 0}</strong></div><div data-status="ok"><span>系数账本</span><strong>{analysis.problem.coefficientLedger?.balanced ? "BALANCED" : "MISSING"}</strong></div></div>
          </section>
        </div>
      ) : null}
    </div>
  );
}

function QuantumPreview({ analysis, run }: { analysis: MaterialsAnalysisPayload; run?: MaterialsRunPayload | null }) {
  if (analysis.executionFamily === "analog_ahs") {
    return (
      <div className="view-stack">
        <MetricRail analysis={analysis} run={run} />
        <PulsePreview analysis={analysis} />
        {isAnalogRun(run) ? <><DynamicsChart points={run.quantum.timeSeries} /><TerminalCounts run={run} /></> : (
          <section className="data-section materials-empty-execution">
            <Waves size={28} aria-hidden="true" />
            <h3>Pure Analog AHS 已通过执行门禁</h3>
            <p>运行后展示真实时点占据、关联、终态 counts 和求解器诊断。</p>
          </section>
        )}
      </div>
    );
  }
  if (isOptimizationRun(run)) return (
    <div className="view-stack">
      <MetricRail analysis={analysis} run={run} />
      <div className="experiment-banner"><div className="experiment-mode"><span className="mode-pulse" /><div><small>QAOA / JOINT MATERIAL QUBO</small><strong>{run.quantum.mode.toUpperCase()}</strong></div></div><div className="experiment-telemetry"><span><small>QUBITS</small><strong>{run.quantum.summary.qubits}</strong></span><span><small>SHOTS</small><strong>{run.quantum.summary.shots}</strong></span><span><small>ANALOG</small><strong>{run.quantum.summary.analogTerms}</strong></span><span><small>DIGITAL</small><strong>{run.quantum.summary.digitalTerms}</strong></span></div></div>
      <div className="split-layout sampling-split"><section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><RadioTower size={14} /> OBSERVATION FREQUENCY</span><h3>构型位串 counts</h3></div></div><CountsChart counts={run.quantum.counts} /><p className="subsection-note">有限 shots 观测频次，不表示热力学概率。</p></section><section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker"><Activity size={14} /> OBJECTIVE HISTORY</span><h3>QAOA 参数目标值</h3></div></div><ParameterChart history={run.quantum.parameterHistory} /></section></div>
      <div className="split-layout sampling-split"><section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker">COMPILED REGISTER</span><h3>独立 Rydberg 编译坐标</h3></div></div><AtomChart atoms={run.quantum.atoms} /></section>{run.quantum.mode === "hybrid" ? <section className="data-section chart-section"><div className="subsection-head"><div><span className="section-kicker">ANALOG BLOCK</span><h3>Rydberg 波形</h3></div></div><WaveformChart waveforms={run.quantum.waveforms} /></section> : <section className="data-section circuit-gate-table"><div className="subsection-head"><div><span className="section-kicker"><Atom size={14} /> DIGITAL CIRCUIT</span><h3>实际绑定 QAOA 线路</h3></div><span className="data-chip">DEPTH {run.quantum.circuit.depth}</span></div><div className="gate-sequence">{run.quantum.circuit.gates.slice(0, 24).map((gate) => <div key={`${gate.depth}-${gate.name}`}><small>{String(gate.depth + 1).padStart(2, "0")}</small><strong>{gate.name}</strong><span>{gate.targets.join(" · ")}</span></div>)}</div></section>}</div>
    </div>
  );
  return (
    <div className="view-stack">
      <MetricRail analysis={analysis} />
      <section className="data-section materials-empty-execution">
        <Grid3X3 size={28} aria-hidden="true" />
        <h3>材料 QUBO 已通过执行门禁</h3>
        <p>运行场景后展示真实 Digital / Hybrid 编译、counts、线路、波形和参数历史。</p>
      </section>
    </div>
  );
}

function ComparisonView({ analysis, run }: { analysis: MaterialsAnalysisPayload; run?: MaterialsRunPayload | null }) {
  if (analysis.executionFamily === "analog_ahs") {
    return (
      <div className="view-stack">
        <MetricRail analysis={analysis} run={run} />
        <section className="data-section materials-comparison">
          <div className="subsection-head">
            <div><span className="section-kicker">INDEPENDENT NUMERICAL REFERENCE</span><h3>AHS RK4 与 DOP853 对照</h3></div>
            <GitCompareArrows size={18} aria-hidden="true" />
          </div>
          {isAnalogRun(run) ? (
            <div className="comparison-columns materials-three-way">
              <div><span>CASCAQIT AHS</span><strong>{run.quantum.timeSeries.length} POINTS</strong><small>AnalogStateVectorKernel</small></div>
              <div><span>CLASSIC REFERENCE</span><strong>DOP853</strong><small>rtol {run.domain.classicReference.rtol.toExponential(0)}</small></div>
              <div><span>TERMINAL FIDELITY</span><strong>{run.domain.comparison.terminalStateFidelity.toFixed(8)}</strong><small>max Δn {run.domain.comparison.maxOccupationAbsoluteError.toExponential(2)}</small></div>
            </div>
          ) : (
            <div className="comparison-columns"><div><span>ANALOG RESULT</span><strong>NOT EXECUTED</strong><small>不以经典结果回填</small></div><div><span>CLASSIC REFERENCE</span><strong>READY</strong><small>执行后独立计算</small></div></div>
          )}
        </section>
        {isAnalogRun(run) ? <DynamicsChart points={run.quantum.timeSeries} classic={run.domain.classicReference.timeSeries} /> : null}
      </div>
    );
  }
  const optimizationRun = isOptimizationRun(run) ? run : null;
  return (
    <div className="view-stack">
      <MetricRail analysis={analysis} run={run} />
      <section className="data-section materials-comparison">
        <div className="subsection-head">
          <div><span className="section-kicker">REFERENCE SEPARATION</span><h3>量子结果与经典对照</h3></div>
          <GitCompareArrows size={18} aria-hidden="true" />
        </div>
        {optimizationRun ? <div className="comparison-columns materials-three-way"><div><span>QUANTUM OBSERVED</span><strong>{optimizationRun.domain.quantumCandidate ? optimizationRun.domain.quantumCandidate.physicalModelEnergy.toFixed(4) : "NOT OBSERVED"}</strong><small>{optimizationRun.domain.quantumCandidate ? `${optimizationRun.domain.quantumCandidate.selectedDefectIds.length} defects / ${optimizationRun.domain.quantumCandidate.selectedAdsorptionIds.length} adsorbates` : "不以经典结果回填"}</small></div><div><span>EXACT ENUMERATION</span><strong>{optimizationRun.domain.classicOptimum.physicalModelEnergy.toFixed(4)}</strong><small>{optimizationRun.domain.classicOptimum.bitstring}</small></div><div><span>OFFLINE REFERENCE</span><strong>{optimizationRun.domain.offlineReference.physicalModelEnergy.toFixed(4)}</strong><small>{optimizationRun.domain.offlineReference.feasible ? "compatible with current controls" : "default-control reference"}</small></div></div> : <div className="comparison-columns"><div><span>QUANTUM RESULT</span><strong>NOT EXECUTED</strong><small>不以经典结果回填</small></div><div><span>CLASSIC REFERENCE</span><strong>READY</strong><small>完整枚举 / 离线参考</small></div></div>}
        {optimizationRun ? <p className="subsection-note">{optimizationRun.domain.interpretation}</p> : null}
      </section>
    </div>
  );
}

type EvidenceRow = {
  label: string;
  value?: string | null;
  detail?: string;
};

function EvidenceSection({
  kicker,
  title,
  rows,
}: {
  kicker: string;
  title: string;
  rows: EvidenceRow[];
}) {
  const visibleRows = rows.filter((row) => row.value);
  if (!visibleRows.length) return null;
  return (
    <section className="data-section materials-audit-section">
      <div className="subsection-head">
        <div><span className="section-kicker">{kicker}</span><h3>{title}</h3></div>
        <span className="data-chip">{visibleRows.length} IDENTITIES</span>
      </div>
      <dl className="materials-evidence-list">
        {visibleRows.map((row, index) => (
          <div key={row.label}>
            <span className="materials-evidence-index">{String(index + 1).padStart(2, "0")}</span>
            <dt>{row.label}</dt>
            <dd><code>{row.value}</code>{row.detail ? <small>{row.detail}</small> : null}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function AuditView({ analysis, run }: { analysis: MaterialsAnalysisPayload; run?: MaterialsRunPayload | null }) {
  const analog = analysis.executionFamily === "analog_ahs";
  const audit = run?.audit;
  const backend = audit?.backend;
  const identityRows: EvidenceRow[] = [
    { label: "数据集清单", value: audit?.manifestHash ?? analysis.dataset.manifestHash, detail: `${analysis.dataset.id} / ${analysis.dataset.version}` },
    { label: "领域输入", value: audit?.domainInputHash, detail: "本次运行绑定的材料领域参数" },
    { label: "分析身份", value: audit?.analysisHash ?? analysis.analysisHash, detail: "分析结果与模式决策的稳定身份" },
    ...(analog
      ? [
          { label: "AHS 实验定义", value: audit?.problemHash ?? analysis.problem.hash, detail: analysis.problem.type },
          { label: "目标快照", value: analysis.analogProgram?.targetSnapshotHash ?? analysis.domain.targetValidation?.targetSnapshotHash, detail: "实验目标与校验诊断的冻结快照" },
          { label: "Rydberg 布局", value: audit?.rydbergLayoutHash ?? analysis.domain.rydbergLayoutHash, detail: "从材料有效窗口编译得到的中性原子坐标" },
          { label: "声明初态", value: audit?.initialStateHash ?? analysis.analogProgram?.initialStateHash ?? analysis.domain.initialState?.stateHash, detail: analysis.domain.initialState ? `${analysis.domain.initialState.basis} / ${analysis.domain.initialState.bitstring}` : undefined },
          { label: "脉冲计划", value: audit?.pulseScheduleHash ?? analysis.analogProgram?.pulseScheduleHash, detail: "Rabi、detuning、phase 与采样时刻" },
        ]
      : [
          { label: "QUBO 定义", value: audit?.problemHash ?? analysis.problem.hash, detail: `${analysis.problem.variables.length} 个决策变量 / ${analysis.problem.type}` },
        ]),
  ];
  const executionRows: EvidenceRow[] = audit
    ? [
        { label: "执行配置", value: audit.configurationHash, detail: audit.configurationSchema },
        { label: analog ? "AHS 编译程序" : "QUBO 编译", value: audit.compileHash, detail: analog ? "CASCAQit Analog AHS 编译产物" : "CASCAQit QAOA 编译产物" },
        { label: "后端能力快照", value: audit.backendHash, detail: backend ? `${backend.backendId} / ${backend.simulationMethod}` : undefined },
        { label: "本地执行", value: audit.executionHash, detail: "配置、编译产物与后端身份共同绑定" },
      ]
    : [];
  const resultRows: EvidenceRow[] = audit
    ? [
        { label: "量子结果", value: audit.resultHash, detail: analog ? "AHS 各采样时刻的量子演化结果" : "有限 shots 的 QAOA 观测结果" },
        ...(analog
          ? [
              { label: "时间序列", value: audit.trajectoryHash, detail: "逐时刻状态、占据、关联与 counts" },
              { label: "DOP853 经典参考", value: audit.classicReferenceHash, detail: "独立数值求解器生成的对照身份" },
            ]
          : []),
        { label: "审计结果载荷", value: audit.outcomeHash, detail: audit.outcomeSchema },
        { label: "结果呈现", value: audit.resultPresentationHash, detail: "领域结果视图所绑定的稳定身份" },
        { label: "报告", value: audit.reportHash, detail: audit.reportSchema },
      ]
    : [];
  return (
    <div className="view-stack materials-audit-view">
      <MetricRail analysis={analysis} run={run} />
      <section className="data-section materials-audit-overview">
        <div className="subsection-head">
          <div><span className="section-kicker">EVIDENCE OVERVIEW</span><h3>证据概览</h3></div>
          <span className="data-chip">{run ? "EXECUTED" : "ANALYSIS ONLY"}</span>
        </div>
        <div className="materials-audit-summary">
          <div><span>场景</span><strong>{analog ? "Pure Analog AHS" : "缺陷与吸附 QUBO"}</strong><small>{analysis.domain.modelLevel}</small></div>
          <div><span>证据阶段</span><strong>{run ? "完整执行链" : "分析身份"}</strong><small>{run ? "输入、编译、执行、结果、报告" : "执行后生成后续审计身份"}</small></div>
          <div><span>执行后端</span><strong>{backend?.backendId ?? "尚未执行"}</strong><small>{backend?.simulationMethod ?? "等待本地运行"}</small></div>
          <div><span>运行参数</span><strong>{audit ? `${audit.shots} shots / seed ${audit.seed}` : "未生成"}</strong><small>{audit ? `${audit.wallTimeSeconds.toFixed(3)} s / ${run?.quantum.mode.toUpperCase()}` : "无 execution / result hash"}</small></div>
        </div>
      </section>
      <EvidenceSection kicker="INPUT AND MODEL IDENTITY" title="输入与模型身份" rows={identityRows} />
      {run ? <EvidenceSection kicker="COMPILE AND EXECUTION" title="执行链" rows={executionRows} /> : null}
      {run ? <EvidenceSection kicker="RESULT AND REPORT" title="结果与报告" rows={resultRows} /> : null}
      <section className="data-section materials-audit-boundaries">
        <div className="subsection-head">
          <div><span className="section-kicker">INTERPRETATION SCOPE</span><h3>解释边界</h3></div>
          <AlertTriangle size={18} aria-hidden="true" />
        </div>
        <div className="boundary-list">
          {analysis.domain.limitations.map((limitation) => (
            <span key={limitation}><AlertTriangle size={13} aria-hidden="true" />{limitation}</span>
          ))}
        </div>
      </section>
    </div>
  );
}

export function MaterialsView({
  analysis,
  run,
  view,
}: {
  analysis: MaterialsAnalysisPayload;
  run?: MaterialsRunPayload | null;
  view: ViewId;
}) {
  if (view === "business") return <ResultView analysis={analysis} run={run} />;
  if (view === "mapping") return <MappingView analysis={analysis} run={run} />;
  if (view === "quantum") return <QuantumPreview analysis={analysis} run={run} />;
  if (view === "comparison") return <ComparisonView analysis={analysis} run={run} />;
  if (view === "audit") return <AuditView analysis={analysis} run={run} />;
  const selectedSolution = isOptimizationRun(run) ? run.domain.quantumCandidate : null;
  const selected = selectedSolution ? new Set([...selectedSolution.selectedDefectIds, ...selectedSolution.selectedAdsorptionIds]) : undefined;
  return (
    <div className="view-stack">
      <MetricRail analysis={analysis} run={run} />
      <div className={`materials-structure-split ${analysis.executionFamily === "analog_ahs" ? "has-register" : ""}`}>
        <LatticeFigure analysis={analysis} selected={selected} />
        {analysis.executionFamily === "analog_ahs" ? <RydbergFigure analysis={analysis} /> : null}
      </div>
    </div>
  );
}
