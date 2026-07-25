import { AlertTriangle, LoaderCircle, RadioTower } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { analyzeScenario, getScenarios, runScenario } from "./api";
import { ControlPanel } from "./components/ControlPanel";
import { ScenarioNav } from "./components/ScenarioNav";
import { TelemetryHeader } from "./components/TelemetryHeader";
import { viewTabs, type ViewId } from "./components/viewTabs";
import { I18nProvider, useI18n } from "./i18n";
import type {
  AnalysisPayload,
  ExecutionProfile,
  Mode,
  RunPayload,
  RunRequest,
  ScenarioSpec,
  SearchStrategy,
} from "./types";
import { executionSignature, MODE_LABELS } from "./utils";

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

function sameValues(
  left: Record<string, string | number | boolean>,
  right: Record<string, string | number | boolean>,
) {
  return JSON.stringify(left) === JSON.stringify(right);
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
  const [scenarios, setScenarios] = useState<ScenarioSpec[]>([]);
  const [activeId, setActiveId] = useState("");
  const [preset, setPreset] = useState("");
  const [values, setValues] = useState<Record<string, string | number | boolean>>({});
  const [analysis, setAnalysis] = useState<AnalysisPayload | null>(null);
  const [mode, setMode] = useState<Mode>("digital");
  const [shots, setShots] = useState(32);
  const [seed, setSeed] = useState(23);
  const [layers, setLayers] = useState(1);
  const [searchStrategy, setSearchStrategy] = useState<SearchStrategy>("preset");
  const [parameterBudget, setParameterBudget] = useState(2);
  const [activeView, setActiveView] = useState<ViewId>("scenario");
  const [run, setRun] = useState<RunPayload | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const revision = useRef(0);
  const suppressAnalysis = useRef(false);
  const cache = useRef(new Map<string, RunPayload>());

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
    setLayers(profile.layers);
    setSearchStrategy(profile.searchStrategy);
    setParameterBudget(profile.parameterBudget);
  }

  useEffect(() => {
    let mounted = true;
    getScenarios()
      .then((items) => {
        if (!mounted) return;
        setScenarios(items);
        const first = items[0];
        setActiveId(first.caseId);
        setPreset(first.presets[0].value);
        setValues(first.values);
        setMode(first.recommendedMode);
        applyExecutionProfile(first.recommendedExecution);
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
      analyzeScenario(activeId, { preset, values }, controller.signal)
        .then((response) => {
          if (currentRevision !== revision.current) return;
          setAnalysis(response.analysis);
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
  }, [activeId, preset, values]);

  const currentRequest = useMemo<RunRequest | null>(() => {
    if (!activeId || !preset) return null;
    return {
      preset,
      values,
      mode,
      shots,
      seed,
      layers: mode === "digital" ? layers : 1,
      search_strategy: mode === "digital" ? searchStrategy : "preset",
      parameter_budget:
        mode === "digital" && searchStrategy !== "preset"
          ? parameterBudget
          : Math.min(parameterBudget, 2),
    };
  }, [
    activeId,
    layers,
    mode,
    parameterBudget,
    preset,
    searchStrategy,
    seed,
    shots,
    values,
  ]);

  const recommendedConfiguration = useMemo(() => {
    if (!activeScenario || !currentRequest) return false;
    const profile = activeScenario.recommendedExecution;
    const recommendedMode =
      analysis?.decision.recommendedMode ?? activeScenario.recommendedMode;
    return (
      mode === recommendedMode &&
      currentRequest.shots === profile.shots &&
      currentRequest.seed === profile.seed &&
      currentRequest.layers === profile.layers &&
      currentRequest.search_strategy === profile.searchStrategy &&
      currentRequest.parameter_budget === profile.parameterBudget
    );
  }, [activeScenario, analysis, currentRequest, mode]);

  useEffect(() => {
    if (!currentRequest) return;
    setRun(cache.current.get(executionSignature(activeId, currentRequest)) ?? null);
  }, [activeId, currentRequest]);

  function selectScenario(scenario: ScenarioSpec) {
    setActiveId(scenario.caseId);
    setPreset(scenario.presets[0].value);
    setValues(scenario.values);
    setMode(scenario.recommendedMode);
    applyExecutionProfile(scenario.recommendedExecution);
    setAnalysis(null);
    setRun(null);
    setActiveView("scenario");
    setError(null);
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
      const response = await analyzeScenario(activeScenario.caseId, {
        preset: nextPreset,
        values: {},
      });
      if (currentRevision !== revision.current) return;
      setValues(response.scenario.values);
      setAnalysis(response.analysis);
      setMode(response.analysis.decision.recommendedMode);
      applyExecutionProfile(response.scenario.recommendedExecution);
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
      const response = await runScenario(activeScenario.caseId, currentRequest);
      setAnalysis(response.run.analysis);
      setRun(response.run);
      cache.current.set(
        executionSignature(activeScenario.caseId, currentRequest),
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

  return (
    <div className="app-shell-react">
      <TelemetryHeader />
      <div className="workbench-grid">
        <ScenarioNav
          scenarios={localizedScenarios}
          activeId={activeId}
          onSelect={selectScenario}
        />
        <ControlPanel
          scenario={displayedScenario ?? activeScenario}
          preset={preset}
          values={values}
          analysis={analysis}
          mode={mode}
          shots={shots}
          seed={seed}
          layers={layers}
          searchStrategy={searchStrategy}
          parameterBudget={parameterBudget}
          recommendedConfiguration={recommendedConfiguration}
          running={running}
          analyzing={analyzing}
          onPreset={selectPreset}
          onValue={(key, value) => {
            setActiveView("scenario");
            setValues((current) => ({ ...current, [key]: value }));
          }}
          onMode={setMode}
          onShots={setShots}
          onSeed={setSeed}
          onLayers={(value) => {
            setLayers(value);
            if (value !== 1 && searchStrategy === "grid") {
              setSearchStrategy("seeded_sample");
            }
          }}
          onSearchStrategy={(value) => {
            setSearchStrategy(value);
            if (value === "preset") setParameterBudget((current) => Math.min(current, 2));
            if (value === "grid") setLayers(1);
          }}
          onParameterBudget={setParameterBudget}
          onRun={execute}
          onReset={() => selectPreset(activeScenario.presets[0].value)}
        />
        <main className={`result-workspace accent-${activeScenario.accent}`}>
          <header className="scenario-header">
            <div>
              <span className="scenario-eyebrow">{displayedScenario?.eyebrow}</span>
              <h1>{displayedScenario?.title}</h1>
              <p>{displayedScenario?.description}</p>
            </div>
            <div className="scenario-status">
              <span className="mode-orbit" data-mode={mode} aria-hidden="true">
                <i />
              </span>
              <div>
                <small>{run ? t("lastExecution") : analyzing ? t("analyzingStatus") : mode === analysis?.decision.recommendedMode ? t("recommendedPath") : t("comparisonPath")}</small>
                <strong>{MODE_LABELS[run?.quantum.mode ?? mode]}</strong>
                <span>{run ? `${run.audit.wallTimeSeconds.toFixed(3)}s / ${run.audit.shots} shots` : tx(selectedDecision?.reason ?? analysis?.decision.reason ?? "")}</span>
              </div>
            </div>
          </header>

          {error ? (
            <div className="error-banner" role="alert">
              <AlertTriangle size={16} aria-hidden="true" />
              <span>{tx(error)}</span>
            </div>
          ) : null}

          <nav className="view-tabs" aria-label={t("resultsView")} role="tablist">
            {viewTabs.map((tab) => {
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
                <strong>{MODE_LABELS[mode]}</strong>
                <small>{t("compilingExecutingSampling")}</small>
              </div>
            ) : null}
            {analysis ? (
              <Suspense fallback={<ViewLoading />}>
                {activeView === "business" ? <BusinessView run={run} mode={mode} /> : null}
                {activeView === "scenario" ? <ScenarioView analysis={analysis} run={run} /> : null}
                {activeView === "mapping" ? <MappingView analysis={analysis} run={run} /> : null}
                {activeView === "quantum" ? <QuantumView run={run} mode={mode} /> : null}
                {activeView === "audit" ? <AuditView run={run} mode={mode} /> : null}
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
