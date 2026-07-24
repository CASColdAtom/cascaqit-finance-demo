export type Mode = "digital" | "hybrid" | "analog";
export type SearchStrategy = "preset" | "grid" | "seeded_sample";
export type ModeStatus = "recommended" | "comparable" | "unsuitable";
export type Accent = "cyan" | "emerald" | "amber";

export interface SelectOption {
  value: string;
  label: string;
}

export interface ControlSpec {
  key: string;
  label: string;
  kind: "range" | "select";
  minimum: number | null;
  maximum: number | null;
  step: number | null;
  options: SelectOption[];
  unit: string;
}

export interface ScenarioSpec {
  caseId: string;
  shortTitle: string;
  title: string;
  eyebrow: string;
  description: string;
  icon: string;
  accent: Accent;
  presets: SelectOption[];
  controls: ControlSpec[];
  values: Record<string, string | number | boolean>;
  recommendedMode: Mode;
}

export interface InputRow {
  id: string;
  label: string;
  group: string;
  primary: string;
  secondary: string;
  detail: string;
}

export interface ModeDecisionRow {
  mode: Mode;
  algorithm: "qaoa" | "qaa";
  status: ModeStatus;
  compilerFeasible: boolean;
  businessSuitable: boolean;
  reason: string;
  diagnosticCodes: string[];
  analogTermCount: number;
  digitalTermCount: number;
  analogBusinessPairs: string[][];
}

export interface MatrixCell {
  left: string;
  right: string;
  value: number;
}

export type ScenarioVisualKind =
  | "portfolio-correlation"
  | "settlement-network"
  | "fraud-entity-network"
  | "collateral-flow"
  | "liquidity-timeline"
  | "credit-capital-map"
  | "derivatives-pnl-surface";

export interface ScenarioVisualNode {
  id: string;
  label: string;
  group: string;
  role: string;
  value: number;
  detail: string;
}

export interface ScenarioVisualEdge {
  id?: string;
  source: string;
  target: string;
  kind: string;
  value?: number;
  label?: string;
}

export interface ScenarioVisualPoint {
  id: string;
  label: string;
  group: string;
  x: number;
  y: number;
  value: number;
  size: number;
  detail: string;
}

export interface ScenarioVisualCell {
  id: string;
  x: number;
  y: number;
  value: number;
  label: string;
}

export interface ScenarioVisualSeries {
  name: string;
  group: string;
  points: Array<{ id: string; x: number; y: number }>;
}

export interface ScenarioVisualPayload {
  kind: ScenarioVisualKind;
  title: string;
  subtitle: string;
  xLabel: string;
  yLabel: string;
  categories: string[];
  nodes: ScenarioVisualNode[];
  edges: ScenarioVisualEdge[];
  points: ScenarioVisualPoint[];
  matrix: {
    xLabels: string[];
    yLabels: string[];
    cells: ScenarioVisualCell[];
  };
  series: ScenarioVisualSeries[];
}

export interface AnalysisPayload {
  caseId: string;
  inputRows: InputRow[];
  problem: {
    id: string;
    type: string;
    hash: string;
    variables: string[];
    matrix: { variables: string[]; cells: MatrixCell[] };
    termGroups: Array<{
      group_id: string;
      label: string;
      kind: string;
      variables: string[];
      pairs: string[][];
    }>;
  };
  resource: Record<string, number | string | boolean>;
  layout: AtomPoint[];
  scenarioVisual: ScenarioVisualPayload;
  decision: {
    recommendedMode: Mode;
    reason: string;
    modes: ModeDecisionRow[];
  };
}

export interface AnalyzeResponse {
  scenario: ScenarioSpec;
  preset: string;
  analysis: AnalysisPayload;
}

export interface Metric {
  label: string;
  value: string;
  context: string;
}

export interface BusinessPoint {
  id: string;
  label: string;
  group: string;
  x: number;
  y: number;
  size: number;
  selected: boolean;
  detail: string;
}

export interface SelectionRow extends InputRow {
  selected: boolean;
  reason: string;
}

export interface ConstraintCheck {
  name: string;
  passed: boolean;
  actual: string;
  expected: string;
}

export interface NetworkData {
  nodes: Array<{ id: string; group: string; value: number }>;
  edges: Array<{
    source: string;
    target: string;
    kind: "conflict" | "dependency";
  }>;
}

export interface BusinessPayload {
  metrics: Metric[];
  chart: {
    kind: string;
    title: string;
    xLabel: string;
    yLabel: string;
    points: BusinessPoint[];
  };
  selection: SelectionRow[];
  checks: ConstraintCheck[];
  displayedSource: string;
  candidate: Record<string, unknown>;
  baseline: Record<string, unknown> | null;
  network: NetworkData | null;
  pricing?: Record<string, string | number | null>;
}

export interface CircuitGate {
  depth: number;
  name: string;
  targets: string[];
  controls: string[];
  parameters: Record<string, unknown>;
}

export interface AtomPoint {
  id: string;
  x: number;
  y: number;
  selected?: boolean;
}

export interface WavePoint {
  time: number;
  value: number;
  raw: number;
}

export interface QuantumPayload {
  mode: Mode;
  algorithm: string;
  topology: string | null;
  layerCount: number;
  searchStrategy: "preset" | "grid" | "seeded_sample" | "explicit";
  evaluationCount: number;
  selectedEvaluationIndex: number;
  blocks: string[];
  layers: string[];
  circuit: { qubits: string[]; gates: CircuitGate[]; depth: number };
  atoms: AtomPoint[];
  waveforms: Record<"rabi" | "detuning" | "phase", WavePoint[]>;
  counts: Array<{ state: string; count: number; rank: number }>;
  parameterHistory: Array<{
    index: number;
    objective: number;
    parameters: Record<string, number>;
    selected: boolean;
  }>;
  termMapping: Array<{
    operator: string;
    targets: string[];
    logical: number;
    analog: number;
    digital: number;
    implementation: string;
  }>;
  summary: {
    analogTerms: number;
    digitalTerms: number;
    qubits: number;
    shots: number;
  };
}

export interface AuditPayload {
  caseId: string;
  mode: Mode;
  problemHash: string;
  analysisHash: string;
  compileHash: string;
  executionHash: string;
  targetId: string;
  backend: string;
  executionKind: string;
  seed: number;
  shots: number;
  wallTimeSeconds: number;
  hardwareExecution: boolean;
  cloudExecution: boolean;
  networkAccessed: boolean;
  optimalityClaim: string;
  reportPath: string | null;
}

export interface RunPayload {
  analysis: AnalysisPayload;
  business: BusinessPayload;
  quantum: QuantumPayload;
  audit: AuditPayload;
}

export interface RunResponse {
  scenario: ScenarioSpec;
  preset: string;
  run: RunPayload;
}

export interface ScenarioRequest {
  preset: string;
  values: Record<string, string | number | boolean>;
}

export interface RunRequest extends ScenarioRequest {
  mode: Mode;
  shots: number;
  seed: number;
  layers: number;
  search_strategy: SearchStrategy;
  parameter_budget: number;
}
