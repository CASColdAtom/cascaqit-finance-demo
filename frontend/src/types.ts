export type Mode = "digital" | "hybrid" | "analog";
export type Algorithm = "recommended" | "qaoa" | "vqe" | "qaa";
export type ResolvedAlgorithm = Exclude<Algorithm, "recommended">;
export type LayerPolicy = "fixed" | "adaptive";
export type SearchStrategy = "preset" | "grid" | "seeded_sample" | "continuous";
export type ModeStatus = "recommended" | "comparable" | "unsuitable";
export type Accent = "cyan" | "emerald" | "amber";
export type DomainId = "finance" | "biomedicine";
export type ImplementationStatus = "available" | "preview";
export type ExperimentLevel = "standard" | "advanced";
export type ComplexityLevel = "standard" | "advanced_live" | "research";
export type ComplexityProfileStatus = "available" | "planned";

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

export interface ExecutionProfile {
  shots: number;
  seed: number;
  algorithm?: Algorithm;
  layerPolicy?: LayerPolicy;
  layers: number;
  maxLayers?: number;
  minImprovement?: number;
  searchStrategy: SearchStrategy;
  parameterBudget: number;
  optimizerStarts?: number;
  repeats?: number;
  estimatedSeconds?: number;
}

export interface ScenarioSpec {
  domainId?: DomainId;
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
  recommendedExecution?: ExecutionProfile;
  executionFamily?: "problem" | "pauli_vqe";
  resultKind?: string;
  visualKind?: string;
  capabilities?: string[];
  implementationStatus?: ImplementationStatus;
  experimentLevels?: ExperimentLevel[];
  complexityProfiles?: ComplexityProfile[];
}

export interface ComplexityProfile {
  profileId: ComplexityLevel;
  level: ComplexityLevel;
  status: ComplexityProfileStatus;
  limits: {
    logicalQubits: number;
    problemVariables: number;
    operatorTerms: number;
    measurementGroups: number;
    shots: number;
    objectiveEvaluations: number;
    estimatedSeconds: number;
  };
}

export interface CapabilityItem {
  id: string;
  label: string;
  layer: "sdk" | "application" | "sdk_application";
  status: "available" | "unavailable";
  reason: string;
  contractTests: string[];
}

export interface CapabilitySnapshot {
  sdk: {
    name: "CASCAQit";
    version: string;
    validatedRelease: boolean;
    validatedRange: string;
  };
  capabilities: CapabilityItem[];
}

export interface ExperimentPlanDiagnostic {
  code: string;
  message: string;
  stage: "planning";
}

export interface ExperimentPlanPoint {
  index: number;
  values: Record<string, string | number | boolean>;
  dataset: {
    id: string;
    version: string;
    manifestHash: string;
  } & Record<string, unknown>;
  analysisHash?: string;
  problemHash: string;
  resource: {
    logicalQubits: number;
    problemVariables: number;
    operatorTerms: number;
    measurementGroups: number;
  };
}

export interface ExperimentPlan {
  planId: string;
  caseId: string;
  preset: string;
  experimentLevel: ExperimentLevel;
  profileId: ComplexityLevel;
  completeDomainProblemHash: string;
  quantumSubproblemHash: string;
  points: ExperimentPlanPoint[];
  configurations: Array<Record<string, unknown>>;
  seeds: number[];
  runCount: number;
  estimatedSeconds: number;
  maxUnitEstimatedSeconds: number;
  executionPolicy: "sync" | "job" | "rejected";
  diagnostics: ExperimentPlanDiagnostic[];
  profile: ComplexityProfile;
  capabilitySnapshot: CapabilitySnapshot;
}

