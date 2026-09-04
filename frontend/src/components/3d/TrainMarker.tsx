import React from 'react';
import { Html } from '@react-three/drei';
import type { TrainPosition } from '../../hooks/usePlanningSimulation';

interface TrainMarkerProps {
  trainPos: TrainPosition;
  isSelected?: boolean;
  onSelect?: () => void;
}

export const TrainMarker: React.FC<TrainMarkerProps> = ({
  trainPos,
  isSelected = false,
  onSelect
}) => {
  const { train, position, isMoving, affectedByMaintenance } = trainPos;
  const isPremium = train.category === 'premium';
  const isFreight = train.category === 'freight';

  // Locomotive Body Colors
  const locoColor = isPremium ? '#d97706' : isFreight ? '#78350f' : '#1d4ed8'; // Amber gold vs dark rust vs royal blue

  return (
    <group
      position={[position.x, position.y + 0.8, position.z]}
      onClick={(e) => { e.stopPropagation(); onSelect?.(); }}
    >
      {/* 1. Main Locomotive Cabin */}
      <mesh position={[0, 0.9, 0]}>
        <boxGeometry args={[7, 1.8, 2.2]} />
        <meshStandardMaterial
          color={isSelected ? '#38bdf8' : locoColor}
          metalness={0.6}
          roughness={0.3}
        />
      </mesh>

      {/* 2. Trailing Coach 1 */}
      <mesh position={[-8, 0.85, 0]}>
        <boxGeometry args={[6.5, 1.7, 2.1]} />
        <meshStandardMaterial
          color={isPremium ? '#f8fafc' : '#334155'}
          metalness={0.3}
          roughness={0.6}
        />
      </mesh>

      {/* 3. Trailing Coach 2 */}
      <mesh position={[-15.5, 0.85, 0]}>
        <boxGeometry args={[6.5, 1.7, 2.1]} />
        <meshStandardMaterial
          color={isPremium ? '#f8fafc' : '#334155'}
          metalness={0.3}
          roughness={0.6}
        />
      </mesh>

      {/* 4. Aerodynamic Nose Cone (for Premium Vande Bharat / Rajdhani) */}
      {isPremium && (
        <mesh position={[3.8, 0.7, 0]} rotation={[0, 0, -Math.PI / 2]}>
          <coneGeometry args={[1.0, 1.6, 12]} />
          <meshStandardMaterial color="#f8fafc" metalness={0.4} roughness={0.3} />
        </mesh>
      )}

      {/* 5. Headlight Beam (when active) */}
      {isMoving && (
        <mesh position={[4.6, 0.7, 0]}>
          <sphereGeometry args={[0.3, 8, 8]} />
          <meshBasicMaterial color="#fef08a" />
        </mesh>
      )}

      {/* 6. Selection Beacon Ring */}
      {isSelected && (
        <mesh position={[0, -0.4, 0]}>
          <cylinderGeometry args={[4.5, 4.5, 0.2, 16]} />
          <meshBasicMaterial color="#38bdf8" wireframe transparent opacity={0.6} />
        </mesh>
      )}

      {/* 7. Train Information Tag */}
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 800 }}>
            <span
              style={{
                width: '6px',
                height: '6px',
                backgroundColor: isPremium ? '#f59e0b' : '#38bdf8',
                borderRadius: '50%'
              }}
            />
            <span>{train.id}</span>
            <span style={{ color: '#94a3b8', fontSize: '8.5px' }}>
              {isPremium ? '★ PREM' : isFreight ? 'FRT' : 'EXP'}
            </span>
          </div>
          <div style={{ fontSize: '8px', color: '#cbd5e1' }}>
            {isMoving ? `${train.max_speed_kmh || 100} km/h` : 'Station Stop'}
            {(train.current_delay_min || 0) > 0 && (
              <span style={{ color: '#f87171', marginLeft: '3px' }}>
                +{train.current_delay_min}m
              </span>
            )}
            {affectedByMaintenance && (
              <span style={{ color: '#ef4444', marginLeft: '3px', fontWeight: 800 }}>
                [BLOCK CONFLICT]
              </span>
            )}
          </div>
        </div>
      </Html>
    </group>
  );
};
