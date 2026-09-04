import React, { useMemo } from 'react';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import type { TrackGeometry } from '../../api/types';

interface MaintenanceBlockVolumeProps {
  track: TrackGeometry;
  jobId: string;
  department: string;
  isShadow?: boolean;
  shadowJobs?: string[];
  isSelected?: boolean;
  onSelect?: () => void;
  showLabel?: boolean;
}

const DEPT_COLORS: Record<string, string> = {
  Engineering: '#f59e0b', // Amber
  OHE: '#06b6d4',         // Cyan
  'S&T': '#8b5cf6'        // Purple
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

  const color = isShadow ? '#10b981' : (DEPT_COLORS[department] || '#f59e0b');
  const shouldRenderLabel = isSelected || showLabel;

  return (
    <group onClick={(e) => { e.stopPropagation(); onSelect?.(); }}>
      {/* 1. Volumetric Possession Cage */}
      <mesh position={[0, 1.2, 0]}>
        <tubeGeometry args={[curve, 20, 3.5, 8, false]} />
        <meshStandardMaterial
          color={color}
          transparent
          opacity={isSelected ? 0.45 : 0.25}
          roughness={0.2}
          wireframe
        />
      </mesh>

      {/* 2. Heavy Maintenance Machine Model (BCM / Tower Wagon) at Midpoint */}
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

      {/* 3. Operational Work Zone Tag */}
      {shouldRenderLabel && (
        <Html position={[midPoint.x, midPoint.y, midPoint.z]} center distanceFactor={150}>
          <div
            style={{
              padding: '3px 8px',
              backgroundColor: '#0f172a',
              color: '#ffffff',
              borderRadius: '4px',
              border: `2px solid ${color}`,
              boxShadow: '0 2px 8px rgba(0,0,0,0.25)',
              fontSize: '9.5px',
              fontFamily: 'monospace',
              whiteSpace: 'nowrap',
              cursor: 'pointer',
              textAlign: 'center',
              userSelect: 'none'
            }}
            title={`Job ${jobId} (${department}) - ${isShadow ? 'Consolidated Shadow Possession' : 'Single Department Block'}`}
          >
            <div style={{ fontWeight: 800, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '6px', height: '6px', backgroundColor: color, borderRadius: '50%' }} />
              <span>{jobId}</span>
              <span style={{ color: '#94a3b8', fontSize: '8.5px' }}>[{department}]</span>
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
    prev.department === next.department
  );
});
