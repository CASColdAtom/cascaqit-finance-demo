import type { DomainId, Mode, RunRequest } from "./types";

export const MODE_LABELS: Record<Mode, string> = {
  digital: "DIGITAL",
  hybrid: "HYBRID D-A-D",
  analog: "ANALOG AHS",
};

export function executionSignature(
  domainId: DomainId,
  caseId: string,
  request: RunRequest,
): string {
  const values = Object.entries(request.values).sort(([left], [right]) =>
    left.localeCompare(right),
  );
  return JSON.stringify({ domainId, caseId, ...request, values });
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
