import type { DomainId, ExecutionProfile, Mode, RunRequest, ScenarioSpec } from "./types";

export const MODE_LABELS: Record<Mode, string> = {
  digital: "DIGITAL",
  hybrid: "HYBRID D-A-D",
  analog: "ANALOG AHS",
};

export interface ExecutionIdentity {
  datasetVersion?: string;
  manifestHash?: string;
  executionFamily?: string;
}

export function scenarioControlValues(
  scenario: Pick<ScenarioSpec, "controls" | "values">,
): Record<string, string | number | boolean> {
  const controlKeys = new Set(scenario.controls.map((control) => control.key));
  return Object.fromEntries(
    Object.entries(scenario.values).filter(([key]) => controlKeys.has(key)),
  );
}

export function executionSignature(
  domainId: DomainId,
  caseId: string,
  request: RunRequest,
  identity: ExecutionIdentity = {},
): string {
  const values = Object.entries(request.values).sort(([left], [right]) =>
    left.localeCompare(right),
  );
  return JSON.stringify({ domainId, caseId, identity, ...request, values });
}

export function estimateExecutionSeconds(
  profile: ExecutionProfile | undefined,
  request: Pick<
    RunRequest,
    "shots" | "layers" | "max_layers" | "layer_policy" | "parameter_budget" | "optimizer_starts" | "repeats"
  >,
): number | null {
  if (!profile?.estimatedSeconds) return null;
  const profileLayers = profile.layerPolicy === "adaptive" ? profile.maxLayers ?? 1 : profile.layers;
  const requestLayers = request.layer_policy === "adaptive" ? request.max_layers : request.layers;
  const ratios = [
    request.shots / Math.max(1, profile.shots),
    request.parameter_budget / Math.max(1, profile.parameterBudget),
    (request.optimizer_starts ?? 1) / Math.max(1, profile.optimizerStarts ?? 1),
    (request.repeats ?? 1) / Math.max(1, profile.repeats ?? 1),
    requestLayers / Math.max(1, profileLayers),
  ];
  return profile.estimatedSeconds * ratios.reduce((total, ratio) => total * Math.max(0, ratio), 1);
}

export function compactId(value: string, length = 14): string {
  if (value.length <= length) return value;
  return `${value.slice(0, Math.max(4, length - 5))}…${value.slice(-4)}`;
}

export function numericResource(
  resource: Record<string, number | string | boolean>,
  key: string,
): number {
  const value = resource[key];
  return typeof value === "number" ? value : Number(value ?? 0);
}

export function termShares(
  analogTerms: number,
  digitalTerms: number,
): { analog: number; digital: number } {
  const analog = Math.max(0, analogTerms);
  const digital = Math.max(0, digitalTerms);
  const total = analog + digital;
  if (total === 0) return { analog: 0, digital: 0 };
  return {
    analog: (analog / total) * 100,
    digital: (digital / total) * 100,
  };
}