export interface WorkbenchModeDecisionRow {
  mode: Mode;
  algorithm: ResolvedAlgorithm;
  availableAlgorithms?: ResolvedAlgorithm[];
  status: ModeStatus;
  reason: string;
  compilerFeasible?: boolean;
  businessSuitable?: boolean;
  diagnosticCodes?: string[];
  analogTermCount?: number;
  digitalTermCount?: number;
  analogBusinessPairs?: string[][];
  coveredGroupIds?: string[];
  missingContributionIds?: string[];
  unexpectedAnalogTermIds?: string[];
  unexpectedInteractionPairs?: string[][];
  geometryStatus?: "verified" | "missing" | "distorted";
  geometrySource?: "business_native" | "verified_embedding" | null;
  layoutPolicy?: string;
  declaredContributionCount?: number;
  coveredContributionCount?: number;
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
  algorithm: ResolvedAlgorithm;
  availableAlgorithms?: ResolvedAlgorithm[];
  status: ModeStatus;
  compilerFeasible: boolean;
  businessSuitable: boolean;
  reason: string;
  diagnosticCodes: string[];
  analogTermCount: number;
  digitalTermCount: number;
  analogBusinessPairs: string[][];
  coveredGroupIds: string[];
  missingContributionIds: string[];
  unexpectedAnalogTermIds: string[];
  unexpectedInteractionPairs: string[][];
  geometryStatus: "verified" | "missing" | "distorted";
  geometrySource: "business_native" | "verified_embedding" | null;
  layoutPolicy: string;
  declaredContributionCount: number;
  coveredContributionCount: number;
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
  stressedPrice?: number;
  riskWeight?: number;
  delta?: number;
  gamma?: number;
  vega?: number;
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
    coefficientLedger: {
      applicability: "qubo" | "not_applicable_graph" | "not_declared";
      balanced: boolean;
      hamiltonianBalanced: boolean;
      contributionCount: number;
      canonicalTermCount: number;
      rows: Array<{
        contributionId: string;
        groupId: string;
        groupLabel: string;
        sourceRule: string;
        sourceRuleLabel: string;
        role: "objective" | "constraint" | "auxiliary";
        termKind: "offset" | "linear" | "quadratic";
        targets: string[];
        contributionCoefficient: number;
        canonicalTermId: string;
        canonicalCoefficient: number;
        hamiltonianTerms: Array<{
          termId: string;
          operator: string;
          targets: string[];
          contributionEffect: number;
          canonicalTermEffect: number;
          logical: number;
          analog: number | null;
          digital: number | null;
          implementation: string;
          implementationLabel: string;
          allocationConserved: boolean;
        }>;
        conserved: boolean;
      }>;
    };
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

export interface BiomedicineStructureNode {
  id: string;
  label?: string;
  element?: string;
  group?: string;
  role?: string;
  x: number;
  y: number;
  z?: number;
}

export interface BiomedicineStructureEdge {
  source: string;
  target: string;
  kind?: string;
  score?: number;
  order?: number;
  lengthAngstrom?: number;
  matchId?: string;
  poseId?: string;
  critical?: boolean;
}

export interface BiomedicineAnalysisPayload {
  kind: "biomedicine";
  caseId: string;
  executionFamily: "pauli_vqe" | "problem";
  implementationStatus: ImplementationStatus;
  analysisHash?: string;
  dataset: {
    id: string;
    version: string;
    manifestHash: string;
    sourceKind: string;
    license: string;
    sourceUri?: string;
    sourceChecksum?: string;
    sourceInputHash?: string;
    generationScriptHash?: string;
    licensePolicyUri?: string;
    licenseCheckedAt?: string;
    allowedClaims?: string[];
    limitations: string[];
  };
  problem: {
    id: string;
    type: string;
    hash: string;
    variables: string[];
    constant?: number;
    terms: Array<{
      id: string;
      operator: string;
      targets: string[];
      coefficient: number;
    }>;
    measurementPlanHash?: string;
    measurementGroups?: Array<{
      index: number;
      basis: Record<string, string>;
      termIds: string[];
    }>;
    termGroups?: Array<{
      group_id: string;
      label: string;
      kind: string;
      variables: string[];
      pairs: string[][];
    }>;
    coefficientLedger?: {
      balanced: boolean;
      contributionCount: number;
      canonicalTermCount: number;
      rows: Array<{
        contributionId: string;
        groupId: string;
        sourceRule: string;
        role: string;
        termKind: string;
        targets: string[];
        coefficient: number;
        canonicalTermId: string;
      }>;
    };
  };
  resource: Record<string, number | string | boolean>;
  decision: {
    recommendedMode: Mode;
    reason: string;
    modes: WorkbenchModeDecisionRow[];
  };
  domain: {
    kind: string;
    modelLevel?: string;
    datasetKey?: string;
    preset?: string;
    noiseModel?: string;
    molecule?: string;
    geometryLabel?: string;
    bondLengthAngstrom?: number;
    charge?: number;
    multiplicity?: number;
    basis?: string;
    activeSpace?: string;
    mapping?: string;
    referenceHartreeFockBitstring?: string;
    bondScanReference?: Array<{
      dataset: string;
      bondLengthAngstrom: number;
      exactGroundEnergy: number;
      hartreeFockEnergy: number;
      selected: boolean;
    }>;
    potentialScanReference?: Array<{
      dataset: string;
      bondLengthAngstrom: number;
      exactGroundEnergy: number;
      hartreeFockEnergy: number;
      selected: boolean;
    }>;
    sequence?: string;
    conformations?: Array<{
      id: string;
      coordinates: number[][];
      contacts: number[][];
      energy: number;
      contactCount: number;
    }>;
    classicGroundIds?: string[];
    structure?: {
      pdb_id: string;
      title: string;
      ligand_component_id: string;
      ligand_name: string;
      protein_chains: string[];
      pocket_residues: string[];
    };
    poses?: Array<{
      id: string;
      label: string;
      strain: number;
      reference: boolean;
    }>;
    matches?: Array<{
      id: string;
      pose_id: string;
      ligand_feature: string;
      pocket_feature: string;
      interaction: string;
      quality: number;
      distance_deviation: number;
      angle_deviation: number;
      critical: boolean;
      reference: boolean;
    }>;
    conflicts?: Array<{
      left: string;
      right: string;
      rule: string;
      evidence: string;
    }>;
    minimumCoverage?: number;
    weights?: Record<string, string | number>;
    atoms?: BiomedicineStructureNode[];
    bonds?: BiomedicineStructureEdge[];
    nodes?: BiomedicineStructureNode[];
    edges?: BiomedicineStructureEdge[];
    limitations: string[];
    reference?: {
      method: string;
      exact_ground_energy_hartree: number;
      hartree_fock_energy_hartree: number;
    } | {
      pose_id: string;
      match_ids: string[];
      interpretation: string;
    };
  };
}

export type WorkbenchAnalysisPayload = AnalysisPayload | BiomedicineAnalysisPayload;

export interface AnalyzeResponse {
  scenario: ScenarioSpec;
  preset: string;
  analysis: WorkbenchAnalysisPayload;
  experimentPlan?: ExperimentPlan;
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
  riskScenarios?: Array<Record<string, string | number>>;
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
  algorithm: ResolvedAlgorithm;
  topology: string | null;
  layerCount: number;
  searchStrategy: SearchStrategy | "explicit";
  evaluationCount: number;
  selectedEvaluationIndex: number;
  optimizer?: {
    method: string;
    starts: number;
    perStartEvaluationBudget: number | null;
    maximumEvaluationCount: number | null;
    selectedStartIndex: number | null;
    startInitializations: string[];
    terminationReason: string | null;
    backendExecutionCount: number | null;
  } | null;
  ansatz?: {
    kind: string;
    layers: number;
    parameterNames: string[];
    parameterCount: number;
    circuitHash: string;
    ansatzHash: string;
    definition: {
      definition_kind: string;
      entanglement: string;
      rotation_axes: string[];
      schema_version: string;
    } | null;
  } | null;
  layerEvidence?: {
    policy: LayerPolicy;
    selectedLayers: number;
    executedLayers: number[];
    maxLayers: number;
    minImprovement: number;
    stopReason: "fixed" | "max_layers_reached" | "patience_exhausted";
    totalEvaluationCount: number;
    steps: Array<{
      layers: number;
      objective: number;
      improvementFromIncumbent: number | null;
      materialImprovement: boolean;
      evaluationCount: number;
      selected: boolean;
    }>;
  };
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
  statistics?: RepeatedRunStatistics;
}

export interface ElectronicStructureRunPayload {
  kind: "biomedicine";
  analysis: BiomedicineAnalysisPayload;
  domain: {
    kind: "ground_state_energy";
    molecule: string;
    datasetKey: string;
    exactOptimizedEnergy: number;
    sampledConfirmationEnergy: number;
    sampledStandardError: number;
    noisySampledConfirmationEnergy: number | null;
    noisySampledStandardError: number | null;
    referenceEnergy: number;
    absoluteErrorHartree: number;
    relativeError: number;
    chemicalAccuracyThresholdHartree: number | null;
    withinChemicalAccuracy: boolean | null;
    accuracyClaim: "h2_equilibrium_benchmark" | "error_report_only";
    estimatorNote: string;
  };
  quantum: {
    kind: "pauli_vqe";
    mode: "digital";
    algorithm: "vqe";
    summary: {
      qubits: number;
      pauliTerms: number;
      measurementGroups: number;
      shotsPerGroup: number;
      totalMeasurementShots: number;
      evaluations: number;
      noiseModel?: "ideal" | "readout_demo";
    };
    circuit: { qubits: string[]; gates: CircuitGate[]; depth: number };
    counts: Record<string, number>;
    parameterHistory: Array<{
      index: number;
      objective: number;
      parameters: Record<string, number>;
      selected?: boolean;
    }>;
    measurement: {
      planHash: string;
      groups: Array<{
        index: number;
        basis: Record<string, string>;
        shots: number;
        counts: Record<string, number>;
        termExpectations?: Record<string, number>;
        termStandardErrors?: Record<string, number>;
        executionEvidence?: Record<string, unknown>;
      }>;
      noisyGroups?: Array<{
        index: number;
        basis: Record<string, string>;
        shots: number;
        counts: Record<string, number>;
        termExpectations?: Record<string, number>;
        termStandardErrors?: Record<string, number>;
        executionEvidence?: Record<string, unknown>;
      }>;
      noiseModelHash?: string | null;
    };
    termination: Record<string, string | number | boolean | null>;
    ansatz: Record<string, unknown>;
  };
  comparison: {
    referenceMethod: string;
    hartreeFockEnergy: number;
    exactGroundEnergy: number;
    vqeExactEnergy: number;
    vqeSampledEnergy: number;
    vqeNoisySampledEnergy: number | null;
  };
  audit: {
    domainId: "biomedicine";
    caseId: string;
    datasetId: string;
    datasetVersion: string;
    manifestHash: string;
    sourceInputHash?: string;
    domainInputHash?: string;
    hamiltonianHash: string;
    analysisHash: string;
    ansatzHash: string;
    compileHash?: string;
    measurementPlanHash: string;
    backend?: Record<string, unknown>;
    backendHash?: string;
    configurationHash: string;
    outcomeHash: string;
    noiseModelHash?: string | null;
    executionHash: string;
    resultHash: string;
    reportHash?: string;
    seed: number;
    shotsPerGroup: number;
    warmStartSource?: string;
    hardwareExecution: false;
    cloudExecution: false;
    networkAccessed: false;
    wallTimeSeconds: number;
    optimalityClaim?: string;
    claimBoundary?: string;
    reportPath?: string;
    timings?: {
      preflightSeconds: number;
      executionSeconds: number;
      reportSeconds: number;
      totalSeconds: number;
    };
  };
}

export interface ActiveCenterRunPayload
  extends Omit<ElectronicStructureRunPayload, "domain" | "comparison" | "audit"> {
  domain: {
    kind: "active_center_result";
    vqeExactEnergyMeV: number;
    sampledEnergyMeV: number;
    sampledStandardErrorMeV: number;
    exactGroundEnergyMeV: number;
    exactFirstGapMeV: number;
    exactFirstGapSource: "classical_exact_diagonalization";
    absoluteErrorMeV: number;
    magnetization: Array<{
      siteId: string;
      expectation: number;
      standardError: number;
    }>;
    correlations: Array<{
      pathId: string;
      leftSiteId: string;
      rightSiteId: string;
      operator: "XX" | "YY" | "ZZ";
      expectation: number;
      standardError: number;
    }>;
    sectorOccupancy: Record<string, number>;
    declaredSector: string;
    interpretation: string;
  };
  comparison: {
    referenceMethod: string;
    hamiltonianHash: string;
    exactSpectrumMeV: number[];
    exactFirstGapMeV: number;
    exactFirstGapSource: "classical_exact_diagonalization";
    exactExpectations: Record<string, number>;
    exactSectorOccupancy: Record<string, number>;
    vqeHamiltonianHash: string;
  };
  audit: ElectronicStructureRunPayload["audit"] & {
    referenceHamiltonianHash: string;
    claimBoundary: "effective_spin_model_only";
  };
}

export interface DockingSolutionPayload {
  source: "quantum_observed" | "complete_enumeration" | "co_crystal_reference";
  bitstring: string;
  poseId: string | null;
  selectedMatchIds: string[];
  modelObjective: number;
  domainScore: number;
  coverage: number;
  referenceOverlap: number;
  feasible: boolean;
  checks: Array<{
    id: string;
    label: string;
    passed: boolean;
    actual: string | number;
    expected: string | number;
  }>;
}

export interface DockingRunPayload {
  kind: "biomedicine";
  analysis: BiomedicineAnalysisPayload;
  domain: {
    kind: "docking_match_result";
    quantumCandidate: DockingSolutionPayload;
    classicOptimum: DockingSolutionPayload;
    coCrystalReference: DockingSolutionPayload;
    topObservedFeasible: DockingSolutionPayload[];
    observedFeasibleCount: number;
    interpretation: string;
  };
  quantum: {
    kind: "problem_qaoa";
    mode: "digital" | "hybrid";
    algorithm: "qaoa";
    topology: string | null;
    layerCount: number;
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
      termId: string;
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
      evaluations: number;
    };
  };
  audit: {
    domainId: "biomedicine";
    caseId: "docking_match";
    datasetId: string;
    datasetVersion: string;
    manifestHash: string;
    domainInputHash: string;
    problemHash: string;
    analysisHash: string;
    compileHash: string;
    executionHash: string;
    resultHash: string;
    resultPresentationHash: string;
    backend: Record<string, unknown>;
    backendHash: string;
    configurationHash: string;
    outcomeHash: string;
    reportHash: string;
    seed: number;
    shots: number;
    hardwareExecution: false;
    cloudExecution: false;
    networkAccessed: false;
    wallTimeSeconds: number;
    optimalityClaim: string;
    claimBoundary: string;
    reportPath?: string;
    timings?: ElectronicStructureRunPayload["audit"]["timings"];
  };
}

