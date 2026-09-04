import React from 'react';
import { Html } from '@react-three/drei';
import type { StationNode as StationNodeType } from '../../api/types';

interface StationNodeProps {
  node: StationNodeType;
  isSelected?: boolean;
  onSelect?: () => void;
}

export const StationNode: React.FC<StationNodeProps> = ({
  node,
  isSelected = false,
  onSelect
}) => {
  const isJunction = node.node_type === 'junction' || node.node_type === 'terminal';

  return (
    <group
      position={[node.position.x, node.position.y, node.position.z]}
      onClick={(e) => { e.stopPropagation(); onSelect?.(); }}
    >
      {/* 1. Main Platform Concrete Base */}
      <mesh position={[0, 0.4, 0]}>
        <boxGeometry args={[18, 0.8, 6]} />
        <meshStandardMaterial
          color={isJunction ? '#475569' : '#64748b'}
          roughness={0.7}
        />
      </mesh>

      {/* 2. Platform Canopy Roof */}
      <mesh position={[0, 3.2, 0]}>
        <boxGeometry args={[16, 0.4, 5.2]} />
        <meshStandardMaterial
          color={isJunction ? '#0284c7' : '#94a3b8'}
          metalness={0.4}
          roughness={0.5}
        />
      </mesh>

      {/* 3. Canopy Support Pillars */}
      {[-6, 0, 6].map((xOffset) => (
        <React.Fragment key={xOffset}>
          <mesh position={[xOffset, 1.8, 2.2]}>
            <cylinderGeometry args={[0.15, 0.15, 2.4, 8]} />
            <meshStandardMaterial color="#334155" />
          </mesh>
          <mesh position={[xOffset, 1.8, -2.2]}>
            <cylinderGeometry args={[0.15, 0.15, 2.4, 8]} />
            <meshStandardMaterial color="#334155" />
          </mesh>
        </React.Fragment>
      ))}

      {/* 4. Station Building Tower (for Junctions) */}
      {isJunction && (
        <mesh position={[0, 5.0, 4.5]}>
          <boxGeometry args={[8, 3.5, 3]} />
          <meshStandardMaterial color="#e2e8f0" roughness={0.3} />
        </mesh>
      )}

      {/* 5. Station Nameplate / Billboard */}
      <Html position={[0, 6.5, 0]} center distanceFactor={160}>
        <div
          style={{
            padding: '4px 10px',
            backgroundColor: isSelected ? '#0284c7' : '#0f172a',
            color: '#ffffff',
            borderRadius: '4px',
            boxShadow: '0 2px 10px rgba(0,0,0,0.2)',
            border: isSelected ? '2px solid #38bdf8' : '1px solid #334155',
            fontSize: '11px',
            fontWeight: 800,
            whiteSpace: 'nowrap',
            cursor: 'pointer',
            textAlign: 'center',
            userSelect: 'none'
          }}
          title={`${node.name} (${node.code}) - KM ${node.chainage_km}`}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span
              style={{
                width: '6px',
                height: '6px',
                backgroundColor: isJunction ? '#38bdf8' : '#e2e8f0',
                borderRadius: '50%'
              }}
            />
            <span>{node.code}</span>
            <span style={{ color: '#94a3b8', fontWeight: 500 }}>{node.name}</span>
          </div>
          <div style={{ fontSize: '8.5px', color: '#cbd5e1', marginTop: '1px' }}>
            KM {node.chainage_km.toFixed(1)} • {node.platforms} PFs
          </div>
        </div>
      </Html>
    </group>
  );
};
