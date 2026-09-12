import React, { useMemo, useEffect } from 'react';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import type { TrackGeometry } from '../../api/types';

export interface RailwayTrackProps {
  track: TrackGeometry;
  state?: {
    status: 'available' | 'active_maintenance' | 'planned_maintenance' | 'fixed_block' | 'conflict' | 'high_risk' | 'frozen_week1' | 'shadow_block';
    department?: string;
    isShadow?: boolean;
    hasConflict?: boolean;
  };
  isSelected?: boolean;
  onSelect?: () => void;
  showLabel?: boolean;
  lod?: 'full' | 'simplified' | 'corridor';
}

// Canonical color tokens adhering to Indian Railways digital-twin visual standards
const STATE_COLORS: Record<string, string> = {
  available: '#64748b',                // Neutral slate track
  planned_maintenance: '#f59e0b',       // Amber planned maintenance
  sanctioned: '#3b82f6',                // Blue sanctioned work
  granted: '#8b5cf6',                   // Purple granted work (locked)
  fixed_block: '#8b5cf6',               // Purple fixed block
  in_progress: '#ef4444',               // Red in-progress work (active)
  active_maintenance: '#ef4444',        // Red active maintenance
  completed: '#6b7280',                 // Muted completed work
  ohe_isolation: '#f97316',             // Orange OHE isolation
  signalling_disconnection: '#c026d3',  // Magenta signalling disconnection
  conflict: '#dc2626',                  // High-contrast danger red
  high_risk: '#f97316',                 // Warning orange
  frozen_week1: '#06b6d4',              // Frozen cyan
  shadow_block: '#10b981'               // Coordinated shadow group
};

const STATE_ICONS: Record<string, string> = {
  available: '🛤',
  planned_maintenance: '📅',
  sanctioned: '📋',
  granted: '🔒',
  fixed_block: '🔒',
  in_progress: '⚡',
  active_maintenance: '⚡',
  completed: '✓',
  ohe_isolation: '⚡🚫',
  signalling_disconnection: '📡🚫',
  conflict: '🚫',
  high_risk: '⚠️',
  frozen_week1: '❄️',
  shadow_block: '🔗'
};

const STATE_LABELS: Record<string, string> = {
  available: 'Available',
  planned_maintenance: 'Planned Maintenance',
  sanctioned: 'Sanctioned Work',
  granted: 'Granted (Locked)',
  fixed_block: 'Fixed Mega Block (Locked)',
  in_progress: 'In-Progress Work',
  active_maintenance: 'Active Possession',
  completed: 'Completed (Muted)',
  ohe_isolation: 'OHE Isolation',
  signalling_disconnection: 'Signal Disconnection',
  conflict: 'Safety Conflict',
  high_risk: 'High-Risk Defect',
  frozen_week1: 'Frozen Week 1',
  shadow_block: 'Shadow Bundle'
};

// Reusable standard materials
const ballastMaterial = new THREE.MeshStandardMaterial({ color: '#334155', roughness: 0.9, metalness: 0.1 });
const normalRailMaterial = new THREE.MeshStandardMaterial({ color: '#94a3b8', metalness: 0.8, roughness: 0.3 });
const selectedRailMaterial = new THREE.MeshStandardMaterial({ color: '#38bdf8', metalness: 0.8, roughness: 0.3 });
const selectionGlowMaterial = new THREE.MeshBasicMaterial({ color: '#0284c7', wireframe: true, transparent: true, opacity: 0.8 });

export const RailwayTrack: React.FC<RailwayTrackProps> = React.memo(({
  track,
  state = { status: 'available' },
  isSelected = false,
  onSelect,
  showLabel = true,
  lod = 'full'
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
  const icon = STATE_ICONS[state.status] || '🛤';

  // Status overlay material
  const statusMaterial = useMemo(() => {
    if (state.status === 'available') return null;
    const isWireframe = state.status === 'planned_maintenance' || state.status === 'frozen_week1' || state.status === 'ohe_isolation';
    return new THREE.MeshStandardMaterial({
      color,
      transparent: true,
      opacity: isSelected ? 0.75 : 0.4,
      roughness: 0.4,
      wireframe: isWireframe
    });
  }, [state.status, color, isSelected]);

  // Cleanup dynamic materials on unmount
  useEffect(() => {
    return () => {
      statusMaterial?.dispose();
    };
  }, [statusMaterial]);

  // Always show label if selected, otherwise respect showLabel budget
  const shouldRenderLabel = isSelected || showLabel;

  // Segment count scaled by LOD
  const tubularSegments = lod === 'corridor' ? 8 : lod === 'simplified' ? 14 : 20;

  return (
    <group onClick={(e) => { e.stopPropagation(); onSelect?.(); }}>
      {/* 1. Track Ballast Bed (Foundation) */}
      <mesh position={[0, 0, 0]}>
        <tubeGeometry args={[curve, tubularSegments, lod === 'corridor' ? 2.2 : 1.8, 6, false]} />
        <primitive object={ballastMaterial} attach="material" />
      </mesh>

      {/* 2. Left & Right Rails (rendered in full LOD only) */}
      {lod === 'full' && (
        <>
          <mesh position={[0, 0.4, 0.7]}>
            <tubeGeometry args={[curve, tubularSegments, 0.2, 5, false]} />
            <primitive object={isSelected ? selectedRailMaterial : normalRailMaterial} attach="material" />
          </mesh>
          <mesh position={[0, 0.4, -0.7]}>
            <tubeGeometry args={[curve, tubularSegments, 0.2, 5, false]} />
            <primitive object={isSelected ? selectedRailMaterial : normalRailMaterial} attach="material" />
          </mesh>
        </>
      )}

      {/* 3. Operational Status Overlay Tube */}
      {state.status !== 'available' && statusMaterial && (
        <mesh position={[0, 0.2, 0]}>
          <tubeGeometry args={[curve, tubularSegments, 2.4, 6, false]} />
          <primitive object={statusMaterial} attach="material" />
        </mesh>
      )}

      {/* 4. Selection Glow Ring */}
      {isSelected && (
        <mesh position={[0, 0.2, 0]}>
          <tubeGeometry args={[curve, tubularSegments, 2.8, 6, false]} />
          <primitive object={selectionGlowMaterial} attach="material" />
        </mesh>
      )}

      {/* 5. Accessible Block Label Badge (Icon + Pattern + Color + Text) */}
      {shouldRenderLabel && (
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
            title={`${track.block_id}: ${icon} ${label} (${track.speed_limit_kmh} km/h)`}
            aria-label={`Track Block ${track.block_id}: Status ${label}, Speed Limit ${track.speed_limit_kmh} km/h`}
          >
            <span>{icon}</span>
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
      )}
    </group>
  );
}, (prev, next) => {
  return (
    prev.track.block_id === next.track.block_id &&
    prev.isSelected === next.isSelected &&
    prev.showLabel === next.showLabel &&
    prev.lod === next.lod &&
    prev.state?.status === next.state?.status
  );
});