export interface PeptideSolutionPayload {
  bitstring: string;
  conformationId: string | null;
  energy: number | null;
  contactCount: number;
  coordinates: number[][];
  contacts: number[][];
  feasible: boolean;
  count?: number;
}

export interface PeptideRunPayload {
  kind: "biomedicine";
  analysis: BiomedicineAnalysisPayload;
  domain: {
    kind: "peptide_landscape_result";
    quantumCandidate: PeptideSolutionPayload;
    topObservedFeasible: PeptideSolutionPayload[];
    observedFeasibleCount: number;
    classicGroundConformations: Array<{
      id: string;
      coordinates: number[][];
      contacts: number[][];
      energy: number;
      contactCount: number;
    }>;
    fullLandscape: Array<{
      id: string;
      coordinates: number[][];
      contacts: number[][];
      energy: number;
      contactCount: number;
    }>;
    energyGapFromGround: number | null;
    interpretation: string;
  };
  quantum: {
    kind: "problem_qaoa";
    mode: "digital";
    algorithm: "qaoa";
    summary: { qubits: number; shots: number; evaluations: number; feasibleObserved: number };
    circuit: { qubits: string[]; gates: CircuitGate[]; depth: number };
    counts: Array<{ state: string; count: number; rank: number }>;
    parameterHistory: Array<{
      index: number;
      objective: number;
      parameters: Record<string, number>;
      selected: boolean;
    }>;
  };
  audit: {
    domainId: "biomedicine";
    caseId: "peptide_landscape";
    datasetId: string;
    datasetVersion: string;
    manifestHash: string;
    domainInputHash: string;
    problemHash: string;
    hamiltonianHash: string;
    analysisHash: string;
    ansatzHash: string;
    compileHash: string;
    backend: Record<string, unknown>;
    backendHash: string;
    configurationHash: string;
    outcomeHash: string;
    executionHash: string;
    resultHash: string;
    reportHash: string;
    seed: number;
    shots: number;
    hardwareExecution: false;
    cloudExecution: false;
    networkAccessed: false;
    wallTimeSeconds: number;
    optimalityClaim: string;
    claimBoundary: string;
    reportPath?: string;
    timings?: ElectronicStructureRunPayload["audit"]["timings"];
  };
}

