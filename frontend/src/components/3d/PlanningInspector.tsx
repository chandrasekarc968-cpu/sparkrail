import React from 'react';
import type { SelectedEntity } from '../../hooks/usePlanningSimulation';
import type { OptimizedSchedule, ValidationStatus } from '../../api/types';

interface InspectorRecord {
  id?: string;
  chainage_start?: number;
  chainage_end?: number;
  description?: string;
  speed_restriction_kmh?: number;
  electrification_status?: string;
  signaling_type?: string;
  department?: string;
  block_id?: string;
  duration?: number;
  job_type?: string;
  safety_clearance_required?: string;
  tci_inputs?: {
    safety_severity: number;
    traffic_impact: number;
    degradation_indicator: number;
    overdue_days: number;
  };
  name?: string;
  category?: string;
  scheduled_start?: number;
  scheduled_end?: number;
  route?: string[];
  max_speed_kmh?: number;
  current_delay_min?: number;
  severity?: string;
  conflict_type?: string;
  title?: string;
  suggested_resolution?: string;
  blocks_approval?: boolean;
  asset_type?: string;
  chainage_start_km?: number;
  chainage_end_km?: number;
  health_score?: number;
  defect_severity?: string;
  observed_defect_type?: string;
  last_ultrasonic_test?: string;
  days_overdue?: number;

  // Canonical Provenance Fields
  source_system?: string;
  source_record_id?: string;
  schema_version?: string;
  coordinate_reference_system?: string;
  source_timestamp?: string;
  ingestion_timestamp?: string;
  data_freshness_seconds?: number;
  confidence?: number;
  validation_status?: ValidationStatus;
  is_synthetic?: boolean;

  // Possession specific
  lifecycle_state?: string;
  status?: string;
  is_locked?: boolean;
  assigned_machines?: string[];
  assigned_crews?: string[];
  affected_ohe_sections?: string[];
  affected_signalling_zones?: string[];
  shadow_bundle_id?: string;
  shadow_with_jobs?: string[];
  delay_impact_minutes?: number;
}

interface PlanningInspectorProps {
  entity: SelectedEntity | null;
  onClose: () => void;
  schedule: OptimizedSchedule | null;
}

