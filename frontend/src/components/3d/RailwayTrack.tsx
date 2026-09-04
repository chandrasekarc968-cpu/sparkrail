import React, { useMemo } from 'react';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import type { TrackGeometry } from '../../api/types';

interface RailwayTrackProps {
  track: TrackGeometry;
  state?: {
    status: 'available' | 'active_maintenance' | 'planned_maintenance' | 'fixed_block' | 'conflict' | 'high_risk' | 'frozen_week1' | 'shadow_block';
    department?: string;
    isShadow?: boolean;
    hasConflict?: boolean;
  };
  isSelected?: boolean;
  onSelect?: () => void;
}

// Color tokens adhering to control-room standards (accessible OKLCH mapped)
const STATE_COLORS: Record<string, string> = {
  available: '#64748b',         // Slate neutral track
  active_maintenance: '#f59e0b', // Signal amber
  planned_maintenance: '#3b82f6',// Info blue
  fixed_block: '#8b5cf6',        // Purple immutable
  conflict: '#ef4444',           // Danger red
  high_risk: '#f97316',          // Warning orange
  frozen_week1: '#06b6d4',       // Frozen cyan
  shadow_block: '#10b981'        // Operational green / multi-dept
};

const STATE_LABELS: Record<string, string> = {
  available: 'Available',
  active_maintenance: 'Active Possession',
  planned_maintenance: 'Planned Work',
  fixed_block: 'Mega Block (Fixed)',
  conflict: 'Critical Conflict',
  high_risk: 'High Risk Defect',
  frozen_week1: 'Frozen Week 1',
  shadow_block: 'Shadow Block (Multi-Dept)'
};

export const RailwayTrack: React.FC<RailwayTrackProps> = ({
  track,
  state = { status: 'available' },
  isSelected = false,
  onSelect
}) => {
  const points = useMemo(() => {
    return track.path_points.map(p => new THREE.Vector3(p.x, p.y, p.z));
  }, [track.path_points]);

  // Curve for tubular track path
  const curve = useMemo(() => {
    return new THREE.CatmullRomCurve3(points);
  }, [points]);

  // Track midpoint for label positioning
  const midPoint = useMemo(() => {
    const midIdx = Math.floor(points.length / 2);
    const p = points[midIdx] || new THREE.Vector3(0, 0, 0);
    return new THREE.Vector3(p.x, p.y + 4.5, p.z);
  }, [points]);

  const color = STATE_COLORS[state.status] || '#64748b';
  const label = STATE_LABELS[state.status] || 'Available';

  return (
    <group onClick={(e) => { e.stopPropagation(); onSelect?.(); }}>
      {/* 1. Track Ballast Bed (Foundation) */}
      <mesh position={[0, 0, 0]}>
        <tubeGeometry args={[curve, 20, 1.8, 8, false]} />
        <meshStandardMaterial
          color="#334155"
          roughness={0.9}
          metalness={0.1}
        />
      </mesh>

      {/* 2. Left Rail */}
      <mesh position={[0, 0.4, 0.7]}>
        <tubeGeometry args={[curve, 20, 0.2, 6, false]} />
        <meshStandardMaterial
          color={isSelected ? '#38bdf8' : '#94a3b8'}
          metalness={0.8}
          roughness={0.3}
        />
      </mesh>

      {/* 3. Right Rail */}
      <mesh position={[0, 0.4, -0.7]}>
        <tubeGeometry args={[curve, 20, 0.2, 6, false]} />
        <meshStandardMaterial
          color={isSelected ? '#38bdf8' : '#94a3b8'}
          metalness={0.8}
          roughness={0.3}
        />
      </mesh>

      {/* 4. Operational Status Overlay Tube */}
      {state.status !== 'available' && (
        <mesh position={[0, 0.2, 0]}>
          <tubeGeometry args={[curve, 24, 2.4, 8, false]} />
          <meshStandardMaterial
            color={color}
            transparent
            opacity={isSelected ? 0.65 : 0.35}
            roughness={0.4}
            wireframe={state.status === 'planned_maintenance' || state.status === 'frozen_week1'}
          />
        </mesh>
      )}

      {/* 5. Selection Glow Ring */}
      {isSelected && (
        <mesh position={[0, 0.2, 0]}>
          <tubeGeometry args={[curve, 24, 2.8, 8, false]} />
          <meshBasicMaterial color="#0284c7" wireframe transparent opacity={0.8} />
        </mesh>
      )}

      {/* 6. Accessible Block Label Badge */}
      <Html position={[midPoint.x, midPoint.y, midPoint.z]} center distanceFactor={180}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '3px 8px',
            backgroundColor: isSelected ? '#0f172a' : '#ffffff',
            color: isSelected ? '#ffffff' : '#0f172a',
            borderRadius: '4px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            border: `2px solid ${color}`,
            fontSize: '11px',
            fontFamily: 'monospace',
            fontWeight: 700,
            whiteSpace: 'nowrap',
            cursor: 'pointer',
            userSelect: 'none'
          }}
          title={`${track.block_id}: ${label} (${track.speed_limit_kmh} km/h)`}
        >
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: state.status === 'conflict' ? '0px' : '50%',
              backgroundColor: color,
              display: 'inline-block'
            }}
          />
          <span>{track.block_id}</span>
          <span style={{ color: isSelected ? '#94a3b8' : '#64748b', fontSize: '9px' }}>
            [{label}]
          </span>
        </div>
      </Html>
    </group>
  );
};
