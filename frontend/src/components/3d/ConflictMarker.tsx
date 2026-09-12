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
  const isMajor = conflict.severity === 'MAJOR';
  const blocksApproval = conflict.blocks_approval ?? (isCritical || isMajor);
  const color = isCritical ? '#ef4444' : isMajor ? '#f97316' : '#f59e0b';
  // Never hide critical or selected conflict labels
  const shouldRenderLabel = isCritical || isMajor || isSelected || showLabel;

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
          emissiveIntensity={isCritical ? 0.9 : 0.5}
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
        <meshBasicMaterial color={color} transparent opacity={0.7} />
      </mesh>

      {/* 4. Conflict Label Tag with Explicit Approval-Blocking Banner */}
      {shouldRenderLabel && (
        <Html position={[0, 2.5, 0]} center distanceFactor={140}>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '3px',
              padding: '4px 9px',
              backgroundColor: '#0f172a',
              color: '#ffffff',
              borderRadius: '4px',
              border: `2px solid ${color}`,
              boxShadow: isCritical ? '0 4px 16px rgba(239, 68, 68, 0.6)' : '0 3px 12px rgba(249, 115, 22, 0.4)',
              fontSize: '10px',
              fontFamily: 'monospace',
              whiteSpace: 'nowrap',
              cursor: 'pointer',
              userSelect: 'none'
            }}
            title={`${conflict.title} - ${conflict.description}\nSuggested: ${conflict.suggested_resolution || 'Review in BDMS'}`}
            role="alert"
            aria-label={`Safety Conflict: ${conflict.title}, Severity ${conflict.severity}${blocksApproval ? ', Blocks Approval' : ''}`}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span
                style={{
                  padding: '1px 5px',
                  borderRadius: '2px',
                  backgroundColor: color,
                  color: '#ffffff',
                  fontWeight: 800,
                  fontSize: '8.5px'
                }}
              >
                {conflict.severity}
              </span>
              <span style={{ fontWeight: 700 }}>{conflict.title}</span>
            </div>

            {blocksApproval && (
              <div
                style={{
                  fontSize: '8px',
                  fontWeight: 800,
                  color: '#fca5a5',
                  backgroundColor: 'rgba(239, 68, 68, 0.25)',
                  padding: '1px 6px',
                  borderRadius: '2px',
                  border: '1px solid #ef4444'
                }}
              >
                🚫 APPROVAL BLOCKED
              </div>
            )}
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
