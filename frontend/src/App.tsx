import { AlertTriangle, LoaderCircle, RadioTower } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import {
  analyzeScenario,
  cancelScenarioJob,
  createScenarioJob,
  getScenarioJob,
  getScenarios,
  runScenario,
} from "./api";
import { ControlPanel } from "./components/ControlPanel";
import { QuantumText } from "./components/QuantumText";
import { ScenarioNav } from "./components/ScenarioNav";
import { TelemetryHeader } from "./components/TelemetryHeader";
import { viewTabs, type ViewId } from "./components/viewTabs";
import { I18nProvider, useI18n } from "./i18n";
import type {
  Algorithm,
  AnalysisPayload,
  BiomedicineAnalysisPayload,
  BiomedicineRunPayload,
  DomainId,
  ExecutionProfile,
  ExperimentLevel,
  ExperimentPlan,
  LayerPolicy,
  Mode,
  LocalJob,
  MaterialsAnalysisPayload,
  RunPayload,
  RunRequest,
  ScenarioSpec,
  SearchStrategy,
  WorkbenchAnalysisPayload,
  WorkbenchRunPayload,
} from "./types";
import {
  estimateExecutionSeconds,
  executionSignature,
  MODE_LABELS,
  type ExecutionIdentity,
} from "./utils";

const BusinessView = lazy(() =>
  import("./components/Views").then((module) => ({ default: module.BusinessView })),
);
const ScenarioView = lazy(() =>
  import("./components/Views").then((module) => ({ default: module.ScenarioView })),
);
const MappingView = lazy(() =>
  import("./components/Views").then((module) => ({ default: module.MappingView })),
);
const QuantumView = lazy(() =>
  import("./components/Views").then((module) => ({ default: module.QuantumView })),
);
const AuditView = lazy(() =>
  import("./components/Views").then((module) => ({ default: module.AuditView })),
);
const BiomedicineResultView = lazy(() =>
  import("./components/BiomedicineViews").then((module) => ({
    default: module.BiomedicineResultView,
  })),
);
const BiomedicineStructureView = lazy(() =>
  import("./components/BiomedicineViews").then((module) => ({
    default: module.BiomedicineStructureView,
  })),
);
const BiomedicineMappingView = lazy(() =>
  import("./components/BiomedicineViews").then((module) => ({
    default: module.BiomedicineMappingView,
  })),
);
const BiomedicineQuantumView = lazy(() =>
  import("./components/BiomedicineViews").then((module) => ({
    default: module.BiomedicineQuantumView,
  })),
);
const BiomedicineAuditView = lazy(() =>
  import("./components/BiomedicineViews").then((module) => ({
    default: module.BiomedicineAuditView,
  })),
);
const BiomedicineComparisonView = lazy(() =>
  import("./components/BiomedicineViews").then((module) => ({
    default: module.BiomedicineComparisonView,
  })),
);
const MaterialsView = lazy(() =>
  import("./components/MaterialsViews").then((module) => ({
    default: module.MaterialsView,
  })),
);

const DEFAULT_EXECUTION_PROFILE: ExecutionProfile = {
  shots: 32,
  seed: 23,
  algorithm: "recommended",
  layerPolicy: "fixed",
  layers: 1,
  maxLayers: 3,
  minImprovement: 0,
  searchStrategy: "preset",
  parameterBudget: 2,
  optimizerStarts: 1,
  repeats: 1,
};

function executionProfile(scenario: ScenarioSpec): ExecutionProfile {
  return scenario.recommendedExecution ?? DEFAULT_EXECUTION_PROFILE;
}

function sameValues(
  left: Record<string, string | number | boolean>,
  right: Record<string, string | number | boolean>,
) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function isBiomedicineAnalysis(
  analysis: WorkbenchAnalysisPayload,
): analysis is BiomedicineAnalysisPayload {
  return "kind" in analysis && analysis.kind === "biomedicine";
}

function isMaterialsAnalysis(
  analysis: WorkbenchAnalysisPayload,
): analysis is MaterialsAnalysisPayload {
  return "kind" in analysis && analysis.kind === "materials";
}

function isBiomedicineRun(run: WorkbenchRunPayload): run is BiomedicineRunPayload {
  return "kind" in run && run.kind === "biomedicine";
}

