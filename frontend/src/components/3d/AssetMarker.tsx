import React from 'react';
import { Html } from '@react-three/drei';
import type { AssetHealthRecord, OHEMast } from '../../api/types';

interface AssetMarkerProps {
  asset?: AssetHealthRecord;
  oheMast?: OHEMast;
  isSelected?: boolean;
  onSelect?: () => void;
}

export const AssetMarker: React.FC<AssetMarkerProps> = ({
  asset,
  oheMast,
  isSelected = false,
  onSelect
}) => {
  // If rendering an OHE Mast
  if (oheMast) {
    const isIsolated = oheMast.is_isolated;
    return (
      <group
        position={[oheMast.position.x, oheMast.position.y, oheMast.position.z]}
        onClick={(e) => { e.stopPropagation(); onSelect?.(); }}
      >
        {/* Steel H-Beam Mast Pole */}
        <mesh position={[0, 2.75, 0]}>
          <cylinderGeometry args={[0.2, 0.25, 5.5, 8]} />
          <meshStandardMaterial
            color={isIsolated ? '#ef4444' : '#64748b'}
            metalness={0.7}
            roughness={0.4}
          />
        </mesh>
        {/* Horizontal Cantilever Arm over Track */}
        <mesh position={[0, 5.2, -1.2]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.1, 0.1, 2.4, 6]} />
          <meshStandardMaterial color="#475569" metalness={0.8} />
        </mesh>
        {/* Insulator Bell */}
        <mesh position={[0, 4.8, -1.8]}>
          <cylinderGeometry args={[0.2, 0.15, 0.6, 8]} />
          <meshStandardMaterial color="#38bdf8" roughness={0.2} />
        </mesh>
      </group>
    );
  }

  // If rendering an inspected track asset
  if (asset) {
    const isCritical = asset.defect_severity === 'Critical';
    const isMajor = asset.defect_severity === 'Major';
    const badgeColor = isCritical ? '#ef4444' : isMajor ? '#f59e0b' : '#10b981';

    return (
      <group
        position={[
          -400.0 + (asset.chainage_start_km / 80.0) * 800.0,
          2.0,
          asset.asset_type === 'Point Machine' ? 2.5 : 0.0
        ]}
        onClick={(e) => { e.stopPropagation(); onSelect?.(); }}
      >
        {/* Inspection Pin Marker */}
        <mesh position={[0, 1.2, 0]}>
          <cylinderGeometry args={[0.08, 0.08, 2.4, 8]} />
          <meshStandardMaterial color={badgeColor} />
        </mesh>
        <mesh position={[0, 2.5, 0]}>
          <sphereGeometry args={[0.45, 12, 12]} />
          <meshStandardMaterial color={badgeColor} roughness={0.3} metalness={0.2} />
        </mesh>

        {/* Telemetry Badge */}
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
      </group>
    );
  }

  return null;
};
