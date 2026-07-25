import { ChevronDown, Play, RotateCcw, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import type {
  AnalysisPayload,
  ControlSpec,
  Mode,
  ScenarioSpec,
  SearchStrategy,
} from "../types";
import { MODE_LABELS } from "../utils";
import { useI18n } from "../i18n";

interface ControlPanelProps {
  scenario: ScenarioSpec;
  preset: string;
  values: Record<string, string | number | boolean>;
  analysis: AnalysisPayload | null;
  mode: Mode;
  shots: number;
  seed: number;
  layers: number;
  searchStrategy: SearchStrategy;
  parameterBudget: number;
  recommendedConfiguration: boolean;
  running: boolean;
  analyzing: boolean;
  onPreset: (value: string) => void;
  onValue: (key: string, value: string | number) => void;
  onMode: (mode: Mode) => void;
  onShots: (value: number) => void;
  onSeed: (value: number) => void;
  onLayers: (value: number) => void;
  onSearchStrategy: (value: SearchStrategy) => void;
  onParameterBudget: (value: number) => void;
  onRun: () => void;
  onReset: () => void;
}

function ControlField({
  control,
  value,
  onValue,
}: {
  control: ControlSpec;
  value: string | number | boolean;
  onValue: (value: string | number) => void;
}) {
  const { language } = useI18n();
  if (control.kind === "select") {
    return (
      <label className="control-field">
        <span>{control.label}</span>
        <select value={String(value)} onChange={(event) => onValue(event.target.value)}>
          {control.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    );
  }
  return (
    <label className="control-field range-field">
      <span>
        {control.label}
        <output>
          {Number(value).toLocaleString(language === "zh" ? "zh-CN" : "en-US", { maximumFractionDigits: 3 })}
          {control.unit}
        </output>
      </span>
      <input
        type="range"
        min={control.minimum ?? undefined}
        max={control.maximum ?? undefined}
        step={control.step ?? undefined}
        value={Number(value)}
        onChange={(event) => onValue(Number(event.target.value))}
      />
      <span className="range-scale" aria-hidden="true">
        <small>{control.minimum}</small>
        <small>{control.maximum}</small>
      </span>
    </label>
  );
}

export function ControlPanel(props: ControlPanelProps) {
  const { t, tx } = useI18n();
  const modes = props.analysis?.decision.modes ?? [];
  const selectedMode = modes.find((item) => item.mode === props.mode);
  const [expanded, setExpanded] = useState(false);
  return (
    <aside className="control-panel-react" data-expanded={expanded}>
      <button
        className="control-collapse"
        type="button"
        aria-expanded={expanded}
        aria-controls="control-panel-body"
        onClick={() => setExpanded((current) => !current)}
      >
        <span>
          <SlidersHorizontal size={15} aria-hidden="true" />
          <strong>{props.scenario.shortTitle}</strong>
          <small>{t("parametersAndExecution")}</small>
        </span>
        <ChevronDown size={18} aria-hidden="true" />
      </button>
      <div className="control-heading">
        <span className="section-kicker">
          <SlidersHorizontal size={14} aria-hidden="true" /> {t("experimentInput")}
        </span>
        <h2>{props.scenario.shortTitle}</h2>
      </div>

      <div className="control-panel-body" id="control-panel-body">

        <label className="control-field preset-field">
          <span>{t("demoPreset")}</span>
          <select value={props.preset} onChange={(event) => props.onPreset(event.target.value)}>
            {props.scenario.presets.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <div className="control-stack">
          {props.scenario.controls.map((control) => (
            <ControlField
              control={control}
              key={control.key}
              value={props.values[control.key] ?? ""}
              onValue={(value) => props.onValue(control.key, value)}
            />
          ))}
        </div>

        <div className="execution-controls">
          <div className="execution-control-heading">
            <span className="section-kicker">{t("executionMode")}</span>
            <span
              className="execution-profile-status"
              data-recommended={props.recommendedConfiguration}
            >
              <i aria-hidden="true" />
              {props.recommendedConfiguration
                ? t("recommendedConfiguration")
                : t("customConfiguration")}
            </span>
          </div>
          <div className="mode-segments" role="group" aria-label={t("executionMode")}>
            {(["digital", "hybrid", "analog"] as Mode[]).map((candidate) => {
              const row = modes.find((item) => item.mode === candidate);
              const unavailable = row?.status === "unsuitable";
              return (
                <button
                  type="button"
                  key={candidate}
                  disabled={unavailable}
                  aria-pressed={props.mode === candidate}
                  onClick={() => props.onMode(candidate)}
                  data-tip={unavailable && row?.reason ? tx(row.reason) : undefined}
                >
                  {candidate.slice(0, 1).toUpperCase()}
                  <small>{candidate}</small>
                </button>
              );
            })}
          </div>
          <div className="mode-readout">
            <span>{MODE_LABELS[props.mode]}</span>
            <small>{tx(selectedMode?.reason ?? props.analysis?.decision.reason ?? t("buildingMapping"))}</small>
          </div>

          <div className="compact-controls">
            <label>
              <span>Shots</span>
              <select value={props.shots} onChange={(event) => props.onShots(Number(event.target.value))}>
                {[16, 32, 64, 128].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Seed</span>
              <select value={props.seed} onChange={(event) => props.onSeed(Number(event.target.value))}>
                {[7, 19, 23, 41].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
            {props.mode === "digital" ? (
              <>
                <label>
                  <span>{t("qaoaLayers")}</span>
                  <select
                    value={props.layers}
                    onChange={(event) => props.onLayers(Number(event.target.value))}
                  >
                    {[1, 2, 3].map((value) => (
                      <option key={value} value={value}>p = {value}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>{t("searchMethod")}</span>
                  <select
                    value={props.searchStrategy}
                    onChange={(event) =>
                      props.onSearchStrategy(event.target.value as SearchStrategy)
                    }
                  >
                    <option value="preset">{t("presetSearch")}</option>
                    <option value="grid" disabled={props.layers !== 1}>
                      {t("gridSearch")}
                    </option>
                    <option value="seeded_sample">{t("seededSearch")}</option>
                  </select>
                </label>
                <label>
                  <span>{t("evaluationBudget")}</span>
                  <select
                    value={props.parameterBudget}
                    onChange={(event) => props.onParameterBudget(Number(event.target.value))}
                  >
                    {(props.searchStrategy === "preset"
                      ? [1, 2]
                      : [2, 4, 8, 12, 16, 24]
                    ).map((value) => (
                      <option key={value} value={value}>{value}</option>
                    ))}
                  </select>
                </label>
              </>
            ) : null}
          </div>

          <div className="run-actions">
            <button className="run-button" type="button" onClick={props.onRun} disabled={props.running || props.analyzing}>
              <Play size={17} fill="currentColor" aria-hidden="true" />
              {props.running ? t("running") : props.analyzing ? t("analyzing") : t("runExperiment")}
            </button>
            <button className="icon-button" type="button" onClick={props.onReset} aria-label={t("resetScenario")} data-tip={t("resetScenario")}>
              <RotateCcw size={17} aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}