export type BiomedicineRunPayload =
  | ElectronicStructureRunPayload
  | ActiveCenterRunPayload
  | PeptideRunPayload
  | DockingRunPayload;

export type WorkbenchRunPayload = RunPayload | BiomedicineRunPayload;

export interface RepeatedRunStatistics {
  repeatCount: number;
  feasibleCount: number;
  feasibleRate: number;
  successSource: "quantum_business_candidate";
  representativeRunIndex: number;
  objective: {
    mean: number;
    sampleStandardDeviation: number;
    confidenceLevel: number;
    confidenceIntervalLow: number;
    confidenceIntervalHigh: number;
  };
  totalEvaluationCount: number;
  totalWallTimeSeconds: number;
  runs: Array<{
    index: number;
    seed: number;
    quantumCandidateFeasible: boolean;
    objective: number;
    candidateObjective: number;
    evaluationCount: number;
    wallTimeSeconds: number;
    selected: boolean;
    diagnosticDisplaySource: string;
  }>;
}

export interface RunResponse {
  scenario: ScenarioSpec;
  preset: string;
  run: WorkbenchRunPayload;
}

export interface ScenarioRequest {
  preset: string;
  values: Record<string, string | number | boolean>;
}

export interface ExperimentConfigurationRequest {
  mode?: Mode | "recommended";
  algorithm?: Algorithm;
  layers?: number;
  shots?: number;
  parameter_budget?: number;
  optimizer_starts?: number;
}

export interface AnalysisRequest extends ScenarioRequest {
  experimentLevel?: ExperimentLevel;
  complexityProfile?: ComplexityLevel;
  configurations?: ExperimentConfigurationRequest[];
  seeds?: number[];
  sweep?: {
    parameter: string;
    values: Array<string | number>;
  };
}

export interface RunRequest extends ScenarioRequest {
  mode: Mode;
  algorithm: Algorithm;
  layer_policy: LayerPolicy;
  shots: number;
  seed: number;
  layers: number;
  max_layers: number;
  min_improvement: number;
  search_strategy: SearchStrategy;
  parameter_budget: number;
  optimizer_starts?: number;
  repeats?: number;
}
