import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiClient, ApiError, isDemoModeEnabled, setDemoModeEnabled } from '../api/client';

describe('ApiClient', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('correctly reports demo mode enabled by default or via setter', () => {
    setDemoModeEnabled(true);
    expect(isDemoModeEnabled()).toBe(true);
    expect(ApiClient.isDemoMode()).toBe(true);

    setDemoModeEnabled(false);
    expect(isDemoModeEnabled()).toBe(false);
    expect(ApiClient.isDemoMode()).toBe(false);

    // Reset to demo mode
    setDemoModeEnabled(true);
  });

  it('returns deterministic scenario data in demo mode with 8 blocks and 20 jobs', async () => {
    setDemoModeEnabled(true);
    const scenario = await ApiClient.getScenario();
    expect(scenario.blocks).toHaveLength(8);
    expect(scenario.jobs).toHaveLength(20);
    expect(scenario.trains).toHaveLength(10);
    expect(scenario.fixed_blocks).toHaveLength(2);
  });

  it('returns optimal schedule in demo mode with SCIP solver and scheduled jobs', async () => {
    setDemoModeEnabled(true);
    const schedule = await ApiClient.getSchedule();
    expect(schedule.status).toBe('optimal');
    expect(schedule.scheduled_jobs.length).toBeGreaterThanOrEqual(18);
    expect(schedule.kpi_metrics?.bue_percent).toBeGreaterThan(100);
  });

  it('scores jobs deterministically using multi-attribute TCI formula', async () => {
    setDemoModeEnabled(true);
    const scored = await ApiClient.scoreJobs();
    expect(scored.scored_jobs).toHaveLength(20);
    const criticalJob = scored.scored_jobs.find((j) => j.job_id === 'J18');
    expect(criticalJob?.tci).toBeGreaterThan(80);
    expect(criticalJob?.explanation.safety_component).toBeDefined();
  });

  it('throws typed ApiError when real API returns non-200 in non-demo mode', async () => {
    setDemoModeEnabled(false);

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable',
      json: async () => ({ detail: 'SCIP Solver busy' })
    } as unknown as Response);

    await expect(ApiClient.getHealth()).rejects.toThrow(ApiError);

    // Reset to demo mode
    setDemoModeEnabled(true);
  });
});
