import { ApiError } from "@/lib/errors";
import type { CompareResponse, ProviderCondition, ReportResponse, ScenarioListResponse } from "@/lib/types";

const LOCAL_API = "http://localhost:8000";

/** Public API origin with no trailing slash. Null in a production build that forgot the variable. */
export function apiBaseUrl(): string | null {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim().replace(/\/$/, "");
  if (configured) return configured;
  if (process.env.NODE_ENV === "production") return null;
  return LOCAL_API;
}

export async function fetchScenarios(): Promise<ScenarioListResponse> {
  return request<ScenarioListResponse>("/api/scenarios");
}

export async function fetchReport(scenarioId: string): Promise<ReportResponse> {
  return request<ReportResponse>(`/api/scenarios/${encodeURIComponent(scenarioId)}/report`);
}

export async function compareScenario(
  scenarioId: string,
  providerCondition: ProviderCondition,
): Promise<CompareResponse> {
  return request<CompareResponse>(`/api/scenarios/${encodeURIComponent(scenarioId)}/compare`, {
    method: "POST",
    body: JSON.stringify({ provider_condition: providerCondition }),
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const base = apiBaseUrl();
  if (!base) {
    throw new ApiError(
      "This build has no API address. Set NEXT_PUBLIC_API_BASE_URL when building the frontend.",
      { unreachable: true },
    );
  }
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(unreachableMessage(base), { unreachable: true });
  }

  if (!response.ok) {
    throw new ApiError((await readDetail(response)) ?? `The API returned status ${response.status}.`, {
      status: response.status,
    });
  }

  return (await response.json()) as T;
}

function unreachableMessage(base: string): string {
  const lead = `This page could not reach the API at ${base}.`;
  if (process.env.NODE_ENV === "production") return lead;
  return `${lead} Start it from the project root, then reload. If it is already running, open this page at http://localhost:3000.`;
}

async function readDetail(response: Response): Promise<string | null> {
  try {
    const body: unknown = await response.json();
    if (!body || typeof body !== "object" || !("detail" in body)) return null;
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (!Array.isArray(detail)) return null;
    const messages = detail
      .map((item) => {
        if (!item || typeof item !== "object" || !("msg" in item)) return null;
        const msg = (item as { msg: unknown }).msg;
        return typeof msg === "string" ? msg : null;
      })
      .filter((msg): msg is string => Boolean(msg));
    return messages.length > 0 ? messages.join(" ") : null;
  } catch {
    return null;
  }
}
