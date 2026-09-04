import { describe, it, expect, beforeEach } from 'vitest';
import { ApiClient } from '../api/client';
import type { ApprovalActionPayload, OperationalOverridePayload } from '../api/types';

describe('BDMS Advisory and Governance Frontend API Client', () => {
  beforeEach(() => {
    localStorage.setItem('sparkrail_demo_mode', 'true');
  });

  it('fetches advisory proposals in demo mode adhering to schema 1.0.0 and advisory flag', async () => {
    const proposals = await ApiClient.getAdvisoryProposals();
    expect(Array.isArray(proposals)).toBe(true);
    expect(proposals.length).toBeGreaterThan(0);

    const first = proposals[0];
    expect(first.schema_version).toBe('1.0.0');
    expect(first.advisory_mode).toBe('ADVISORY_ONLY_NOT_EXECUTED');
    expect(first.division_code).toBe('PRYJ');
    expect(first.safety_status).toBe('SAFETY_CERTIFIED');
    expect(first.approval_chain).toHaveProperty('CTPC');
    expect(first.approval_chain).toHaveProperty('SR_DOM');
    expect(first.recommended_blocks.length).toBeGreaterThan(0);
  });

  it('progresses the statutory approval chain when CTPC and SR_DOM sign off', async () => {
    const proposals = await ApiClient.getAdvisoryProposals();
    const propId = proposals[0].optimization_run_id;

    const ctpcAction: ApprovalActionPayload = {
      role: 'CTPC',
      approver_id: 'EMP-CTPC-01',
      approver_name: 'Chief Controller IR',
      decision: 'APPROVED',
      comments: 'Conforms to Zonal corridor possession window.'
    };

    const updatedAfterCtpc = await ApiClient.approveProposal(propId, ctpcAction);
    expect(updatedAfterCtpc.approval_chain['CTPC'].status).toBe('APPROVED');
    expect(updatedAfterCtpc.approval_chain['CTPC'].approver_name).toBe('Chief Controller IR');

    const srDomAction: ApprovalActionPayload = {
      role: 'SR_DOM',
      approver_id: 'EMP-SRDOM-01',
      approver_name: 'Senior DOM Prayagraj',
      decision: 'APPROVED',
      comments: 'Traffic path cleared, sanctioned.'
    };

    const updatedAfterSrDom = await ApiClient.approveProposal(propId, srDomAction);
    expect(updatedAfterSrDom.approval_chain['SR_DOM'].status).toBe('APPROVED');
    expect(updatedAfterSrDom.approval_status).toBe('SANCTIONED');
    expect(updatedAfterSrDom.recommended_blocks[0].lifecycle_state).toBe('SANCTIONED');
  });

  it('marks proposal and recommended blocks as REJECTED when rejected by controller', async () => {
    const proposals = await ApiClient.getAdvisoryProposals();
    const propId = proposals[0].optimization_run_id;

    const rejectAction: ApprovalActionPayload = {
      role: 'SECTION_CONTROLLER',
      approver_id: 'EMP-SC-02',
      approver_name: 'Section Controller Mirzapur',
      decision: 'REJECTED',
      comments: 'Conflicting unscheduled military freight rake.'
    };

    const updated = await ApiClient.rejectProposal(propId, rejectAction);
    expect(updated.approval_status).toBe('REJECTED');
    expect(updated.approval_chain['SECTION_CONTROLLER'].status).toBe('REJECTED');
    expect(updated.recommended_blocks[0].lifecycle_state).toBe('REJECTED');
  });

  it('records statutory operational override with mandatory justification', async () => {
    const proposals = await ApiClient.getAdvisoryProposals();
    const propId = proposals[0].optimization_run_id;

    const overridePayload: OperationalOverridePayload = {
      user_id: 'SR_DOM_OFFICER',
      role: 'SR_DOM',
      reason_code: 'EMERGENCY_DERAILMENT_RISK',
      justification: 'TRC-09 detected severe gauge variation on B6 requiring immediate track packing.',
      overridden_schedule: { recommended_blocks: proposals[0].recommended_blocks }
    };

    const result = await ApiClient.overrideProposal(propId, overridePayload);
    expect(result.status).toBe('OVERRIDE_RECORDED');
    expect(result.reason_code).toBe('EMERGENCY_DERAILMENT_RISK');
    expect(result.overridden_by).toBe('SR_DOM_OFFICER');
    expect(result.updated_proposal.approval_status).toBe('OVERRIDDEN');
  });

  it('retrieves tamper-evident audit trail entries', async () => {
    const auditTrail = await ApiClient.getAuditTrail(20);
    expect(Array.isArray(auditTrail)).toBe(true);
    expect(auditTrail.length).toBeGreaterThan(0);
    expect(auditTrail[0]).toHaveProperty('event_type');
    expect(auditTrail[0]).toHaveProperty('user_id');
    expect(auditTrail[0]).toHaveProperty('timestamp');
  });
});
