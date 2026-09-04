import React from 'react';
import type {
  NetworkGeometryResponse,
  OptimizedSchedule
} from '../../api/types';
import type { TrainPosition, SelectedEntity } from '../../hooks/usePlanningSimulation';

export interface BlockStateInfo {
  status: string;
  activeJobId?: string;
  department?: string;
  isShadow?: boolean;
  hasConflict?: boolean;
}

interface Accessible2DNetworkProps {
  geometry: NetworkGeometryResponse | null;
  schedule: OptimizedSchedule | null;
  currentTime: number;
  trainPositions: TrainPosition[];
  blockStates: Map<string, BlockStateInfo>;
  onSelectEntity: (entity: SelectedEntity | null) => void;
  selectedEntityId?: string;
}

const STATE_COLORS: Record<string, string> = {
  available: '#94a3b8',
  active_maintenance: '#f59e0b',
  planned_maintenance: '#3b82f6',
  fixed_block: '#8b5cf6',
  conflict: '#ef4444',
  high_risk: '#f97316',
  frozen_week1: '#06b6d4',
  shadow_block: '#10b981'
};

export const Accessible2DNetwork: React.FC<Accessible2DNetworkProps> = ({
  geometry,
  schedule,
  currentTime,
  trainPositions,
  blockStates,
  onSelectEntity,
  selectedEntityId
}) => {
  const tracks = geometry?.tracks || [];
  const nodes = geometry?.nodes || [];
  const conflicts = schedule?.conflicts || geometry?.conflicts || [];
  const totalLengthKm = geometry?.total_length_km || 
    (tracks.length > 0 ? Math.max(...tracks.map(t => t.chainage_end)) : 80.0);

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        overflow: 'auto',
        backgroundColor: '#f8fafc',
        padding: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        boxSizing: 'border-box',
        fontFamily: 'system-ui, sans-serif'
      }}
      role="region"
      aria-label="Accessible 2D Corridor Schematic View"
    >
      {/* Schematic Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 800, color: '#0f172a' }}>
            {geometry?.line_name || 'Subedarganj - Mirzapur Mainline'} (Schematic 2D View)
          </h2>
          <p style={{ margin: '3px 0 0 0', fontSize: '12px', color: '#64748b' }}>
            High-contrast operational layout with chainage markers, active possessions, and train tracking.
          </p>
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', fontSize: '11px', color: '#334155', fontWeight: 600 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '12px', height: '12px', backgroundColor: '#94a3b8', borderRadius: '2px' }} /> Available
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '12px', height: '12px', backgroundColor: '#f59e0b', borderRadius: '2px' }} /> Active Possession
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '12px', height: '12px', backgroundColor: '#10b981', borderRadius: '2px' }} /> Shadow Block
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '12px', height: '12px', backgroundColor: '#8b5cf6', borderRadius: '2px' }} /> Fixed Block
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '12px', height: '12px', backgroundColor: '#ef4444', borderRadius: '2px' }} /> Conflict
          </div>
        </div>
      </div>

      {/* SVG Linear Schematic Diagram */}
      <div
        style={{
          backgroundColor: '#ffffff',
          borderRadius: '8px',
          padding: '24px 16px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          border: '1px solid #cbd5e1',
          overflowX: 'auto'
        }}
      >
        <svg
          viewBox="0 0 1000 240"
          style={{ width: '100%', minWidth: '850px', height: '240px', display: 'block' }}
        >
          {/* Main Corridor Baseline Track */}
          <line x1="50" y1="120" x2="950" y2="120" stroke="#cbd5e1" strokeWidth="12" strokeLinecap="round" />
          <line x1="50" y1="116" x2="950" y2="116" stroke="#475569" strokeWidth="2" />
          <line x1="50" y1="124" x2="950" y2="124" stroke="#475569" strokeWidth="2" />

          {/* Block Sections */}
          {tracks.map((track) => {
            const startX = 50 + (track.chainage_start / totalLengthKm) * 900;
            const endX = 50 + (track.chainage_end / totalLengthKm) * 900;
            const blockState = blockStates.get(track.block_id) || { status: 'available' };
            const color = STATE_COLORS[blockState.status] || '#94a3b8';
            const isSelected = selectedEntityId === track.block_id;

            return (
              <g
                key={track.block_id}
                onClick={() => onSelectEntity({ type: 'block', id: track.block_id, data: track })}
                style={{ cursor: 'pointer' }}
              >
                {/* Block Possession Segment */}
                <line
                  x1={startX + 2}
                  y1="120"
                  x2={endX - 2}
                  y2="120"
                  stroke={color}
                  strokeWidth={isSelected ? "14" : "10"}
                  strokeDasharray={blockState.status === 'planned_maintenance' ? '6 4' : 'none'}
                />

                {/* Block Separator Notch */}
                <line x1={startX} y1="105" x2={startX} y2="135" stroke="#334155" strokeWidth="2" />

                {/* Block ID Label */}
                <text
                  x={(startX + endX) / 2}
                  y="96"
                  textAnchor="middle"
                  fill={isSelected ? '#0284c7' : '#0f172a'}
                  fontSize="12"
                  fontWeight="800"
                  fontFamily="monospace"
                >
                  {track.block_id}
                </text>

                {/* Speed Limit & Status */}
                <text
                  x={(startX + endX) / 2}
                  y="146"
                  textAnchor="middle"
                  fill="#64748b"
                  fontSize="9.5"
                  fontFamily="system-ui"
                >
                  {track.speed_limit_kmh} km/h • {blockState.status.replace('_', ' ')}
                </text>
              </g>
            );
          })}

          {/* Station Nodes along Corridor */}
          {nodes.map((node) => {
            const nodeX = 50 + (node.chainage_km / totalLengthKm) * 900;
            const isSelected = selectedEntityId === node.id;

            return (
              <g
                key={node.id}
                onClick={() => onSelectEntity({ type: 'asset', id: node.id, data: node })}
                style={{ cursor: 'pointer' }}
              >
                {/* Station Pillar Marker */}
                <rect
                  x={nodeX - 5}
                  y="112"
                  width="10"
                  height="16"
                  fill={isSelected ? '#0284c7' : '#0f172a'}
                  rx="2"
                />

                {/* Station Code Badge */}
                <rect
                  x={nodeX - 18}
                  y="50"
                  width="36"
                  height="20"
                  fill={isSelected ? '#0284c7' : '#1e293b'}
                  rx="4"
                  stroke="#ffffff"
                  strokeWidth="1.5"
                />
                <text
                  x={nodeX}
                  y="64"
                  textAnchor="middle"
                  fill="#ffffff"
                  fontSize="10"
                  fontWeight="800"
                  fontFamily="monospace"
                >
                  {node.code}
                </text>
                <text
                  x={nodeX}
                  y="44"
                  textAnchor="middle"
                  fill="#475569"
                  fontSize="9"
                  fontWeight="600"
                >
                  KM {node.chainage_km.toFixed(0)}
                </text>
              </g>
            );
          })}

          {/* Active Trains along Track */}
          {trainPositions.map((tp) => {
            const track = tracks.find(t => t.block_id === tp.currentBlockId);
            let trainChainage: number;
            if (track) {
              trainChainage = track.chainage_start + (track.chainage_end - track.chainage_start) * tp.progress;
            } else {
              trainChainage = ((tp.position.x + 400.0) / 800.0) * totalLengthKm;
            }
            const trainX = 50 + (trainChainage / totalLengthKm) * 900;
            const isPrem = tp.train.category === 'premium';
            const color = isPrem ? '#d97706' : '#1d4ed8';
            const isSelected = selectedEntityId === tp.train.id;

            return (
              <g
                key={tp.train.id}
                onClick={() => onSelectEntity({ type: 'train', id: tp.train.id, data: tp.train })}
                style={{ cursor: 'pointer' }}
              >
                <polygon
                  points={`${trainX - 12},110 ${trainX + 12},110 ${trainX + 18},120 ${trainX + 12},130 ${trainX - 12},130`}
                  fill={color}
                  stroke={isSelected ? '#38bdf8' : '#ffffff'}
                  strokeWidth="2"
                />
                <text
                  x={trainX}
                  y="124"
                  textAnchor="middle"
                  fill="#ffffff"
                  fontSize="8.5"
                  fontWeight="800"
                  fontFamily="monospace"
                >
                  {tp.train.id}
                </text>
              </g>
            );
          })}

          {/* Active Conflicts Alert Icons */}
          {conflicts.map((conf) => {
            let confChainage: number | null = null;
            if (conf.position) {
              confChainage = ((conf.position.x + 400.0) / 800.0) * totalLengthKm;
            } else if (conf.block_id) {
              const trk = tracks.find(t => t.block_id === conf.block_id);
              if (trk) {
                confChainage = (trk.chainage_start + trk.chainage_end) / 2;
              }
            }
            if (confChainage === null) {
              return null; // Zero-invention: do not render conflicts without canonical spatial coordinates or track
            }
            const confX = 50 + (confChainage / totalLengthKm) * 900;
            return (
              <g
                key={conf.id}
                onClick={() => onSelectEntity({ type: 'conflict', id: conf.id, data: conf })}
                style={{ cursor: 'pointer' }}
              >
                <circle cx={confX} cy="175" r="10" fill="#ef4444" stroke="#ffffff" strokeWidth="2" />
                <text x={confX} y="179" textAnchor="middle" fill="#ffffff" fontSize="11" fontWeight="800">
                  !
                </text>
                <text x={confX} y="198" textAnchor="middle" fill="#991b1b" fontSize="8.5" fontWeight="700">
                  {conf.id}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Accessible Table for Screen Readers and Detailed Auditing */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '8px', padding: '16px', border: '1px solid #cbd5e1' }}>
        <h3 style={{ margin: '0 0 10px 0', fontSize: '14px', fontWeight: 700, color: '#0f172a' }}>
          Corridor Operational Status Table (At T+{currentTime.toFixed(1)}h)
        </h3>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
          <thead>
            <tr style={{ backgroundColor: '#f1f5f9', borderBottom: '2px solid #cbd5e1' }}>
              <th style={{ padding: '8px' }}>Block Section</th>
              <th style={{ padding: '8px' }}>Chainage</th>
              <th style={{ padding: '8px' }}>Status</th>
              <th style={{ padding: '8px' }}>Speed Limit</th>
              <th style={{ padding: '8px' }}>Active Job</th>
              <th style={{ padding: '8px' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {tracks.map((track) => {
              const state = blockStates.get(track.block_id) || { status: 'available' };
              return (
                <tr key={track.block_id} style={{ borderBottom: '1px solid #e2e8f0' }}>
                  <td style={{ padding: '8px', fontWeight: 700, fontFamily: 'monospace' }}>{track.block_id}</td>
                  <td style={{ padding: '8px' }}>KM {track.chainage_start} - KM {track.chainage_end}</td>
                  <td style={{ padding: '8px' }}>
                    <span
                      style={{
                        padding: '2px 6px',
                        borderRadius: '4px',
                        backgroundColor: STATE_COLORS[state.status] || '#94a3b8',
                        color: '#ffffff',
                        fontWeight: 700,
                        fontSize: '10px'
                      }}
                    >
                      {state.status.replace('_', ' ').toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '8px' }}>{track.speed_limit_kmh} km/h</td>
                  <td style={{ padding: '8px' }}>{state.activeJobId || 'None'}</td>
                  <td style={{ padding: '8px' }}>
                    <button
                      onClick={() => onSelectEntity({ type: 'block', id: track.block_id, data: track })}
                      style={{
                        padding: '3px 8px',
                        backgroundColor: '#0284c7',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '4px',
                        fontSize: '11px',
                        cursor: 'pointer'
                      }}
                    >
                      Inspect
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
