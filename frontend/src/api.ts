import type {
  AnalyzeResponse,
  RunRequest,
  RunResponse,
  ScenarioRequest,
  ScenarioSpec,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(payload?.detail ?? `请求失败：HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function getScenarios(): Promise<ScenarioSpec[]> {
  const payload = await request<{ scenarios: ScenarioSpec[] }>("/api/scenarios");
  return payload.scenarios;
}

export function analyzeScenario(
  caseId: string,
  body: ScenarioRequest,
  signal?: AbortSignal,
): Promise<AnalyzeResponse> {
  return request(`/api/scenarios/${caseId}/analyze`, {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  });
}

export function runScenario(
  caseId: string,
  body: RunRequest,
): Promise<RunResponse> {
  return request(`/api/scenarios/${caseId}/run`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
