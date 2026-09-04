import type {
  Scenario,
  OptimizedSchedule,
  ScoredJob,
  KPIReport,
  SystemEvent,
  AssetHealthRecord,
  NetworkGeometryResponse,
  PlanningCapabilitiesResponse,
  HealthResponse,
  AdvisoryProposal,
  ApprovalActionPayload,
  OperationalOverridePayload,
  AuditEventRecord
} from './types';
import { validateNetworkGeometryContract, GeometryContractError } from './geometryValidator';
import {
  mockScenario,
  mockSchedule,
  mockScoredJobs,
  mockKPIReport,
  mockEvents,
  mockAssetHealth,
  mockNetworkGeometry,
  mockPlanningCapabilities,
  mockAdvisoryProposals,
  mockAuditEvents
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

const demoAdvisoryProposals: AdvisoryProposal[] = [...mockAdvisoryProposals];

export const ApiClient = {
  isDemoMode(): boolean {
    return isDemoModeEnabled();
  },

  async getHealth(signal?: AbortSignal): Promise<HealthResponse> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 120));
      return {
        status: "ok",
        version: "1.0.0-demo",
        geometry_schema_version: "1.0.0",
        solver_available: true,
        solver_name: "PySCIPOpt (MIP Solver)",
        data_mode: "local_synthetic"
      };
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/health`, { signal });
    const data = await res.json();
    if (!data || typeof data !== 'object' || typeof data.status !== 'string') {
      throw new ApiError(502, "Invalid health response from backend API", data);
    }
    return data as HealthResponse;
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
      return validateNetworkGeometryContract(mockNetworkGeometry, true);
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/network/geometry`, { signal });
    const data = await res.json();
    try {
      return validateNetworkGeometryContract(data, false);
    } catch (err: unknown) {
      if (err instanceof GeometryContractError) {
        throw new ApiError(502, err.message, data);
      }
      throw err;
    }
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
  },

  async getAdvisoryProposals(signal?: AbortSignal): Promise<AdvisoryProposal[]> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 150));
      return [...demoAdvisoryProposals];
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/advisory/proposals`, { signal });
    const data = await res.json();
    if (!Array.isArray(data)) {
      throw new ApiError(502, "Invalid advisory proposals list response from backend", data);
    }
    return data;
  },

  async getAdvisoryProposal(proposalId: string, signal?: AbortSignal): Promise<AdvisoryProposal> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 150));
      const found = demoAdvisoryProposals.find((p) => p.optimization_run_id === proposalId);
      if (!found) throw new ApiError(404, `Proposal ${proposalId} not found`);
      return { ...found };
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/advisory/proposals/${proposalId}`, { signal });
    const data = await res.json();
    if (!data || typeof data.optimization_run_id !== 'string') {
      throw new ApiError(502, "Invalid advisory proposal details from backend", data);
    }
    return data;
  },

  async createAdvisoryProposal(
    params: { division_code?: string; horizon_hours?: number; freeze_week1?: boolean; dry_run?: boolean } = {},
    signal?: AbortSignal
  ): Promise<AdvisoryProposal> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 400));
      const newProposal: AdvisoryProposal = {
        ...mockAdvisoryProposals[0],
        optimization_run_id: `BDMS-PROP-${params.division_code || 'PRYJ'}-${Date.now().toString().slice(-6)}`,
        idempotency_key: `IDEMP-${Date.now()}`,
        division_code: params.division_code || "PRYJ",
        created_at: new Date().toISOString()
      };
      demoAdvisoryProposals.unshift(newProposal);
      return newProposal;
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/advisory/proposals`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
      signal
    });
    const data = await res.json();
    if (!data || typeof data.optimization_run_id !== 'string') {
      throw new ApiError(502, "Invalid proposal creation response from backend", data);
    }
    return data;
  },

  async approveProposal(proposalId: string, action: ApprovalActionPayload, signal?: AbortSignal): Promise<AdvisoryProposal> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 200));
      const prop = demoAdvisoryProposals.find((p) => p.optimization_run_id === proposalId);
      if (!prop) throw new ApiError(404, `Proposal ${proposalId} not found`);
      if (prop.approval_chain[action.role]) {
        prop.approval_chain[action.role] = {
          status: "APPROVED",
          approver_id: action.approver_id,
          approver_name: action.approver_name,
          comments: action.comments,
          timestamp: new Date().toISOString()
        };
      }
      const ctpc = prop.approval_chain["CTPC"]?.status;
      const srDom = prop.approval_chain["SR_DOM"]?.status;
      if (ctpc === "APPROVED" && srDom === "APPROVED") {
        prop.approval_status = "SANCTIONED";
        prop.recommended_blocks.forEach((b) => {
          b.lifecycle_state = "SANCTIONED";
        });
      }
      return { ...prop };
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/advisory/proposals/${proposalId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(action),
      signal
    });
    return res.json();
  },

  async rejectProposal(proposalId: string, action: ApprovalActionPayload, signal?: AbortSignal): Promise<AdvisoryProposal> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 200));
      const prop = demoAdvisoryProposals.find((p) => p.optimization_run_id === proposalId);
      if (!prop) throw new ApiError(404, `Proposal ${proposalId} not found`);
      prop.approval_status = "REJECTED";
      if (prop.approval_chain[action.role]) {
        prop.approval_chain[action.role] = {
          status: "REJECTED",
          approver_id: action.approver_id,
          approver_name: action.approver_name,
          comments: action.comments,
          timestamp: new Date().toISOString()
        };
      }
      prop.recommended_blocks.forEach((b) => {
        b.lifecycle_state = "REJECTED";
      });
      return { ...prop };
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/advisory/proposals/${proposalId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(action),
      signal
    });
    return res.json();
  },

  async overrideProposal(
    proposalId: string,
    payload: OperationalOverridePayload,
    signal?: AbortSignal
  ): Promise<{ status: string; proposal_id: string; overridden_by: string; reason_code: string; timestamp: string; updated_proposal: AdvisoryProposal }> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 250));
      const prop = demoAdvisoryProposals.find((p) => p.optimization_run_id === proposalId);
      if (!prop) throw new ApiError(404, `Proposal ${proposalId} not found`);
      prop.approval_status = "OVERRIDDEN";
      return {
        status: "OVERRIDE_RECORDED",
        proposal_id: proposalId,
        overridden_by: payload.user_id,
        reason_code: payload.reason_code,
        timestamp: new Date().toISOString(),
        updated_proposal: { ...prop }
      };
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/advisory/proposals/${proposalId}/override`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal
    });
    return res.json();
  },

  async getAuditTrail(limit = 100, signal?: AbortSignal): Promise<AuditEventRecord[]> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 120));
      return [...mockAuditEvents];
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/advisory/audit?limit=${limit}`, { signal });
    const data = await res.json();
    if (!Array.isArray(data)) {
      throw new ApiError(502, "Invalid audit trail response from backend", data);
    }
    return data;
  }
};
