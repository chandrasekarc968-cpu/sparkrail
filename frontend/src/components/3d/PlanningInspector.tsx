import React from 'react';
import type { SelectedEntity } from '../../hooks/usePlanningSimulation';
import type { OptimizedSchedule } from '../../api/types';

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
  suggested_resolution?: string;
  asset_type?: string;
  chainage_start_km?: number;
  chainage_end_km?: number;
  health_score?: number;
  defect_severity?: string;
  observed_defect_type?: string;
  last_ultrasonic_test?: string;
  days_overdue?: number;
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

  return (
    <aside
      style={{
        position: 'absolute',
        top: '16px',
        right: '16px',
        bottom: '120px',
        width: '360px',
        maxWidth: '90vw',
        zIndex: 25,
        backgroundColor: '#ffffff',
        borderRadius: '8px',
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.15)',
        border: '1px solid #cbd5e1',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        fontFamily: 'system-ui, sans-serif'
      }}
      aria-label="Planning Detail Inspector"
    >
      {/* Header */}
      <div
        style={{
          padding: '12px 16px',
          backgroundColor: '#0f172a',
          color: '#ffffff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #1e293b'
        }}
      >
        <div>
          <span style={{ fontSize: '10px', textTransform: 'uppercase', color: '#38bdf8', fontWeight: 700, letterSpacing: '0.5px' }}>
            {type} Inspector
          </span>
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

      {/* Body Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {/* BLOCK INSPECTION */}
        {type === 'block' && (
          <>
            <div style={cardStyle}>
              <div style={labelStyle}>Block Details</div>
              <div style={valStyle}><strong>Chainage:</strong> KM {data.chainage_start ?? 0} - KM {data.chainage_end ?? 0} ({((data.chainage_end ?? 0) - (data.chainage_start ?? 0)).toFixed(1)} km)</div>
              <div style={valStyle}><strong>Description:</strong> {data.description}</div>
              <div style={valStyle}><strong>Speed Limit:</strong> {data.speed_restriction_kmh || 100} km/h</div>
              <div style={valStyle}><strong>Electrification:</strong> {data.electrification_status || '25kV AC'}</div>
              <div style={valStyle}><strong>Signaling:</strong> {data.signaling_type || 'Automatic'}</div>
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

        {/* JOB INSPECTION */}
        {type === 'job' && (
          <>
            <div style={cardStyle}>
              <div style={labelStyle}>Maintenance Job Info</div>
              <div style={valStyle}><strong>Department:</strong> {data.department}</div>
              <div style={valStyle}><strong>Block:</strong> {data.block_id}</div>
              <div style={valStyle}><strong>Duration:</strong> {data.duration} hours</div>
              <div style={valStyle}><strong>Type:</strong> {data.job_type || 'Corridor Maintenance'}</div>
              <div style={valStyle}><strong>Safety Clearance:</strong> {data.safety_clearance_required || 'Standard Track Possession'}</div>
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

            {/* AI Explainability */}
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
            <div style={valStyle}><strong>Train Name:</strong> {data.name || data.id || id}</div>
            <div style={valStyle}><strong>Category:</strong> <span style={{ textTransform: 'uppercase', fontWeight: 700 }}>{data.category}</span></div>
            <div style={valStyle}><strong>Scheduled Window:</strong> T+{(data.scheduled_start ?? 0).toFixed(1)}h - T+{(data.scheduled_end ?? 0).toFixed(1)}h</div>
            <div style={valStyle}><strong>Route Corridor:</strong> {data.route?.join(' ➔ ')}</div>
            <div style={valStyle}><strong>Max Speed:</strong> {data.max_speed_kmh || 100} km/h</div>
            <div style={valStyle}><strong>Current Delay:</strong> {data.current_delay_min || 0} minutes</div>
          </div>
        )}

        {/* CONFLICT INSPECTION */}
        {type === 'conflict' && (
          <>
            <div style={{ ...cardStyle, backgroundColor: '#fef2f2', borderColor: '#fecaca' }}>
              <div style={{ ...labelStyle, color: '#991b1b' }}>Operational Conflict Warning</div>
              <div style={valStyle}><strong>Severity:</strong> <span style={{ color: '#dc2626', fontWeight: 800 }}>{data.severity}</span></div>
              <div style={valStyle}><strong>Type:</strong> {data.conflict_type}</div>
              <div style={valStyle}><strong>Section:</strong> {data.block_id}</div>
              <div style={valStyle}><strong>Description:</strong> {data.description}</div>
            </div>

            <div style={cardStyle}>
              <div style={labelStyle}>Recommended Resolution</div>
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
