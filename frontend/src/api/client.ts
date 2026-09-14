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
  AuditEventRecord,
  WhatIfScenarioRequest,
  WhatIfScenarioResponse,
  BlockShiftRequest,
  BlockShiftResponse,
  AuthTokenResponse,
  UserProfile
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

export function getAuthToken(): string | null {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('sparkrail_access_token');
  }
  return null;
}

export function setAuthToken(token: string | null): void {
  if (typeof window !== 'undefined') {
    if (token) {
      localStorage.setItem('sparkrail_access_token', token);
    } else {
      localStorage.removeItem('sparkrail_access_token');
    }
  }
}

async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  retries = 2,
  backoffMs = 500
): Promise<Response> {
  try {
    const headers = new Headers(options.headers || {});
    const token = getAuthToken();
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    const finalOptions: RequestInit = {
      ...options,
      headers,
      credentials: options.credentials || 'include'
    };
    const res = await fetch(url, finalOptions);
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
    let res: Response;
    try {
      res = await fetchWithRetry(`${getApiBaseUrl()}/network/geometry/v1`, { signal });
    } catch {
      res = await fetchWithRetry(`${getApiBaseUrl()}/network/geometry`, { signal });
    }
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

  async getNetworkTopology(signal?: AbortSignal): Promise<unknown> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 120));
      return { division: "PRYJ", corridor: "Subedarganj - Mirzapur", directed: true, schema_version: "1.0.0" };
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/network/topology`, { signal });
    return res.json();
  },

  async queryNetworkTopology(query: { query_type: string; [key: string]: unknown }, signal?: AbortSignal): Promise<unknown> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 150));
      return { status: "success", query_type: query.query_type, result: [] };
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/network/topology/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(query),
      signal
    });
    return res.json();
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
      const sc = prop.approval_chain["SECTION_CONTROLLER"]?.status;
      const sm = prop.approval_chain["STATION_MASTER"]?.status;
      if (ctpc === "APPROVED" && srDom === "APPROVED" && sc === "APPROVED" && sm === "APPROVED") {
        prop.approval_status = "SANCTIONED";
        prop.recommended_blocks.forEach((b) => {
          b.lifecycle_state = "SANCTIONED";
        });
      } else {
        const nextRole = !ctpc || ctpc !== "APPROVED" ? "CTPC" : (!srDom || srDom !== "APPROVED" ? "SR_DOM" : (!sc || sc !== "APPROVED" ? "SECTION_CONTROLLER" : "STATION_MASTER"));
        prop.approval_status = `PENDING_${nextRole}_REVIEW`;
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
  },

  async getV1Health(signal?: AbortSignal): Promise<Record<string, unknown>> {
    if (this.isDemoMode()) {
      return {
        status: "ok",
        plugin_version: "1.0.0",
        mode: "synthetic",
        is_synthetic: true,
        is_shadow: false,
        is_live: false,
        geometry_schema_version: "1.0.0",
        solver_available: true,
        solver_mode: "CP-SAT / ALNS Deterministic Fallback",
        statutory_safety_rules: {
          advisory_only: true,
          zero_physical_actuation: true,
          active_possession_immutability: true,
          four_role_approval_enforced: true
        }
      };
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/api/v1/health`, { signal });
    return res.json();
  },

  async exportAdvisorySchedule(
    format: 'json' | 'csv' | 'html' | 'pdf' = 'json',
    runId?: string,
    signal?: AbortSignal
  ): Promise<string> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 150));
      if (format === 'json') {
        return JSON.stringify({
          advisory_notice: "ADVISORY ONLY: HUMAN APPROVAL REQUIRED",
          environment_status: "SYNTHETIC DEMO MODE",
          division_code: "PRYJ",
          corridor: "Subedarganj (SFG) - Mirzapur (MZP)",
          optimization_run_id: runId || "RUN-SYNTH-DEMO-01",
          primary_possession: {
            possession_id: "POSS-PRYJ-DEMO",
            track_section_id: "B1",
            scheduled_start: 0.0,
            scheduled_end: 4.0,
            status: "PROPOSED"
          },
          statutory_approvals: { CTPC: "PENDING", SR_DOM: "PENDING", SECTION_CONTROLLER: "PENDING", STATION_MASTER: "PENDING" },
          limitations: "SparkRail is advisory only. Physical railway commands strictly prohibited."
        }, null, 2);
      } else if (format === 'csv') {
        return `# ADVISORY ONLY: HUMAN APPROVAL REQUIRED\n# ENVIRONMENT: SYNTHETIC DEMO MODE\nPossession_ID,Track_Section,Start_Hr,End_Hr,Status\nPOSS-PRYJ-DEMO,B1,0.0,4.0,PROPOSED`;
      } else {
        return `<!DOCTYPE html><html><body><h1>ADVISORY ONLY: HUMAN APPROVAL REQUIRED</h1><p>Synthetic Demo Corridor Advisory Docket</p></body></html>`;
      }
    }
    const params = new URLSearchParams({ format });
    if (runId) params.append('run_id', runId);
    const res = await fetchWithRetry(`${getApiBaseUrl()}/api/v1/advisory/export?${params.toString()}`, { signal });
    return res.text();
  },

  async simulateWhatIf(
    req: WhatIfScenarioRequest,
    signal?: AbortSignal
  ): Promise<WhatIfScenarioResponse> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 150));
      return {
        status: "SUCCESS",
        run_id: `WIF-DEMO-${Date.now()}`,
        delta_report: {
          baseline_cumulative_delay_min: 20.0,
          what_if_cumulative_delay_min: 35.0,
          delta_cumulative_delay_min: 15.0,
          train_deltas: [
            {
              train_id: "T4",
              train_name: "BOXN Coal Freight Spl",
              category: "freight",
              baseline_delay_min: 15.0,
              what_if_delay_min: 30.0,
              delta_delay_min: 15.0,
              energy_loss_kwh: 301.4,
              crew_duty_exceeded: false
            }
          ],
          heavy_machine_productivity_delta_hours: 1.0,
          freight_rakes_regulated_count: 1,
          total_energy_loss_kwh: 301.4,
          total_fuel_cost_impact_inr: 2562.0,
          crew_hours_timeout_warnings: [],
          narrative_summary_en: "What-If Simulation Result: Injected changes introduce +15 min delay on 1 freight service. Traction kinetic energy loss: 301 kWh (~₹2,562). Machine window change: +1.0h.",
          narrative_summary_hi: "वॉट-इफ सिमुलेशन परिणाम: प्रस्तावित परिवर्तन से 1 मालगाड़ी में +15 मिनट का अतिरिक्त विलंब। पुन: गति पकड़ने में अनुमानित 301 kWh बिजली (~₹2,562) खर्च होगी। मशीन समय: +1.0 घंटा।"
        },
        what_if_schedule: mockSchedule as unknown as Record<string, unknown>,
        conflicts_count: 0
      };
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/api/v1/simulation/scenario`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
      signal
    });
    return res.json();
  },

  async evaluateBlockShift(
    req: BlockShiftRequest,
    signal?: AbortSignal
  ): Promise<BlockShiftResponse> {
    if (this.isDemoMode()) {
      await new Promise((r) => setTimeout(r, 100));
      const shiftMins = req.shift_minutes ?? (req.shift_hours ? req.shift_hours * 60 : 0);
      const shiftH = shiftMins / 60.0;
      const newStart = 10.0 + shiftH;
      const newEnd = 12.0 + shiftH;
      const addedDelay = shiftMins > 45 ? 12.0 : 0.0;
      const conflictsCount = shiftMins > 45 ? 1 : 0;
      return {
        job_id: req.job_id,
        block_id: "B4",
        original_start_hours: 10.0,
        new_start_hours: newStart,
        new_end_hours: newEnd,
        is_feasible: true,
        conflict_count: conflictsCount,
        delta_delay_min: addedDelay,
        conflicts: conflictsCount > 0 ? [{ type: "TRAIN_CONFLICT", detail: "Overlap with BOXN Freight" }] : [],
        bilingual_advisory: {
          en: `Shifted Block ${req.job_id} by ${shiftMins > 0 ? '+' : ''}${shiftMins} mins. Added delay: ${addedDelay > 0 ? '12 mins' : '0 mins'}.`,
          hi: `ब्लॉक ${req.job_id} को ${shiftMins > 0 ? '+' : ''}${shiftMins} मिनट खिसकाया गया। अतिरिक्त विलंब: ${addedDelay > 0 ? '12 मिनट' : '0 मिनट'}।`
        },
        new_start_time: newStart,
        new_end_time: newEnd,
        added_delay_minutes: addedDelay,
        is_viable: true,
        recommendation: addedDelay > 0 ? "Viable with minor freight regulation." : "Viable with zero train conflicts."
      };
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/api/v1/simulation/evaluate-shift`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
      signal
    });
    return res.json();
  },

  async getXaiBriefing(signal?: AbortSignal): Promise<{ en: string; hi: string }> {
    if (this.isDemoMode()) {
      return {
        en: "SparkRail Decision-Support: 18 maintenance blocks coordinated across 8 sections. Zero Class-1 passenger disruptions. 4 multi-department shadow possessions active.",
        hi: "स्पार्क-रेल निर्णय-सहायता: 8 सेक्शनों में 18 रखरखाव ब्लॉक समन्वित। प्रीमियम यात्री सेवाओं पर शून्य प्रभाव। 4 बहु-विभागीय शैडो ब्लॉक सक्रिय।"
      };
    }
    const res = await fetchWithRetry(`${getApiBaseUrl()}/api/v1/simulation/xai-briefing`, { signal });
    return res.json();
  },

  async login(identifier: string, password: string, signal?: AbortSignal): Promise<AuthTokenResponse> {
    const res = await fetchWithRetry(`${getApiBaseUrl()}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier, password }),
      signal
    });
    const data: AuthTokenResponse = await res.json();
    if (data?.access_token) {
      setAuthToken(data.access_token);
    }
    return data;
  },

  async refresh(signal?: AbortSignal): Promise<AuthTokenResponse> {
    const res = await fetchWithRetry(`${getApiBaseUrl()}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal
    });
    const data: AuthTokenResponse = await res.json();
    if (data?.access_token) {
      setAuthToken(data.access_token);
    }
    return data;
  },

  async logout(signal?: AbortSignal): Promise<void> {
    try {
      await fetchWithRetry(`${getApiBaseUrl()}/api/v1/auth/logout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal
      });
    } finally {
      setAuthToken(null);
    }
  },

  async getMe(signal?: AbortSignal): Promise<UserProfile> {
    const res = await fetchWithRetry(`${getApiBaseUrl()}/api/v1/auth/me`, { signal });
    return res.json();
  }
};
