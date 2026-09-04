import React from 'react';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import type { ConflictItem } from '../../api/types';

interface ConflictMarkerProps {
  conflict: ConflictItem;
  isSelected?: boolean;
  onSelect?: () => void;
  showLabel?: boolean;
}

const octaGeometry = new THREE.OctahedronGeometry(1.2, 0);
const coreSphereGeometry = new THREE.SphereGeometry(0.5, 8, 8);
const ringGeometry = new THREE.RingGeometry(2.5, 3.2, 16);
const coreMaterial = new THREE.MeshBasicMaterial({ color: '#ffffff' });

export const ConflictMarker: React.FC<ConflictMarkerProps> = React.memo(({
  conflict,
  isSelected = false,
  onSelect,
  showLabel = true
}) => {
  const pos = conflict.position || conflict.coordinates;
  if (!pos) return null;
  const isCritical = conflict.severity === 'CRITICAL';
  const color = isCritical ? '#ef4444' : '#f59e0b';
  // Never hide critical or selected conflict labels
  const shouldRenderLabel = isCritical || isSelected || showLabel;

  return (
    <group
      position={[pos.x, pos.y + 4.5, pos.z]}
      onClick={(e) => { e.stopPropagation(); onSelect?.(); }}
    >
      {/* 1. Hazard Warning Diamond Indicator */}
      <mesh rotation={[Math.PI / 4, 0, Math.PI / 4]}>
        <primitive object={octaGeometry} attach="geometry" />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.6}
          roughness={0.2}
          wireframe={!isSelected}
        />
      </mesh>

      {/* 2. Core Warning Light */}
      <mesh>
        <primitive object={coreSphereGeometry} attach="geometry" />
        <primitive object={coreMaterial} attach="material" />
      </mesh>

      {/* 3. Hazard Base Projection Ring */}
      <mesh position={[0, -4.2, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <primitive object={ringGeometry} attach="geometry" />
        <meshBasicMaterial color={color} transparent opacity={0.6} />
      </mesh>

      {/* 4. Conflict Label Tag */}
      {shouldRenderLabel && (
        <Html position={[0, 2.5, 0]} center distanceFactor={140}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 8px',
              backgroundColor: '#0f172a',
              color: '#ffffff',
              borderRadius: '4px',
              border: `2px solid ${color}`,
              boxShadow: '0 3px 12px rgba(239, 68, 68, 0.4)',
              fontSize: '9.5px',
              fontFamily: 'monospace',
              whiteSpace: 'nowrap',
              cursor: 'pointer',
              userSelect: 'none'
            }}
            title={`${conflict.title} - ${conflict.description}`}
          >
            <span
              style={{
                padding: '1px 4px',
                borderRadius: '2px',
                backgroundColor: color,
                color: '#ffffff',
                fontWeight: 800,
                fontSize: '8px'
              }}
            >
              {conflict.severity}
            </span>
            <span style={{ fontWeight: 700 }}>{conflict.title}</span>
          </div>
        </Html>
      )}
    </group>
  );
}, (prev, next) => {
  return (
    prev.conflict.id === next.conflict.id &&
    prev.isSelected === next.isSelected &&
    prev.showLabel === next.showLabel
  );
});