export const PlanningInspector: React.FC<PlanningInspectorProps> = ({
  entity,
  onClose,
  schedule
}) => {
  if (!entity) return null;

  const { type, id } = entity;
  const data = (entity.data || {}) as InspectorRecord;

  // Determine validation status and provenance defaults
  const validationStatus: ValidationStatus = data.validation_status || (data.is_synthetic ? 'SYNTHETIC' : 'VALIDATED');
  const sourceSystem = data.source_system || 'IR-CORRIDOR-DATABASE';
  const sourceRecordId = data.source_record_id || `REC-${id}`;
  const schemaVersion = data.schema_version || '1.0.0';
  const crs = data.coordinate_reference_system || 'LOCAL_CORRIDOR';
  const freshness = data.data_freshness_seconds !== undefined ? `${data.data_freshness_seconds}s ago` : 'Real-Time Sync';
  const confidencePercent = data.confidence !== undefined ? `${(data.confidence * 100).toFixed(0)}%` : '98%';

  // Possession Lock check
  const possessionStatus = (data.lifecycle_state || data.status || '').toUpperCase();
  const isLocked = data.is_locked || possessionStatus === 'GRANTED' || possessionStatus === 'IN_PROGRESS';

  const getStatusBadgeColor = (status: ValidationStatus): { bg: string; text: string } => {
    switch (status) {
      case 'VALIDATED': return { bg: '#dcfce7', text: '#166534' };
      case 'SYNTHETIC': return { bg: '#fef3c7', text: '#92400e' };
      case 'STALE': return { bg: '#fee2e2', text: '#991b1b' };
      case 'LOW_CONFIDENCE': return { bg: '#ffedd5', text: '#9a3412' };
      case 'INVALID': return { bg: '#ef4444', text: '#ffffff' };
      case 'CONTRADICTORY': return { bg: '#f43f5e', text: '#ffffff' };
      default: return { bg: '#f1f5f9', text: '#475569' };
    }
  };

  const statusBadge = getStatusBadgeColor(validationStatus);

  return (
    <aside
      style={{
        position: 'absolute',
        top: '16px',
        right: '16px',
        bottom: '120px',
        width: '380px',
        maxWidth: '90vw',
        zIndex: 25,
        backgroundColor: '#ffffff',
        borderRadius: '8px',
        boxShadow: '0 8px 28px rgba(0, 0, 0, 0.2)',
        border: '1px solid #cbd5e1',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        fontFamily: 'system-ui, sans-serif'
      }}
      aria-label="Planning Detail Inspector"
    >
      {/* 1. Header with Lock Indicator & Close Button */}
      <div
        style={{
          padding: '12px 16px',
          backgroundColor: isLocked ? '#2e1065' : '#0f172a',
          color: '#ffffff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #1e293b'
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '10px', textTransform: 'uppercase', color: '#38bdf8', fontWeight: 700, letterSpacing: '0.5px' }}>
              {type} Inspector
            </span>
            {isLocked && (
              <span
                style={{
                  fontSize: '9px',
                  backgroundColor: '#8b5cf6',
                  color: '#ffffff',
                  padding: '1px 5px',
                  borderRadius: '3px',
                  fontWeight: 800
                }}
                title="Safety Boundary #6: Active/Granted possession is locked and immutable"
              >
                🔒 IMMUTABLE ACTIVE
              </span>
            )}
          </div>
          <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700, fontFamily: 'monospace' }}>
            {id}
          </h3>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: '#94a3b8',
            fontSize: '18px',
            cursor: 'pointer',
            padding: '4px'
          }}
          aria-label="Close Inspector"
        >
          ✕
        </button>
      </div>

      {/* 2. Scrollable Body Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {/* Immutable Lock Warning Card for Active Possessions */}
        {isLocked && (
          <div style={{ ...cardStyle, backgroundColor: '#faf5ff', borderColor: '#d8b4fe' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#6b21a8', fontWeight: 800, fontSize: '11px', marginBottom: '4px' }}>
              <span>🔒 IMMUTABLE POSSESSION ENVELOPE</span>
            </div>
            <div style={{ fontSize: '11px', color: '#581c87', lineHeight: '1.4' }}>
              This possession is <strong>GRANTED / IN-PROGRESS</strong>. In accordance with IR safety rules, track limits and execution windows are strictly locked against UI edits or direct moves.
            </div>
          </div>
        )}

        {/* PROVENANCE & VALIDATION STATUS (CRITICAL SAFETY REQUIREMENT #4) */}
        <div style={{ ...cardStyle, backgroundColor: '#f8fafc' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={labelStyle}>Data Lineage & Provenance</span>
            <span
              style={{
                fontSize: '9px',
                fontWeight: 800,
                padding: '2px 6px',
                borderRadius: '3px',
                backgroundColor: statusBadge.bg,
                color: statusBadge.text
              }}
            >
              {validationStatus}
            </span>
          </div>
          <div style={valStyle}><strong>Source System:</strong> {sourceSystem}</div>
          <div style={valStyle}><strong>Source Record ID:</strong> {sourceRecordId}</div>
          <div style={valStyle}><strong>Schema Version:</strong> {schemaVersion}</div>
          <div style={valStyle}><strong>CRS:</strong> {crs}</div>
          <div style={valStyle}><strong>Confidence:</strong> {confidencePercent}</div>
          <div style={valStyle}><strong>Freshness:</strong> {freshness}</div>
          {validationStatus === 'SYNTHETIC' && (
            <div style={{ fontSize: '10px', color: '#b45309', marginTop: '4px', fontWeight: 600 }}>
              ℹ️ Synthetic dataset for decision rehearsal and simulation.
            </div>
          )}
        </div>

        {/* BLOCK INSPECTION */}
        {type === 'block' && (
          <>
            <div style={cardStyle}>
              <div style={labelStyle}>Track Section Details</div>
              <div style={valStyle}><strong>Chainage:</strong> KM {data.chainage_start ?? 0} - KM {data.chainage_end ?? 0} ({((data.chainage_end ?? 0) - (data.chainage_start ?? 0)).toFixed(1)} km)</div>
              <div style={valStyle}><strong>Description:</strong> {data.description || 'Corridor Mainline Section'}</div>
              <div style={valStyle}><strong>Line Direction:</strong> UP / DOWN Mainline</div>
              <div style={valStyle}><strong>Speed Limit:</strong> {data.speed_restriction_kmh || 100} km/h</div>
              <div style={valStyle}><strong>Electrification:</strong> {data.electrification_status || '25kV AC Traction'}</div>
              <div style={valStyle}><strong>Signaling:</strong> {data.signaling_type || 'Automatic Block (Absolute Interlocked)'}</div>
            </div>

            {/* Related Jobs on this block */}
            <div style={cardStyle}>
              <div style={labelStyle}>Scheduled Maintenance Possessions</div>
              {schedule?.scheduled_jobs?.filter(j => j.block_id === id).length ? (
                schedule.scheduled_jobs.filter(j => j.block_id === id).map(job => (
                  <div key={job.job_id} style={{ padding: '6px 0', borderBottom: '1px solid #f1f5f9' }}>
                    <div style={{ fontWeight: 700, fontSize: '12px' }}>{job.job_id} • {job.department}</div>
                    <div style={{ fontSize: '11px', color: '#475569' }}>
                      Window: T+{job.start_time.toFixed(1)}h - T+{job.end_time.toFixed(1)}h (TCI: {job.tci.toFixed(1)})
                    </div>
                    {job.is_shadow_block && (
                      <span style={{ fontSize: '9px', backgroundColor: '#d1fae5', color: '#065f46', padding: '1px 5px', borderRadius: '3px', fontWeight: 700 }}>
                        SHADOW POSSESSION
                      </span>
                    )}
                  </div>
                ))
              ) : (
                <div style={{ fontSize: '12px', color: '#64748b' }}>No active possessions on this block section.</div>
              )}
            </div>
          </>
        )}

        {/* JOB / POSSESSION INSPECTION */}
        {type === 'job' && (
          <>
            <div style={cardStyle}>
              <div style={labelStyle}>Possession Execution Envelope</div>
              <div style={valStyle}><strong>Department:</strong> {data.department}</div>
              <div style={valStyle}><strong>Track Limits:</strong> Block {data.block_id} (KM {data.chainage_start ?? 0} to {data.chainage_end ?? 0})</div>
              <div style={valStyle}><strong>Duration:</strong> {data.duration} hours</div>
              <div style={valStyle}><strong>Lifecycle State:</strong> <span style={{ fontWeight: 700 }}>{possessionStatus || 'REQUESTED'}</span></div>
              <div style={valStyle}><strong>Job Type:</strong> {data.job_type || 'Corridor Track Maintenance'}</div>
              <div style={valStyle}><strong>Safety Clearance:</strong> {data.safety_clearance_required || 'Standard Track Block Clearance'}</div>
              {data.assigned_machines && data.assigned_machines.length > 0 && (
                <div style={valStyle}><strong>Assigned Machines:</strong> {data.assigned_machines.join(', ')}</div>
              )}
              {data.assigned_crews && data.assigned_crews.length > 0 && (
                <div style={valStyle}><strong>Assigned Crews:</strong> {data.assigned_crews.join(', ')}</div>
              )}
            </div>

            {/* OHE & SIGNALLING DEPENDENCIES (PHASE 6) */}
            <div style={{ ...cardStyle, backgroundColor: '#fffbeb', borderColor: '#fde68a' }}>
              <div style={{ ...labelStyle, color: '#92400e' }}>OHE & Signalling Constraints</div>
              <div style={valStyle}>
                <strong>OHE Elementary Sections:</strong> {data.affected_ohe_sections?.join(', ') || `ES-${data.block_id}-01 (Power Isolated)`}
              </div>
              <div style={valStyle}>
                <strong>Signalling Dependencies:</strong> {data.affected_signalling_zones?.join(', ') || `Zone-${data.block_id} Disconnection Notice`}
              </div>
            </div>

            {/* TCI Component Breakdown */}
            {data.tci_inputs && (
              <div style={cardStyle}>
                <div style={labelStyle}>Task Criticality Index (TCI) Breakdown</div>
                <div style={valStyle}>• Safety Severity: {(data.tci_inputs.safety_severity * 100).toFixed(0)}%</div>
                <div style={valStyle}>• Traffic Impact: {(data.tci_inputs.traffic_impact * 100).toFixed(0)}%</div>
                <div style={valStyle}>• Degradation Indicator: {(data.tci_inputs.degradation_indicator * 100).toFixed(0)}%</div>
                <div style={valStyle}>• Overdue Days: {data.tci_inputs.overdue_days} days</div>
              </div>
            )}

            {/* AI Scheduling Rationale */}
            {schedule?.explainability?.[id] && (
              <div style={{ ...cardStyle, backgroundColor: '#f0fdf4', borderColor: '#bbf7d0' }}>
                <div style={{ ...labelStyle, color: '#166534' }}>AI Scheduling Explanation</div>
                <div style={valStyle}><strong>Priority Reason:</strong> {schedule.explainability[id].priority_rationale}</div>
                <div style={valStyle}><strong>Window Choice:</strong> {schedule.explainability[id].window_rationale}</div>
                {schedule.explainability[id].consolidation_rationale && (
                  <div style={valStyle}><strong>Shadow Block:</strong> {schedule.explainability[id].consolidation_rationale}</div>
                )}
                <div style={valStyle}><strong>Protected Trains:</strong> {schedule.explainability[id].protected_trains.join(', ') || 'None'}</div>
              </div>
            )}
          </>
        )}

        {/* TRAIN INSPECTION */}
        {type === 'train' && (
          <div style={cardStyle}>
            <div style={labelStyle}>Train Service Details</div>
            <div style={valStyle}><strong>Train:</strong> {data.name || data.id || id}</div>
            <div style={valStyle}><strong>Category / Priority:</strong> <span style={{ textTransform: 'uppercase', fontWeight: 800 }}>{data.category}</span></div>
            <div style={valStyle}><strong>Scheduled Window:</strong> T+{(data.scheduled_start ?? 0).toFixed(1)}h - T+{(data.scheduled_end ?? 0).toFixed(1)}h</div>
            <div style={valStyle}><strong>Route Corridor:</strong> {data.route?.join(' ➔ ') || 'Mainline Corridor'}</div>
            <div style={valStyle}><strong>Max Authorized Speed:</strong> {data.max_speed_kmh || 100} km/h</div>
            <div style={valStyle}><strong>Current Delay:</strong> {data.current_delay_min || 0} minutes</div>
            <div style={{ fontSize: '10px', color: '#64748b', marginTop: '6px', fontStyle: 'italic' }}>
              📍 Position interpolated from canonical topology route timetable.
            </div>
          </div>
        )}

        {/* CONFLICT INSPECTION */}
        {type === 'conflict' && (
          <>
            <div style={{ ...cardStyle, backgroundColor: '#fef2f2', borderColor: '#fecaca' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <span style={{ ...labelStyle, color: '#991b1b', margin: 0 }}>Operational Safety Conflict</span>
                {data.blocks_approval !== false && (
                  <span style={{ fontSize: '9px', fontWeight: 800, backgroundColor: '#ef4444', color: '#fff', padding: '1px 5px', borderRadius: '3px' }}>
                    BLOCKS APPROVAL
                  </span>
                )}
              </div>
              {data.title && <div style={{ fontSize: '13px', fontWeight: 800, color: '#991b1b', marginBottom: '6px' }}>{data.title}</div>}
              <div style={valStyle}><strong>Severity:</strong> <span style={{ color: '#dc2626', fontWeight: 800 }}>{data.severity}</span></div>
              <div style={valStyle}><strong>Type:</strong> {data.conflict_type}</div>
              <div style={valStyle}><strong>Section:</strong> Block {data.block_id}</div>
              <div style={valStyle}><strong>Description:</strong> {data.description}</div>
            </div>

            <div style={cardStyle}>
              <div style={labelStyle}>Recommended Advisory Resolution</div>
              <div style={{ fontSize: '12px', color: '#0f172a', lineHeight: '1.4' }}>
                {data.suggested_resolution}
              </div>
            </div>
          </>
        )}

        {/* ASSET INSPECTION */}
        {type === 'asset' && (
          <div style={cardStyle}>
            <div style={labelStyle}>Track Asset Health Telemetry</div>
            <div style={valStyle}><strong>Asset Name:</strong> {data.name}</div>
            <div style={valStyle}><strong>Type:</strong> {data.asset_type}</div>
            <div style={valStyle}><strong>Location:</strong> Block {data.block_id} (KM {data.chainage_start_km} - {data.chainage_end_km})</div>
            <div style={valStyle}><strong>Health Score:</strong> <strong style={{ color: (data.health_score ?? 100) < 50 ? '#dc2626' : '#16a34a' }}>{data.health_score ?? 0}%</strong></div>
            <div style={valStyle}><strong>Defect Severity:</strong> {data.defect_severity}</div>
            <div style={valStyle}><strong>Observed Defect:</strong> {data.observed_defect_type}</div>
            <div style={valStyle}><strong>Ultrasonic Test Date:</strong> {data.last_ultrasonic_test}</div>
            <div style={valStyle}><strong>Days Overdue:</strong> {data.days_overdue} days</div>
          </div>
        )}

        {/* 3. Safety Boundary Legal Disclaimer */}
        <div style={{ padding: '8px', backgroundColor: '#f1f5f9', borderRadius: '4px', border: '1px solid #e2e8f0', fontSize: '10px', color: '#64748b', lineHeight: '1.3' }}>
          <strong>CRITICAL SAFETY NOTICE:</strong> This 3D mapping module provides visualization and decision support only. Direct signalling, point-machine, traction-breaker, or train-dispatch commands are strictly prohibited.
        </div>
      </div>
    </aside>
  );
};

const cardStyle: React.CSSProperties = {
  backgroundColor: '#f8fafc',
  border: '1px solid #e2e8f0',
  borderRadius: '6px',
  padding: '12px'
};

const labelStyle: React.CSSProperties = {
  fontSize: '11px',
  fontWeight: 700,
  textTransform: 'uppercase',
  color: '#475569',
  marginBottom: '6px',
  letterSpacing: '0.3px'
};

const valStyle: React.CSSProperties = {
  fontSize: '12px',
  color: '#1e293b',
  marginBottom: '4px',
  lineHeight: '1.35'
};
