import {
  AlertTriangle,
  Atom,
  Braces,
  GitCompareArrows,
  Grid3X3,
  RadioTower,
  Waves,
} from "lucide-react";
import type { MaterialsAnalysisPayload } from "../types";
import type { ViewId } from "./viewTabs";

function MetricRail({ analysis }: { analysis: MaterialsAnalysisPayload }) {
  const analog = analysis.executionFamily === "analog_ahs";
  const activeSites = analysis.domain.nodes.filter(
    (node) => node.role !== "vacancy",
  ).length;
  return (
    <div className="scenario-analysis-rail materials-metric-rail">
      <div>
        <span>EXPERIMENT KIND</span>
        <strong>{analog ? "ANALOG AHS" : "MATERIAL QUBO"}</strong>
        <small>{analysis.implementationStatus.toUpperCase()}</small>
      </div>
      <div>
        <span>EFFECTIVE SITES</span>
        <strong>{activeSites}</strong>
        <small>{analysis.domain.nodes.length - activeSites} defect sites</small>
      </div>
      <div>
        <span>COORDINATE IDENTITIES</span>
        <strong>{analog ? "3" : "2"}</strong>
        <small>material / effective{analog ? " / Rydberg" : ""}</small>
      </div>
      <div>
        <span>EXECUTION GATE</span>
        <strong>PREVIEW</strong>
        <small>executor unavailable</small>
      </div>
    </div>
  );
}

function LatticeFigure({ analysis }: { analysis: MaterialsAnalysisPayload }) {
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
          <g className="lattice-site" data-role={node.role} key={node.id}>
            <circle cx={node.x} cy={node.y} r="4.5" />
            <text x={node.x} y={node.y + 1.3}>{node.role === "vacancy" ? "V" : node.label}</text>
          </g>
        ))}
        {adsorbates.map((item) => {
          const position = positions.get(item.site);
          if (!position) return null;
          return (
            <g className="adsorbate-site" key={item.id}>
              <line x1={position.x} y1={position.y - 5} x2={position.x} y2={position.y - 13} />
              <rect x={position.x - 6} y={position.y - 22} width="12" height="8" rx="2" />
              <text x={position.x} y={position.y - 16.3}>{item.label}</text>
            </g>
          );
        })}
      </svg>
      <div className="materials-legend" aria-label="晶格图例">
        <span><i data-kind="site" />有效位点</span>
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
        viewBox="0 0 42 36"
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
        当前仅展示定义和采样网格；SDK 时分辨契约通过前不生成占据或关联时间序列。
      </p>
    </section>
  );
}

function ResultView({ analysis }: { analysis: MaterialsAnalysisPayload }) {
  const analog = analysis.executionFamily === "analog_ahs";
  return (
    <div className="view-stack">
      <MetricRail analysis={analysis} />
      <section className="data-section materials-readiness">
        <div className="subsection-head">
          <div>
            <span className="section-kicker">SCENARIO READINESS</span>
            <h3>{analog ? "纯 Analog 实验门禁" : "材料构型优化门禁"}</h3>
          </div>
          <span className="data-chip status-preview">PLANNED</span>
        </div>
        <div className="readiness-grid">
          {(analog
            ? [
                ["AHS 定义", "已建模", "ok"],
                ["执行族", "ANALOG ONLY", "ok"],
                ["时分辨结果", "SDK GAP", "warn"],
                ["本地规模", "4 atoms", "warn"],
              ]
            : [
                ["周期晶格", "已建模", "ok"],
                ["联合变量", "已定义", "ok"],
                ["离线能量 fixture", "待固化", "warn"],
                ["Hybrid 几何", "待验证", "warn"],
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

function MappingView({ analysis }: { analysis: MaterialsAnalysisPayload }) {
  const analog = analysis.executionFamily === "analog_ahs";
  const stages = analog
    ? ["有效晶格", "AHS 定义", "目标校验", "AnalogExecutor", "时序观测量"]
    : ["周期表面", "对称归一", "材料 QUBO", "Digital / Hybrid", "构型解码"];
  return (
    <div className="view-stack">
      <MetricRail analysis={analysis} />
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
    </div>
  );
}

function QuantumPreview({ analysis }: { analysis: MaterialsAnalysisPayload }) {
  if (analysis.executionFamily === "analog_ahs") {
    return <div className="view-stack"><MetricRail analysis={analysis} /><PulsePreview analysis={analysis} /></div>;
  }
  return (
    <div className="view-stack">
      <MetricRail analysis={analysis} />
      <section className="data-section materials-empty-execution">
        <Grid3X3 size={28} aria-hidden="true" />
        <h3>材料 QUBO 执行链尚未开放</h3>
        <p>周期、计量和对称性 fixture 固化后，Digital 与 Hybrid 将使用同一逻辑 QUBO。</p>
      </section>
    </div>
  );
}

function ComparisonView({ analysis }: { analysis: MaterialsAnalysisPayload }) {
  return (
    <div className="view-stack">
      <MetricRail analysis={analysis} />
      <section className="data-section materials-comparison">
        <div className="subsection-head">
          <div><span className="section-kicker">REFERENCE SEPARATION</span><h3>量子结果与经典对照</h3></div>
          <GitCompareArrows size={18} aria-hidden="true" />
        </div>
        <div className="comparison-columns">
          <div><span>QUANTUM RESULT</span><strong>NOT EXECUTED</strong><small>不以经典结果回填</small></div>
          <div><span>CLASSIC REFERENCE</span><strong>PLANNED</strong><small>{analysis.executionFamily === "analog_ahs" ? "独立精确时间演化" : "枚举 / 整数规划"}</small></div>
        </div>
      </section>
    </div>
  );
}

function AuditView({ analysis }: { analysis: MaterialsAnalysisPayload }) {
  return (
    <div className="view-stack">
      <MetricRail analysis={analysis} />
      <section className="audit-section materials-audit">
        <div className="subsection-head">
          <div><span className="section-kicker">IMMUTABLE IDENTITIES</span><h3>分析预览审计</h3></div>
          <span className="data-chip">NO EXECUTION HASH</span>
        </div>
        <dl>
          <dt>Analysis</dt><dd><code>{analysis.analysisHash}</code></dd>
          <dt>Dataset</dt><dd><code>{analysis.dataset.manifestHash}</code></dd>
          <dt>Problem</dt><dd><code>{analysis.problem.hash}</code></dd>
          <dt>Execution</dt><dd>未执行，不生成 execution/result hash</dd>
        </dl>
        <div className="interpretation-boundary">
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
  view,
}: {
  analysis: MaterialsAnalysisPayload;
  view: ViewId;
}) {
  if (view === "business") return <ResultView analysis={analysis} />;
  if (view === "mapping") return <MappingView analysis={analysis} />;
  if (view === "quantum") return <QuantumPreview analysis={analysis} />;
  if (view === "comparison") return <ComparisonView analysis={analysis} />;
  if (view === "audit") return <AuditView analysis={analysis} />;
  return (
    <div className="view-stack">
      <MetricRail analysis={analysis} />
      <div className={`materials-structure-split ${analysis.executionFamily === "analog_ahs" ? "has-register" : ""}`}>
        <LatticeFigure analysis={analysis} />
        {analysis.executionFamily === "analog_ahs" ? <RydbergFigure analysis={analysis} /> : null}
      </div>
    </div>
  );
}
