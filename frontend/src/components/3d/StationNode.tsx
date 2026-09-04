import React from 'react';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import type { StationNode as StationNodeType } from '../../api/types';

interface StationNodeProps {
  node: StationNodeType;
  isSelected?: boolean;
  onSelect?: () => void;
  showLabel?: boolean;
}

// Module-level shared geometries
const platformGeometry = new THREE.BoxGeometry(18, 0.8, 6);
const canopyGeometry = new THREE.BoxGeometry(16, 0.4, 5.2);
const pillarGeometry = new THREE.CylinderGeometry(0.15, 0.15, 2.4, 6);
const towerGeometry = new THREE.BoxGeometry(8, 3.5, 3);

// Module-level shared materials
const platformJunctionMaterial = new THREE.MeshStandardMaterial({ color: '#475569', roughness: 0.7 });
const platformStandardMaterial = new THREE.MeshStandardMaterial({ color: '#64748b', roughness: 0.7 });
const canopyJunctionMaterial = new THREE.MeshStandardMaterial({ color: '#0284c7', metalness: 0.4, roughness: 0.5 });
const canopyStandardMaterial = new THREE.MeshStandardMaterial({ color: '#94a3b8', metalness: 0.4, roughness: 0.5 });
const pillarMaterial = new THREE.MeshStandardMaterial({ color: '#334155' });
const towerMaterial = new THREE.MeshStandardMaterial({ color: '#e2e8f0', roughness: 0.3 });

export const StationNode: React.FC<StationNodeProps> = React.memo(({
  node,
  isSelected = false,
  onSelect,
  showLabel = true
}) => {
  const isJunction = node.node_type === 'junction' || node.node_type === 'terminal';
  const pos = node.position || node.coordinates;
  if (!pos) return null;
  const shouldRenderLabel = isSelected || showLabel;

  return (
    <group
      position={[pos.x, pos.y, pos.z]}
      onClick={(e) => { e.stopPropagation(); onSelect?.(); }}
    >
      {/* 1. Main Platform Concrete Base */}
      <mesh position={[0, 0.4, 0]}>
        <primitive object={platformGeometry} attach="geometry" />
        <primitive object={isJunction ? platformJunctionMaterial : platformStandardMaterial} attach="material" />
      </mesh>

      {/* 2. Platform Canopy Roof */}
      <mesh position={[0, 3.2, 0]}>
        <primitive object={canopyGeometry} attach="geometry" />
        <primitive object={isJunction ? canopyJunctionMaterial : canopyStandardMaterial} attach="material" />
      </mesh>

      {/* 3. Canopy Support Pillars */}
      {[-6, 0, 6].map((xOffset) => (
        <React.Fragment key={xOffset}>
          <mesh position={[xOffset, 1.8, 2.2]}>
            <primitive object={pillarGeometry} attach="geometry" />
            <primitive object={pillarMaterial} attach="material" />
          </mesh>
          <mesh position={[xOffset, 1.8, -2.2]}>
            <primitive object={pillarGeometry} attach="geometry" />
            <primitive object={pillarMaterial} attach="material" />
          </mesh>
        </React.Fragment>
      ))}

      {/* 4. Station Building Tower (for Junctions) */}
      {isJunction && (
        <mesh position={[0, 5.0, 4.5]}>
          <primitive object={towerGeometry} attach="geometry" />
          <primitive object={towerMaterial} attach="material" />
        </mesh>
      )}

      {/* 5. Station Nameplate / Billboard */}
      {shouldRenderLabel && (
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
      )}
    </group>
  );
}, (prev, next) => {
  return (
    prev.node.id === next.node.id &&
    prev.isSelected === next.isSelected &&
    prev.showLabel === next.showLabel
  );
});
