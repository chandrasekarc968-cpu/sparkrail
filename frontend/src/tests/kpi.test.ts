import { describe, it, expect } from 'vitest';
import { mockKPIReport } from '../api/mockData';

describe('KPI Calculations & Metrics', () => {
  it('correctly reports Block Utilization Efficiency (BUE) exceeding 100% via multi-department consolidation', () => {
    expect(mockKPIReport.bue_percent).toBe(134.48);
    expect(mockKPIReport.bue_baseline_percent).toBe(100.0);
    expect(mockKPIReport.bue_percent).toBeGreaterThan(mockKPIReport.bue_baseline_percent);
  });

  it('demonstrates significant delay savings in Punctuality Impact Index (PII)', () => {
    expect(mockKPIReport.pii_delays).toBe(4.0);
    expect(mockKPIReport.pii_baseline_delays).toBe(42.0);
    const delayReduction = ((mockKPIReport.pii_baseline_delays - mockKPIReport.pii_delays) / mockKPIReport.pii_baseline_delays) * 100;
    expect(delayReduction).toBeGreaterThan(90);
  });

  it('verifies Shadow Block Ratio (SBR) and consolidated blocks', () => {
    expect(mockKPIReport.sbr_percent).toBe(17.65);
    expect(mockKPIReport.consolidated_blocks).toBe(3);
  });

  it('verifies total closure time reduction compared to baseline', () => {
    expect(mockKPIReport.total_closure_hours).toBe(29.0);
    expect(mockKPIReport.baseline_closure_hours).toBe(39.0);
    expect(mockKPIReport.total_closure_hours).toBeLessThan(mockKPIReport.baseline_closure_hours);
  });
});