function cacheIdentity(
  analysis: WorkbenchAnalysisPayload | null,
  scenario: ScenarioSpec | null,
): ExecutionIdentity {
  if (
    analysis &&
    (isBiomedicineAnalysis(analysis) || isMaterialsAnalysis(analysis))
  ) {
    return {
      datasetVersion: analysis.dataset.version,
      manifestHash: analysis.dataset.manifestHash,
      executionFamily: analysis.executionFamily,
    };
  }
  return { executionFamily: scenario?.executionFamily };
}

function analyzeForDomain(
  domainId: DomainId,
  caseId: string,
  body: import("./types").AnalysisRequest,
  signal?: AbortSignal,
) {
  return domainId === "finance"
    ? analyzeScenario(caseId, body, signal)
    : analyzeScenario(caseId, body, signal, domainId);
}

function runForDomain(domainId: DomainId, caseId: string, request: RunRequest) {
  return domainId === "finance"
    ? runScenario(caseId, request)
    : runScenario(caseId, request, domainId);
}

function ViewLoading() {
  const { t } = useI18n();
  return (
    <div className="view-module-loading" role="status">
      <LoaderCircle className="spin" size={20} aria-hidden="true" />
      <span>{t("loadingView")}</span>
    </div>
  );
}

function Workbench() {
  const { scenario: localizeScenario, t, tx } = useI18n();
  const [domainId, setDomainId] = useState<DomainId>("finance");
  const [scenarios, setScenarios] = useState<ScenarioSpec[]>([]);
  const [activeId, setActiveId] = useState("");
  const [preset, setPreset] = useState("");
  const [values, setValues] = useState<Record<string, string | number | boolean>>({});
  const [analysis, setAnalysis] = useState<WorkbenchAnalysisPayload | null>(null);
  const [experimentLevel, setExperimentLevel] = useState<ExperimentLevel>("standard");
  const [experimentPlan, setExperimentPlan] = useState<ExperimentPlan | null>(null);
  const [job, setJob] = useState<LocalJob | null>(null);
  const [mode, setMode] = useState<Mode>("digital");
  const [algorithm, setAlgorithm] = useState<Algorithm>("recommended");
  const [layerPolicy, setLayerPolicy] = useState<LayerPolicy>("fixed");
  const [shots, setShots] = useState(32);
  const [seed, setSeed] = useState(23);
  const [layers, setLayers] = useState(1);
  const [maxLayers, setMaxLayers] = useState(3);
  const [minImprovement, setMinImprovement] = useState(0);
  const [searchStrategy, setSearchStrategy] = useState<SearchStrategy>("preset");
  const [parameterBudget, setParameterBudget] = useState(2);
  const [optimizerStarts, setOptimizerStarts] = useState(1);
  const [repeats, setRepeats] = useState(1);
  const [activeView, setActiveView] = useState<ViewId>("scenario");
  const [run, setRun] = useState<WorkbenchRunPayload | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const revision = useRef(0);
  const suppressAnalysis = useRef(false);
  const cache = useRef(new Map<string, WorkbenchRunPayload>());
  const catalogs = useRef(new Map<DomainId, ScenarioSpec[]>());
  const lastScenario = useRef<Record<DomainId, string>>({
    finance: "",
    biomedicine: "",
    materials: "",
  });

  const activeScenario = useMemo(
    () => scenarios.find((scenario) => scenario.caseId === activeId) ?? null,
    [activeId, scenarios],
  );
  const localizedScenarios = useMemo(
    () => scenarios.map(localizeScenario),
    [localizeScenario, scenarios],
  );
  const displayedScenario = useMemo(
    () => (activeScenario ? localizeScenario(activeScenario) : null),
    [activeScenario, localizeScenario],
  );
  const selectedDecision = useMemo(
    () => analysis?.decision.modes.find((item) => item.mode === mode) ?? null,
    [analysis, mode],
  );

  function applyExecutionProfile(profile: ExecutionProfile) {
    setShots(profile.shots);
    setSeed(profile.seed);
    setAlgorithm(profile.algorithm ?? "recommended");
    setLayerPolicy(profile.layerPolicy ?? "fixed");
    setLayers(profile.layers);
    setMaxLayers(profile.maxLayers ?? 3);
    setMinImprovement(profile.minImprovement ?? 0);
    setSearchStrategy(profile.searchStrategy);
    setParameterBudget(profile.parameterBudget);
    setOptimizerStarts(profile.optimizerStarts ?? 1);
    setRepeats(profile.repeats ?? 1);
  }

  useEffect(() => {
    let mounted = true;
    getScenarios()
      .then((items) => {
        if (!mounted) return;
        setScenarios(items);
        catalogs.current.set("finance", items);
        const first = items[0];
        setActiveId(first.caseId);
        setPreset(first.presets[0].value);
        setValues(first.values);
        setMode(first.recommendedMode);
        applyExecutionProfile(executionProfile(first));
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => mounted && setCatalogLoading(false));
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!activeId || !preset || suppressAnalysis.current) {
      suppressAnalysis.current = false;
      return;
    }
    const controller = new AbortController();
    const currentRevision = ++revision.current;
    const timer = window.setTimeout(() => {
      setAnalyzing(true);
      setError(null);
      const advancedRequest = experimentLevel === "advanced" ? {
        experimentLevel,
        complexityProfile: "advanced_live" as const,
        configurations: [{
          mode,
          algorithm,
          layers,
          shots,
          parameter_budget: parameterBudget,
          optimizer_starts: optimizerStarts,
        }],
        seeds: [seed, seed + 16, seed + 34].slice(0, Math.max(2, repeats)),
      } : {};
      analyzeForDomain(
        domainId,
        activeId,
        { preset, values, ...advancedRequest },
        controller.signal,
      )
        .then((response) => {
          if (currentRevision !== revision.current) return;
          setAnalysis(response.analysis);
          setExperimentPlan(response.experimentPlan ?? null);
          setValues((current) =>
            sameValues(current, response.scenario.values)
              ? current
              : response.scenario.values,
          );
          const available = response.analysis.decision.modes.filter(
            (item) => item.status !== "unsuitable",
          );
          setMode((current) =>
            available.some((item) => item.mode === current)
              ? current
              : response.analysis.decision.recommendedMode,
          );
        })
        .catch((reason: Error) => {
          if (reason.name !== "AbortError") setError(reason.message);
        })
        .finally(() => {
          if (currentRevision === revision.current) setAnalyzing(false);
        });
    }, 180);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [
    activeId,
    algorithm,
    domainId,
    experimentLevel,
    layers,
    mode,
    optimizerStarts,
    parameterBudget,
    preset,
    repeats,
    seed,
    shots,
    values,
  ]);

  const currentRequest = useMemo<RunRequest | null>(() => {
    if (!activeId || !preset) return null;
    const resolvedAlgorithm =
      algorithm === "recommended"
        ? mode === "analog"
          ? "qaa"
          : "qaoa"
        : algorithm;
    const effectiveLayers = mode === "analog" ? 1 : layers;
    const effectiveMaxLayers =
      mode === "analog"
        ? 1
        : Math.min(maxLayers, resolvedAlgorithm === "vqe" || mode === "hybrid" ? 2 : 3);
    const effectiveSearchStrategy =
      layerPolicy === "adaptive" || resolvedAlgorithm === "vqe"
        ? "continuous"
        : mode === "digital" || searchStrategy === "continuous"
          ? searchStrategy
          : "preset";
    const parameterLayers = layerPolicy === "adaptive" ? effectiveMaxLayers : effectiveLayers;
    const parameterCount =
      resolvedAlgorithm === "vqe"
        ? (analysis?.problem.variables.length ?? 1) * parameterLayers
        : resolvedAlgorithm === "qaoa"
          ? 2 * parameterLayers
          : 2;
    const continuousMinimum = parameterCount + 2;
    return {
      preset,
      values,
      mode,
      algorithm,
      layer_policy: mode === "analog" ? "fixed" : layerPolicy,
      shots,
      seed,
      layers: effectiveLayers,
      max_layers: effectiveMaxLayers,
      min_improvement: minImprovement,
      search_strategy: effectiveSearchStrategy,
      parameter_budget:
        effectiveSearchStrategy === "continuous"
          ? Math.max(parameterBudget, continuousMinimum)
          : mode === "digital" && effectiveSearchStrategy !== "preset"
          ? parameterBudget
          : Math.min(parameterBudget, 2),
      optimizer_starts: effectiveSearchStrategy === "continuous" ? optimizerStarts : 1,
      repeats,
    };
  }, [
    activeId,
    algorithm,
    analysis,
    layerPolicy,
    layers,
    maxLayers,
    minImprovement,
    mode,
    optimizerStarts,
    parameterBudget,
    preset,
    searchStrategy,
    seed,
    shots,
    repeats,
    values,
  ]);

  const recommendedConfiguration = useMemo(() => {
    if (!activeScenario || !currentRequest) return false;
    const profile = executionProfile(activeScenario);
    const recommendedMode =
      analysis?.decision.recommendedMode ?? activeScenario.recommendedMode;
    return (
      mode === recommendedMode &&
      currentRequest.shots === profile.shots &&
      currentRequest.seed === profile.seed &&
      currentRequest.algorithm === (profile.algorithm ?? "recommended") &&
      currentRequest.layer_policy === (profile.layerPolicy ?? "fixed") &&
      currentRequest.layers === profile.layers &&
      currentRequest.max_layers === (profile.maxLayers ?? 3) &&
      currentRequest.min_improvement === (profile.minImprovement ?? 0) &&
      currentRequest.search_strategy === profile.searchStrategy &&
      currentRequest.parameter_budget === profile.parameterBudget &&
      currentRequest.optimizer_starts === (profile.optimizerStarts ?? 1) &&
      currentRequest.repeats === (profile.repeats ?? 1)
    );
  }, [activeScenario, analysis, currentRequest, mode]);

  const currentExecutionIdentity = useMemo(
    () => cacheIdentity(analysis, activeScenario),
    [activeScenario, analysis],
  );
  const estimatedSeconds = useMemo(
    () =>
      currentRequest
        ? estimateExecutionSeconds(activeScenario?.recommendedExecution, currentRequest)
        : null,
    [activeScenario, currentRequest],
  );

  useEffect(() => {
    if (!currentRequest) return;
    setRun(
      cache.current.get(
        executionSignature(domainId, activeId, currentRequest, currentExecutionIdentity),
      ) ?? null,
    );
  }, [activeId, currentExecutionIdentity, currentRequest, domainId]);

  function selectScenario(scenario: ScenarioSpec) {
    lastScenario.current[domainId] = scenario.caseId;
    setActiveId(scenario.caseId);
    setPreset(scenario.presets[0].value);
    setValues(scenario.values);
    setMode(scenario.recommendedMode);
    applyExecutionProfile(executionProfile(scenario));
    setAnalysis(null);
    setExperimentLevel("standard");
    setExperimentPlan(null);
    setRun(null);
    setActiveView("scenario");
    setError(null);
    window.history.replaceState(null, "", `/${domainId}/${scenario.caseId}`);
  }

  async function selectDomain(nextDomain: DomainId) {
    if (nextDomain === domainId) return;
    lastScenario.current[domainId] = activeId;
    const currentRevision = ++revision.current;
    setCatalogLoading(true);
    setError(null);
    try {
      let items = catalogs.current.get(nextDomain);
      if (!items) {
        items = await getScenarios(nextDomain);
        catalogs.current.set(nextDomain, items);
      }
      if (currentRevision !== revision.current) return;
      const remembered = lastScenario.current[nextDomain];
      const scenario = items.find((item) => item.caseId === remembered) ?? items[0];
      if (!scenario) throw new Error(t("emptyCatalog"));
      setDomainId(nextDomain);
      setScenarios(items);
      setActiveId(scenario.caseId);
      setPreset(scenario.presets[0].value);
      setValues(scenario.values);
      setMode(scenario.recommendedMode);
      applyExecutionProfile(executionProfile(scenario));
      setAnalysis(null);
      setExperimentLevel("standard");
      setExperimentPlan(null);
      setRun(null);
      setActiveView("scenario");
      window.history.replaceState(null, "", `/${nextDomain}/${scenario.caseId}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      if (currentRevision === revision.current) setCatalogLoading(false);
    }
  }

  async function selectPreset(nextPreset: string) {
    if (!activeScenario) return;
    const currentRevision = ++revision.current;
    suppressAnalysis.current = true;
    setActiveView("scenario");
    setPreset(nextPreset);
    setAnalyzing(true);
    setError(null);
    try {
      const response = await analyzeForDomain(
        domainId,
        activeScenario.caseId,
        {
          preset: nextPreset,
          values: {},
          ...(experimentLevel === "advanced"
            ? {
                experimentLevel,
                complexityProfile: "advanced_live" as const,
                configurations: [{
                  mode,
                  algorithm,
                  layers,
                  shots,
                  parameter_budget: parameterBudget,
                  optimizer_starts: optimizerStarts,
                }],
                seeds: [seed, seed + 16],
              }
            : {}),
        },
      );
      if (currentRevision !== revision.current) return;
      setValues(response.scenario.values);
      setAnalysis(response.analysis);
      setExperimentPlan(response.experimentPlan ?? null);
      setMode(response.analysis.decision.recommendedMode);
      applyExecutionProfile(executionProfile(response.scenario));
      setRun(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      if (currentRevision === revision.current) setAnalyzing(false);
    }
  }

  async function execute() {
    if (!activeScenario || !currentRequest) return;
    setRunning(true);
    setError(null);
    try {
      if (
        domainId === "biomedicine" &&
        experimentLevel === "advanced" &&
        experimentPlan?.executionPolicy === "job"
      ) {
        const configurations = [{
          mode,
          algorithm,
          layers,
          shots,
          parameter_budget: parameterBudget,
          optimizer_starts: optimizerStarts,
        }];
        const seeds = [seed, seed + 16, seed + 34].slice(
          0,
          Math.max(2, repeats),
        );
        const created = await createScenarioJob(activeScenario.caseId, {
          preset,
          values,
          experimentLevel,
          complexityProfile: "advanced_live",
          configurations,
          seeds,
          planId: experimentPlan.planId,
        });
        setJob(created.job);
        let current = created.job;
        while (["queued", "running"].includes(current.status)) {
          await new Promise((resolve) => window.setTimeout(resolve, 500));
          current = (await getScenarioJob(current.jobId)).job;
          setJob(current);
        }
        return;
      }
      const response = await runForDomain(
        domainId,
        activeScenario.caseId,
        currentRequest,
      );
      setAnalysis(response.run.analysis);
      setRun(response.run);
      cache.current.set(
        executionSignature(
          domainId,
          activeScenario.caseId,
          currentRequest,
          cacheIdentity(response.run.analysis, activeScenario),
        ),
        response.run,
      );
      setActiveView("business");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRunning(false);
    }
  }

  if (catalogLoading) {
    return (
      <main className="boot-screen">
        <RadioTower size={34} strokeWidth={1.3} aria-hidden="true" />
        <strong>{t("productTitle")}</strong>
        <span>{t("loadingService")}</span>
        <LoaderCircle className="spin" size={20} aria-hidden="true" />
      </main>
    );
  }

  if (!activeScenario) {
    return (
      <main className="boot-screen error-screen">
        <AlertTriangle size={32} aria-hidden="true" />
        <strong>{t("loadFailed")}</strong>
        <span>{error ?? t("emptyCatalog")}</span>
      </main>
    );
  }

  const biomedicineAnalysis =
    analysis && isBiomedicineAnalysis(analysis) ? analysis : null;
  const biomedicineRun = run && isBiomedicineRun(run) ? run : null;
  const materialsAnalysis =
    analysis && isMaterialsAnalysis(analysis) ? analysis : null;
  const financeAnalysis =
    analysis &&
    !isBiomedicineAnalysis(analysis) &&
    !isMaterialsAnalysis(analysis)
      ? (analysis as AnalysisPayload)
      : null;
  const financeRun = run && !isBiomedicineRun(run) ? (run as RunPayload) : null;
  const displayedShots = run
    ? isBiomedicineRun(run)
      ? "shots" in run.audit
        ? run.audit.shots
        : run.audit.shotsPerGroup
      : run.audit.shots
    : null;
  const visibleTabs =
    domainId !== "finance"
      ? viewTabs
      : viewTabs.filter((tab) => tab.id !== "comparison");

  return (
    <div className="app-shell-react">
      <TelemetryHeader domainId={domainId} onDomain={selectDomain} />
      <div className="workbench-grid">
        <ScenarioNav
          scenarios={localizedScenarios}
          activeId={activeId}
          onSelect={selectScenario}
          domainId={domainId}
        />
        <ControlPanel
          scenario={displayedScenario ?? activeScenario}
          preset={preset}
          values={values}
          analysis={analysis}
          experimentLevel={experimentLevel}
          experimentPlan={experimentPlan}
          mode={mode}
          algorithm={algorithm}
          layerPolicy={layerPolicy}
          shots={shots}
          seed={seed}
          layers={layers}
          maxLayers={maxLayers}
          searchStrategy={searchStrategy}
          parameterBudget={parameterBudget}
          optimizerStarts={optimizerStarts}
          repeats={repeats}
          recommendedConfiguration={recommendedConfiguration}
          estimatedSeconds={estimatedSeconds}
          running={running}
          analyzing={analyzing}
          canRun={
            activeScenario.implementationStatus !== "preview" &&
            (experimentLevel === "standard" ||
              experimentPlan?.executionPolicy === "job")
          }
          onPreset={selectPreset}
          onExperimentLevel={(value) => {
            setExperimentLevel(value);
            setExperimentPlan(null);
            setRun(null);
          }}
          onValue={(key, value) => {
            setActiveView("scenario");
            setValues((current) => ({ ...current, [key]: value }));
          }}
          onMode={(value) => {
            setMode(value);
            setAlgorithm("recommended");
            if (value === "analog") setLayerPolicy("fixed");
            if (
              value !== "digital" &&
              searchStrategy !== "preset" &&
              searchStrategy !== "continuous"
            ) {
              setSearchStrategy("preset");
              setParameterBudget((current) => Math.min(current, 2));
            }
          }}
          onShots={setShots}
          onSeed={setSeed}
          onAlgorithm={(value) => {
            setAlgorithm(value);
            if (value === "vqe") {
              setSearchStrategy("continuous");
              setLayers((current) => Math.min(current, 2));
              setMaxLayers((current) => Math.min(current, 2));
              setParameterBudget((current) => Math.max(current, 12));
            }
          }}
          onLayerPolicy={(value) => {
            setLayerPolicy(value);
            if (value === "adaptive") {
              setSearchStrategy("continuous");
              setParameterBudget((current) => Math.max(current, 8));
            }
          }}
          onLayers={(value) => {
            setLayers(value);
            if (value !== 1 && searchStrategy === "grid") {
              setSearchStrategy("seeded_sample");
            }
          }}
          onMaxLayers={setMaxLayers}
          onSearchStrategy={(value) => {
            setSearchStrategy(value);
            if (value === "preset") setParameterBudget((current) => Math.min(current, 2));
            if (value === "grid") setLayers(1);
            if (value === "continuous") setParameterBudget((current) => Math.max(current, 4));
          }}
          onParameterBudget={setParameterBudget}
          onOptimizerStarts={setOptimizerStarts}
          onRepeats={setRepeats}
          onRun={execute}
          onReset={() => selectPreset(activeScenario.presets[0].value)}
        />
        <main className={`result-workspace accent-${activeScenario.accent}`}>
          <header className="scenario-header">
            <div>
              <span className="scenario-eyebrow"><QuantumText text={displayedScenario?.eyebrow ?? ""} /></span>
              <h1>{displayedScenario?.title}</h1>
              <p>{displayedScenario?.description}</p>
            </div>
            <div className="scenario-status">
              <span className="mode-orbit" data-mode={mode} aria-hidden="true">
                <i />
              </span>
              <div>
                <small>{run ? t("lastExecution") : analyzing ? t("analyzingStatus") : mode === analysis?.decision.recommendedMode ? t("recommendedPath") : t("comparisonPath")}</small>
                <strong><QuantumText text={MODE_LABELS[run?.quantum.mode ?? mode]} /></strong>
                <span>{run ? `${run.audit.wallTimeSeconds.toFixed(3)}s / ${displayedShots} shots` : tx(selectedDecision?.reason ?? analysis?.decision.reason ?? "")}</span>
              </div>
            </div>
          </header>

          {error ? (
            <div className="error-banner" role="alert">
              <AlertTriangle size={16} aria-hidden="true" />
              <span>{tx(error)}</span>
            </div>
          ) : null}

          {job && domainId === "biomedicine" && job.caseId === activeId ? (
            <section className="data-section" aria-label="高级实验任务">
              <div className="subsection-head">
                <div><span className="section-kicker">EXPERIMENT MATRIX</span><h3>高级实验运行单元</h3></div>
                <span className="data-chip">{job.status.toUpperCase()}</span>
              </div>
              {job.status === "queued" && job.canCancelPending ? (
                <button
                  className="icon-text-button"
                  type="button"
                  onClick={async () => {
                    try {
                      setJob((await cancelScenarioJob(job.jobId)).job);
                    } catch (reason) {
                      setError(reason instanceof Error ? reason.message : String(reason));
                    }
                  }}
                >
                  取消排队任务
                </button>
              ) : null}
              <div className="table-wrap">
                <table className="data-table compact-table">
                  <thead><tr><th>Point</th><th>Config</th><th>Seed</th><th>Status</th><th>Report</th></tr></thead>
                  <tbody>
                    {job.runs.map((item) => (
                      <tr key={item.runId}>
                        <td>{item.pointIndex + 1}</td>
                        <td>{item.configurationIndex + 1}</td>
                        <td>{item.seed}</td>
                        <td>{item.status}</td>
                        <td className="mono">{item.reportHash ? item.reportHash.slice(0, 12) : "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="subsection-note">
                {job.progress.completed}/{job.progress.total} 完成，{job.progress.succeeded} 成功，{job.progress.failed} 失败。运行单元结果保持独立，不自动替换为经典参考。
              </p>
            </section>
          ) : null}

          <nav className={`view-tabs view-tabs-${visibleTabs.length}`} aria-label={t("resultsView")} role="tablist">
            {visibleTabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  type="button"
                  key={tab.id}
                  id={`view-tab-${tab.id}`}
                  role="tab"
                  aria-selected={activeView === tab.id}
                  aria-controls="view-panel"
                  onClick={() => setActiveView(tab.id)}
                >
                  <Icon size={15} aria-hidden="true" />
                  <span>{t(tab.labelKey)}</span>
                </button>
              );
            })}
          </nav>

          <div
            className="view-stage"
            id="view-panel"
            role="tabpanel"
            aria-labelledby={`view-tab-${activeView}`}
            aria-busy={running || analyzing}
          >
            {running ? (
              <div className="execution-overlay">
                <span className="scan-line" aria-hidden="true" />
                <LoaderCircle className="spin" size={22} aria-hidden="true" />
                <strong><QuantumText text={MODE_LABELS[mode]} /></strong>
                <small>{t("compilingExecutingSampling")}</small>
              </div>
            ) : null}
            {analysis ? (
              <Suspense fallback={<ViewLoading />}>
                {materialsAnalysis ? (
                  <MaterialsView analysis={materialsAnalysis} view={activeView} />
                ) : biomedicineAnalysis ? (
                  <>
                    {activeView === "business" ? <BiomedicineResultView analysis={biomedicineAnalysis} run={biomedicineRun} /> : null}
                    {activeView === "scenario" ? <BiomedicineStructureView analysis={biomedicineAnalysis} /> : null}
                    {activeView === "mapping" ? <BiomedicineMappingView analysis={biomedicineAnalysis} /> : null}
                    {activeView === "quantum" ? <BiomedicineQuantumView run={biomedicineRun} mode={mode} /> : null}
                    {activeView === "comparison" ? <BiomedicineComparisonView analysis={biomedicineAnalysis} run={biomedicineRun} /> : null}
                    {activeView === "audit" ? <BiomedicineAuditView analysis={biomedicineAnalysis} run={biomedicineRun} /> : null}
                  </>
                ) : financeAnalysis ? (
                  <>
                    {activeView === "business" ? <BusinessView run={financeRun} mode={mode} /> : null}
                    {activeView === "scenario" ? <ScenarioView analysis={financeAnalysis} run={financeRun} /> : null}
                    {activeView === "mapping" ? <MappingView analysis={financeAnalysis} run={financeRun} /> : null}
                    {activeView === "quantum" ? <QuantumView run={financeRun} mode={mode} /> : null}
                    {activeView === "audit" ? <AuditView run={financeRun} mode={mode} /> : null}
                  </>
                ) : null}
              </Suspense>
            ) : (
              <div className="analysis-loading">
                <LoaderCircle className="spin" size={22} aria-hidden="true" />
                <span>{t("buildingMapping")}</span>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <I18nProvider>
      <Workbench />
    </I18nProvider>
  );
}
