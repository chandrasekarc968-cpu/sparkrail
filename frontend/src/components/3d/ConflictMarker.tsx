import React from 'react';
import { Html } from '@react-three/drei';
import type { ConflictItem } from '../../api/types';

interface ConflictMarkerProps {
  conflict: ConflictItem;
  isSelected?: boolean;
  onSelect?: () => void;
}

export const ConflictMarker: React.FC<ConflictMarkerProps> = ({
  conflict,
  isSelected = false,
  onSelect
}) => {
  const pos = conflict.position || { x: 0, y: 3.0, z: 0 };
  const isCritical = conflict.severity === 'CRITICAL';
  const color = isCritical ? '#ef4444' : '#f59e0b';

  return (
    <group
      position={[pos.x, pos.y + 4.5, pos.z]}
      onClick={(e) => { e.stopPropagation(); onSelect?.(); }}
    >
      {/* 1. Hazard Warning Diamond Indicator */}
      <mesh rotation={[Math.PI / 4, 0, Math.PI / 4]}>
        <octahedronGeometry args={[1.2, 0]} />
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
        <sphereGeometry args={[0.5, 8, 8]} />
        <meshBasicMaterial color="#ffffff" />
      </mesh>

      {/* 3. Hazard Base Projection Ring */}
      <mesh position={[0, -4.2, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[2.5, 3.2, 16]} />
        <meshBasicMaterial color={color} transparent opacity={0.6} />
      </mesh>

      {/* 4. Conflict Label Tag */}
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
    </group>
  );
};
