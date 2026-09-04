import type {
  Scenario,
  OptimizedSchedule,
  ScoredJob,
  KPIReport,
  SystemEvent,
  AssetHealthRecord,
  NetworkGeometryResponse,
  PlanningCapabilitiesResponse
} from './types';
import {
  mockScenario,
  mockSchedule,
  mockScoredJobs,
  mockKPIReport,
  mockEvents,
  mockAssetHealth,
  mockNetworkGeometry,
  mockPlanningCapabilities
} from './mockData';

export class ApiError extends Error {
  status: number;
  statusText?: string;
  data?: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const override = localStorage.getItem('sparkrail_api_url');
    if (override) return override;
  }
  return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
}

export function setApiBaseUrl(url: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem('sparkrail_api_url', url);
  }
}

export function isDemoModeEnabled(): boolean {
  if (typeof window !== 'undefined') {
    const localVal = localStorage.getItem('sparkrail_demo_mode');
    if (localVal !== null) {
      return localVal === 'true';
    }
  }
  return import.meta.env.VITE_DEMO_MODE === 'true';
}

export function setDemoModeEnabled(enabled: boolean): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem('sparkrail_demo_mode', enabled ? 'true' : 'false');
  }
}

async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  retries = 2,
  backoffMs = 500
): Promise<Response> {
  try {
    const res = await fetch(url, options);
    if (!res.ok) {
      let errorBody: unknown;
      try {
        errorBody = await res.json();
      } catch {
        errorBody = await res.text();
      }
      throw new ApiError(res.status, `HTTP ${res.status}: ${res.statusText}`, errorBody);
    }
    return res;
  } catch (err: unknown) {
    if (err instanceof ApiError && err.status < 500) {
      // Client errors (4xx) should not be retried
      throw err;
    }
    if (retries > 0) {
      await new Promise((r) => setTimeout(r, backoffMs));
      return fetchWithRetry(url, options, retries - 1, backoffMs * 2);
    }
    throw err;
  }
}

export const ApiClient = {
  isDemoMode(): boolean {
    return isDemoModeEnabled();
  },

  async getHealth(signal?: AbortSignal): Promise<{ status: string; version: string }> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 120));
      return { status: "ok", version: "1.0.0-demo" };
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/health`, { signal });
    const data = await res.json();
    if (!data || typeof data !== 'object' || typeof data.status !== 'string') {
      throw new ApiError(502, "Invalid health response from backend API", data);
    }
    return data;
  },

  async generateData(signal?: AbortSignal): Promise<{ message: string }> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 400));
      return { message: "Synthetic dataset generated successfully in simulation memory" };
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/data/generate`, {
      method: 'POST',
      signal
    });
    const data = await res.json();
    if (!data || typeof data !== 'object' || typeof data.message !== 'string') {
      throw new ApiError(502, "Invalid response from data generation endpoint", data);
    }
    return data;
  },

  async getScenario(signal?: AbortSignal): Promise<Scenario> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 200));
      return mockScenario;
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/scenario`, { signal });
    const data = await res.json();
    if (!data || !Array.isArray(data.blocks) || !Array.isArray(data.jobs)) {
      throw new ApiError(502, "Invalid scenario response schema from backend", data);
    }
    return data;
  },

  async scoreJobs(signal?: AbortSignal): Promise<{ scored_jobs: ScoredJob[] }> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 250));
      return mockScoredJobs;
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/score`, {
      method: 'POST',
      signal
    });
    const data = await res.json();
    if (!data || !Array.isArray(data.scored_jobs)) {
      throw new ApiError(502, "Invalid scoring response schema from backend", data);
    }
    return data;
  },

  async optimizeSchedule(signal?: AbortSignal): Promise<OptimizedSchedule> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 600));
      return mockSchedule;
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/optimize`, {
      method: 'POST',
      signal
    });
    const data = await res.json();
    if (!data || typeof data.status !== 'string' || !Array.isArray(data.scheduled_jobs)) {
      throw new ApiError(502, "Invalid schedule optimization schema from backend", data);
    }
    return data;
  },

  async evaluateKPIs(signal?: AbortSignal): Promise<KPIReport> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 200));
      return mockKPIReport;
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/evaluate`, {
      method: 'POST',
      signal
    });
    const data = await res.json();
    if (!data || typeof data.bue_percent !== 'number') {
      throw new ApiError(502, "Invalid KPI evaluation schema from backend", data);
    }
    return data;
  },

  async getSchedule(scheduleId = "latest", signal?: AbortSignal): Promise<OptimizedSchedule> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 300));
      return mockSchedule;
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/schedule/${scheduleId}`, { signal });
    const data = await res.json();
    if (!data || typeof data.status !== 'string' || !Array.isArray(data.scheduled_jobs)) {
      throw new ApiError(502, "Invalid schedule response schema from backend", data);
    }
    return data;
  },

  async getAssetHealth(signal?: AbortSignal): Promise<AssetHealthRecord[]> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 180));
      return mockAssetHealth;
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/assets/health`, { signal });
    const data = await res.json();
    if (!Array.isArray(data)) {
      throw new ApiError(502, "Invalid asset health list response from backend", data);
    }
    return data;
  },

  async getEvents(signal?: AbortSignal): Promise<SystemEvent[]> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 150));
      return mockEvents;
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/events`, { signal });
    const data = await res.json();
    if (!Array.isArray(data)) {
      throw new ApiError(502, "Invalid events list response from backend", data);
    }
    return data;
  },

  async getNetworkGeometry(signal?: AbortSignal): Promise<NetworkGeometryResponse> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 180));
      return mockNetworkGeometry;
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/network/geometry`, { signal });
    const data = await res.json();
    if (!data || !Array.isArray(data.tracks) || !Array.isArray(data.nodes)) {
      throw new ApiError(502, "Invalid 3D network geometry response from backend", data);
    }
    return data;
  },

  async getPlanningCapabilities(signal?: AbortSignal): Promise<PlanningCapabilitiesResponse> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 100));
      return mockPlanningCapabilities;
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/planning/capabilities`, { signal });
    const data = await res.json();
    if (!data || typeof data.solver_name !== 'string') {
      throw new ApiError(502, "Invalid planning capabilities response from backend", data);
    }
    return data;
  }
};
