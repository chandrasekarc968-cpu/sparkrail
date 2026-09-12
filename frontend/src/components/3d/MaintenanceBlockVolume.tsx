import React, { useMemo } from 'react';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import type { TrackGeometry } from '../../api/types';

interface MaintenanceBlockVolumeProps {
  track: TrackGeometry;
  jobId: string;
  department: string;
  status?: string;
  isLocked?: boolean;
  isShadow?: boolean;
  shadowJobs?: string[];
  isSelected?: boolean;
  onSelect?: () => void;
  showLabel?: boolean;
}

// Canonical possession status colors
const POSSESSION_STATUS_COLORS: Record<string, string> = {
  REQUESTED: '#f59e0b',        // Amber planned
  PLANNED: '#f59e0b',          // Amber planned
  SANCTIONED: '#3b82f6',       // Blue sanctioned
  GRANTED: '#8b5cf6',          // Purple granted (immutable)
  IN_PROGRESS: '#ef4444',      // Red in-progress (active)
  COMPLETED: '#6b7280',        // Muted completed
  active_maintenance: '#ef4444',
  fixed_block: '#8b5cf6'
};

const chassisGeometry = new THREE.BoxGeometry(8, 1.6, 2.6);
const craneGeometry = new THREE.BoxGeometry(0.4, 2.5, 0.4);
const beaconGeometry = new THREE.SphereGeometry(0.3, 8, 8);

const chassisMaterial = new THREE.MeshStandardMaterial({ color: '#b45309', roughness: 0.5, metalness: 0.4 });
const craneMaterial = new THREE.MeshStandardMaterial({ color: '#fef08a', roughness: 0.3 });
const beaconMaterial = new THREE.MeshBasicMaterial({ color: '#ef4444' });

export const MaintenanceBlockVolume: React.FC<MaintenanceBlockVolumeProps> = React.memo(({
  track,
  jobId,
  department,
  status = 'REQUESTED',
  isLocked = false,
  isShadow = false,
  shadowJobs = [],
  isSelected = false,
  onSelect,
  showLabel = true
}) => {
  const points = useMemo(() => {
    return track.path_points.map(p => new THREE.Vector3(p.x, p.y, p.z));
  }, [track.path_points]);

  const curve = useMemo(() => {
    return new THREE.CatmullRomCurve3(points);
  }, [points]);

  const midPoint = useMemo(() => {
    const midIdx = Math.floor(points.length / 2);
    const p = points[midIdx] || new THREE.Vector3(0, 0, 0);
    return new THREE.Vector3(p.x, p.y + 6.0, p.z);
  }, [points]);

  const normalizedStatus = String(status).toUpperCase();
  const isImmutableLocked = isLocked || normalizedStatus === 'GRANTED' || normalizedStatus === 'IN_PROGRESS' || normalizedStatus === 'FIXED_BLOCK';

  const baseColor = isShadow
    ? '#10b981'
    : (POSSESSION_STATUS_COLORS[normalizedStatus] || POSSESSION_STATUS_COLORS[status] || '#f59e0b');

  const shouldRenderLabel = isSelected || showLabel;

  return (
    <group onClick={(e) => { e.stopPropagation(); onSelect?.(); }}>
      {/* 1. Volumetric Possession Cage Envelope */}
      <mesh position={[0, 1.2, 0]}>
        <tubeGeometry args={[curve, 20, 3.5, 8, false]} />
        <meshStandardMaterial
          color={baseColor}
          transparent
          opacity={isSelected ? 0.55 : 0.3}
          roughness={0.2}
          wireframe={!isImmutableLocked}
        />
      </mesh>

      {/* 2. Heavy Maintenance Machine Model (BCM / Track Tamper / Tower Wagon) */}
      <group position={[midPoint.x, midPoint.y - 4.5, midPoint.z]}>
        {/* Machine Chassis */}
        <mesh position={[0, 0.8, 0]}>
          <primitive object={chassisGeometry} attach="geometry" />
          <primitive object={chassisMaterial} attach="material" />
        </mesh>
        {/* Work Crane / Inspection Arm */}
        <mesh position={[1.5, 2.2, 0]} rotation={[0, 0, 0.3]}>
          <primitive object={craneGeometry} attach="geometry" />
          <primitive object={craneMaterial} attach="material" />
        </mesh>
        {/* Flashing Hazard Beacon */}
        <mesh position={[0, 1.8, 0]}>
          <primitive object={beaconGeometry} attach="geometry" />
          <primitive object={beaconMaterial} attach="material" />
        </mesh>
      </group>

      {/* 3. Operational Possession Tag with Immutable Lock Indicator */}
      {shouldRenderLabel && (
        <Html position={[midPoint.x, midPoint.y, midPoint.z]} center distanceFactor={150}>
          <div
            style={{
              padding: '4px 9px',
              backgroundColor: '#0f172a',
              color: '#ffffff',
              borderRadius: '4px',
              border: isImmutableLocked ? '2px solid #8b5cf6' : `2px solid ${baseColor}`,
              boxShadow: isImmutableLocked ? '0 3px 12px rgba(139, 92, 246, 0.4)' : '0 2px 8px rgba(0,0,0,0.25)',
              fontSize: '10px',
              fontFamily: 'monospace',
              whiteSpace: 'nowrap',
              cursor: 'pointer',
              textAlign: 'center',
              userSelect: 'none'
            }}
            title={`Possession ${jobId} (${department}) [${normalizedStatus}]${isImmutableLocked ? ' - IMMUTABLE ACTIVE POSSESSION (LOCKED)' : ''}`}
            aria-label={`Possession ${jobId}, Department ${department}, Status ${normalizedStatus}${isImmutableLocked ? ', Locked and Immutable' : ''}`}
          >
            <div style={{ fontWeight: 800, display: 'flex', alignItems: 'center', gap: '5px', justifyContent: 'center' }}>
              {isImmutableLocked && <span title="Safety Boundary #6: Granted and in-progress possessions are immutable">🔒</span>}
              <span style={{ width: '6px', height: '6px', backgroundColor: baseColor, borderRadius: '50%' }} />
              <span>{jobId}</span>
              <span style={{ color: '#94a3b8', fontSize: '8.5px' }}>[{department}]</span>
            </div>
            <div style={{ fontSize: '8px', color: isImmutableLocked ? '#c084fc' : '#38bdf8', marginTop: '2px', fontWeight: 700 }}>
              {isImmutableLocked ? '🔒 IMMUTABLE ACTIVE' : normalizedStatus}
            </div>
            {isShadow && shadowJobs.length > 0 && (
              <div style={{ fontSize: '8px', color: '#34d399', marginTop: '1px' }}>
                🔗 Shadow +{shadowJobs.length} jobs
              </div>
            )}
          </div>
        </Html>
      )}
    </group>
  );
}, (prev, next) => {
  return (
    prev.jobId === next.jobId &&
    prev.track.block_id === next.track.block_id &&
    prev.isSelected === next.isSelected &&
    prev.showLabel === next.showLabel &&
    prev.isShadow === next.isShadow &&
    prev.department === next.department &&
    prev.status === next.status &&
    prev.isLocked === next.isLocked
  );
});
