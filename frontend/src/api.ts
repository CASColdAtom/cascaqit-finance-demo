import type {
  AnalyzeResponse,
  AnalysisRequest,
  CapabilitySnapshot,
  DomainId,
  RunRequest,
  RunResponse,
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
      detail?: string | { message?: string; code?: string };
    } | null;
    const detail = payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message ?? detail?.code ?? `请求失败：HTTP ${response.status}`;
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export async function getScenarios(domainId: DomainId = "finance"): Promise<ScenarioSpec[]> {
  const payload = await request<{ scenarios: ScenarioSpec[] }>(
    `/api/domains/${domainId}/scenarios`,
  );
  return payload.scenarios;
}

export function analyzeScenario(
  caseId: string,
  body: AnalysisRequest,
  signal?: AbortSignal,
  domainId: DomainId = "finance",
): Promise<AnalyzeResponse> {
  return request(`/api/domains/${domainId}/scenarios/${caseId}/analyze`, {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  });
}

export function getBiomedicineCapabilities(): Promise<CapabilitySnapshot> {
  return request("/api/domains/biomedicine/capabilities");
}

export function runScenario(
  caseId: string,
  body: RunRequest,
  domainId: DomainId = "finance",
): Promise<RunResponse> {
  return request(`/api/domains/${domainId}/scenarios/${caseId}/run`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
