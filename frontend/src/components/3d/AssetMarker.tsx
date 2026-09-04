import React from 'react';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import type { AssetHealthRecord, OHEMast } from '../../api/types';

interface AssetMarkerProps {
  asset?: AssetHealthRecord;
  oheMast?: OHEMast;
  isSelected?: boolean;
  onSelect?: () => void;
  showLabel?: boolean;
}

const pinGeometry = new THREE.CylinderGeometry(0.08, 0.08, 2.4, 8);
const sphereGeometry = new THREE.SphereGeometry(0.45, 10, 10);
const mastPoleGeometry = new THREE.CylinderGeometry(0.2, 0.25, 5.5, 8);
const mastArmGeometry = new THREE.CylinderGeometry(0.1, 0.1, 2.4, 6);
const mastInsulatorGeometry = new THREE.CylinderGeometry(0.2, 0.15, 0.6, 8);

const normalMastMat = new THREE.MeshStandardMaterial({ color: '#64748b', metalness: 0.7, roughness: 0.4 });
const isolatedMastMat = new THREE.MeshStandardMaterial({ color: '#ef4444', metalness: 0.7, roughness: 0.4 });
const armMat = new THREE.MeshStandardMaterial({ color: '#475569', metalness: 0.8 });
const insulatorMat = new THREE.MeshStandardMaterial({ color: '#38bdf8', roughness: 0.2 });

export const AssetMarker: React.FC<AssetMarkerProps> = React.memo(({
  asset,
  oheMast,
  isSelected = false,
  onSelect,
  showLabel = true
}) => {
  // If rendering an OHE Mast
  if (oheMast) {
    const isIsolated = oheMast.is_isolated;
    const pos = oheMast.position || oheMast.coordinates;
    if (!pos) return null;
    return (
      <group
        position={[pos.x, pos.y, pos.z]}
        onClick={(e) => { e.stopPropagation(); onSelect?.(); }}
      >
        {/* Steel H-Beam Mast Pole */}
        <mesh position={[0, 2.75, 0]}>
          <primitive object={mastPoleGeometry} attach="geometry" />
          <primitive object={isIsolated ? isolatedMastMat : normalMastMat} attach="material" />
        </mesh>
        {/* Horizontal Cantilever Arm over Track */}
        <mesh position={[0, 5.2, -1.2]} rotation={[0, 0, Math.PI / 2]}>
          <primitive object={mastArmGeometry} attach="geometry" />
          <primitive object={armMat} attach="material" />
        </mesh>
        {/* Insulator Bell */}
        <mesh position={[0, 4.8, -1.8]}>
          <primitive object={mastInsulatorGeometry} attach="geometry" />
          <primitive object={insulatorMat} attach="material" />
        </mesh>
      </group>
    );
  }

  // If rendering an inspected track asset
  if (asset) {
    const pos = asset.position || asset.coordinates;
    if (!pos) return null;
    const isCritical = asset.defect_severity === 'Critical';
    const isMajor = asset.defect_severity === 'Major';
    const badgeColor = isCritical ? '#ef4444' : isMajor ? '#f59e0b' : '#10b981';
    const shouldRenderLabel = isSelected || showLabel;

    return (
      <group
        position={[pos.x, pos.y, pos.z]}
        onClick={(e) => { e.stopPropagation(); onSelect?.(); }}
      >
        {/* Inspection Pin Marker */}
        <mesh position={[0, 1.2, 0]}>
          <primitive object={pinGeometry} attach="geometry" />
          <meshStandardMaterial color={badgeColor} />
        </mesh>
        <mesh position={[0, 2.5, 0]}>
          <primitive object={sphereGeometry} attach="geometry" />
          <meshStandardMaterial color={badgeColor} roughness={0.3} metalness={0.2} />
        </mesh>

        {/* Telemetry Badge */}
        {shouldRenderLabel && (
          <Html position={[0, 3.8, 0]} center distanceFactor={140}>
            <div
              style={{
                padding: '3px 7px',
                backgroundColor: isSelected ? '#0369a1' : '#0f172a',
                color: '#ffffff',
                borderRadius: '4px',
                border: `1.5px solid ${badgeColor}`,
                boxShadow: '0 2px 6px rgba(0,0,0,0.25)',
                fontSize: '9px',
                fontFamily: 'monospace',
                whiteSpace: 'nowrap',
                cursor: 'pointer',
                userSelect: 'none'
              }}
              title={`${asset.name} (${asset.asset_type}) - Health: ${asset.health_score}%`}
            >
              <div style={{ fontWeight: 800 }}>{asset.asset_id}</div>
              <div style={{ color: badgeColor, fontSize: '8px' }}>
                {asset.health_score}% • {asset.defect_severity}
              </div>
            </div>
          </Html>
        )}
      </group>
    );
  }

  return null;
}, (prev, next) => {
  return (
    prev.asset?.asset_id === next.asset?.asset_id &&
    prev.oheMast?.id === next.oheMast?.id &&
    prev.isSelected === next.isSelected &&
    prev.showLabel === next.showLabel
  );
});
