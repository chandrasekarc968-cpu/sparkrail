import React from 'react';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import type { TrainPosition } from '../../hooks/usePlanningSimulation';

interface TrainMarkerProps {
  trainPos: TrainPosition;
  isSelected?: boolean;
  onSelect?: () => void;
  showLabel?: boolean;
}

// Module-level shared geometries
const cabinGeometry = new THREE.BoxGeometry(7, 1.8, 2.2);
const coachGeometry = new THREE.BoxGeometry(6.5, 1.7, 2.1);
const noseGeometry = new THREE.ConeGeometry(1.0, 1.6, 12);
const headlightGeometry = new THREE.SphereGeometry(0.3, 8, 8);
const ringGeometry = new THREE.CylinderGeometry(4.5, 4.5, 0.2, 16);

// Module-level shared materials
const premiumCabinMaterial = new THREE.MeshStandardMaterial({ color: '#d97706', metalness: 0.6, roughness: 0.3 });
const freightCabinMaterial = new THREE.MeshStandardMaterial({ color: '#78350f', metalness: 0.6, roughness: 0.3 });
const standardCabinMaterial = new THREE.MeshStandardMaterial({ color: '#1d4ed8', metalness: 0.6, roughness: 0.3 });
const selectedCabinMaterial = new THREE.MeshStandardMaterial({ color: '#38bdf8', metalness: 0.8, roughness: 0.2 });

const premiumCoachMaterial = new THREE.MeshStandardMaterial({ color: '#f8fafc', metalness: 0.3, roughness: 0.6 });
const freightCoachMaterial = new THREE.MeshStandardMaterial({ color: '#334155', metalness: 0.3, roughness: 0.6 });
const noseMaterial = new THREE.MeshStandardMaterial({ color: '#f8fafc', metalness: 0.4, roughness: 0.3 });
const headlightMaterial = new THREE.MeshBasicMaterial({ color: '#fef08a' });
const selectionBeaconMaterial = new THREE.MeshBasicMaterial({ color: '#38bdf8', wireframe: true, transparent: true, opacity: 0.6 });

export const TrainMarker: React.FC<TrainMarkerProps> = React.memo(({
  trainPos,
  isSelected = false,
  onSelect,
  showLabel = true
}) => {
  const { train, position, isMoving, affectedByMaintenance } = trainPos;
  const isPremium = train.category === 'premium';
  const isFreight = train.category === 'freight';

  const cabinMat = isSelected
    ? selectedCabinMaterial
    : isPremium
    ? premiumCabinMaterial
    : isFreight
    ? freightCabinMaterial
    : standardCabinMaterial;

  const coachMat = isPremium ? premiumCoachMaterial : freightCoachMaterial;
  const shouldRenderLabel = isSelected || showLabel;

  return (
    <group
      position={[position.x, position.y + 0.8, position.z]}
      onClick={(e) => { e.stopPropagation(); onSelect?.(); }}
    >
      {/* 1. Main Locomotive Cabin */}
      <mesh position={[0, 0.9, 0]}>
        <primitive object={cabinGeometry} attach="geometry" />
        <primitive object={cabinMat} attach="material" />
      </mesh>

      {/* 2. Trailing Coach 1 */}
      <mesh position={[-8, 0.85, 0]}>
        <primitive object={coachGeometry} attach="geometry" />
        <primitive object={coachMat} attach="material" />
      </mesh>

      {/* 3. Trailing Coach 2 */}
      <mesh position={[-15.5, 0.85, 0]}>
        <primitive object={coachGeometry} attach="geometry" />
        <primitive object={coachMat} attach="material" />
      </mesh>

      {/* 4. Aerodynamic Nose Cone (for Premium trains) */}
      {isPremium && (
        <mesh position={[3.8, 0.7, 0]} rotation={[0, 0, -Math.PI / 2]}>
          <primitive object={noseGeometry} attach="geometry" />
          <primitive object={noseMaterial} attach="material" />
        </mesh>
      )}

      {/* 5. Headlight Beam (when active) */}
      {isMoving && (
        <mesh position={[4.6, 0.7, 0]}>
          <primitive object={headlightGeometry} attach="geometry" />
          <primitive object={headlightMaterial} attach="material" />
        </mesh>
      )}

      {/* 6. Selection Beacon Ring */}
      {isSelected && (
        <mesh position={[0, -0.4, 0]}>
          <primitive object={ringGeometry} attach="geometry" />
          <primitive object={selectionBeaconMaterial} attach="material" />
        </mesh>
      )}

      {/* 7. Train Information Tag */}
      {shouldRenderLabel && (
        <Html position={[0, 3.6, 0]} center distanceFactor={140}>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              padding: '3px 8px',
              backgroundColor: isSelected ? '#0369a1' : '#0f172a',
              color: '#ffffff',
              borderRadius: '4px',
              boxShadow: '0 2px 10px rgba(0,0,0,0.3)',
              border: isSelected ? '2px solid #38bdf8' : affectedByMaintenance ? '2px solid #ef4444' : '1px solid #334155',
              fontSize: '10px',
              fontFamily: 'monospace',
              whiteSpace: 'nowrap',
              cursor: 'pointer',
              userSelect: 'none'
            }}
            title={`${train.name || train.id} (${train.category})`}
          >
            <div style={{ fontWeight: 800, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span>{isPremium ? '⚡' : '🚂'}</span>
              <span>{train.id}</span>
              <span style={{ color: '#94a3b8', fontSize: '9px' }}>{train.name?.split(' ')[0]}</span>
            </div>
            {affectedByMaintenance && (
              <div style={{ color: '#f87171', fontSize: '8.5px', fontWeight: 700, marginTop: '1px' }}>
                ⚠️ Work Zone Delay
              </div>
            )}
          </div>
        </Html>
      )}
    </group>
  );
}, (prev, next) => {
  return (
    prev.trainPos.train.id === next.trainPos.train.id &&
    prev.isSelected === next.isSelected &&
    prev.showLabel === next.showLabel &&
    prev.trainPos.position.x === next.trainPos.position.x &&
    prev.trainPos.position.y === next.trainPos.position.y &&
    prev.trainPos.position.z === next.trainPos.position.z &&
    prev.trainPos.isMoving === next.trainPos.isMoving &&
    prev.trainPos.affectedByMaintenance === next.trainPos.affectedByMaintenance
  );
});
