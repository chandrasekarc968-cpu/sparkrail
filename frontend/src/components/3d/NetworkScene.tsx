import React, { useRef, useEffect } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { OrbitControls, Grid } from '@react-three/drei';

import { RailwayTrack } from './RailwayTrack';
import { StationNode } from './StationNode';
import { TrainMarker } from './TrainMarker';
import { MaintenanceBlockVolume } from './MaintenanceBlockVolume';
import { AssetMarker } from './AssetMarker';
import { ConflictMarker } from './ConflictMarker';

import type {
  NetworkGeometryResponse,
  Scenario,
  OptimizedSchedule,
  AssetHealthRecord
} from '../../api/types';
import type {
  CameraPreset,
  SelectedEntity,
  TrainPosition
} from '../../hooks/usePlanningSimulation';

export interface BlockStateScene {
  status: 'available' | 'active_maintenance' | 'planned_maintenance' | 'fixed_block' | 'conflict' | 'high_risk' | 'frozen_week1' | 'shadow_block';
  activeJobId?: string;
  department?: string;
  isShadow?: boolean;
  shadowWith?: string[];
  hasConflict?: boolean;
  conflictId?: string;
  isFrozen?: boolean;
}

interface NetworkSceneProps {
  geometry: NetworkGeometryResponse;
  scenario: Scenario | null;
  schedule: OptimizedSchedule | null;
  assets: AssetHealthRecord[];
  trainPositions: TrainPosition[];
  blockStates: Map<string, BlockStateScene>;
  cameraMode: CameraPreset;
  selectedEntity: SelectedEntity | null;
  onSelectEntity: (entity: SelectedEntity | null) => void;
  focusTarget: [number, number, number] | null;
}

// Sub-component to manage smooth camera transitions and views
function CameraController({
  cameraMode,
  focusTarget
}: {
  cameraMode: CameraPreset;
  focusTarget: [number, number, number] | null;
}) {
  const { camera } = useThree();
  const controlsRef = useRef<React.ComponentRef<typeof OrbitControls>>(null);

  useEffect(() => {
    if (cameraMode === 'top_down') {
      camera.position.set(0, 350, 0);
      camera.lookAt(0, 0, 0);
      if (controlsRef.current) {
        controlsRef.current.target.set(0, 0, 0);
        controlsRef.current.update();
      }
    } else if (cameraMode === 'side_elevation') {
      camera.position.set(0, 10, 220);
      camera.lookAt(0, 5, 0);
      if (controlsRef.current) {
        controlsRef.current.target.set(0, 5, 0);
        controlsRef.current.update();
      }
    } else {
      // Perspective
      camera.position.set(0, 160, 260);
      camera.lookAt(0, 0, 0);
      if (controlsRef.current) {
        controlsRef.current.target.set(0, 0, 0);
        controlsRef.current.update();
      }
    }
  }, [cameraMode, camera]);

  useEffect(() => {
    if (focusTarget && controlsRef.current) {
      controlsRef.current.target.set(focusTarget[0], focusTarget[1], focusTarget[2]);
      controlsRef.current.update();
    }
  }, [focusTarget]);

  return (
    <OrbitControls
      ref={controlsRef}
      makeDefault
      minDistance={10}
      maxDistance={600}
      maxPolarAngle={cameraMode === 'top_down' ? 0.05 : Math.PI / 2 - 0.05}
      dampingFactor={0.08}
      enableDamping
    />
  );
}

export const NetworkScene: React.FC<NetworkSceneProps> = ({
  geometry,
  scenario,
  schedule,
  assets,
  trainPositions,
  blockStates,
  cameraMode,
  selectedEntity,
  onSelectEntity,
  focusTarget
}) => {
  const tracks = geometry.tracks;
  const nodes = geometry.nodes;
  const oheMasts = geometry.ohe_masts || [];
  const conflicts = schedule?.conflicts || geometry.conflicts || [];

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Canvas
        camera={{ position: [0, 160, 260], fov: 45, near: 1, far: 2000 }}
        style={{ background: '#0f172a' }}
        onPointerMissed={() => onSelectEntity(null)}
      >
        <CameraController cameraMode={cameraMode} focusTarget={focusTarget} />

        {/* Lighting Setup */}
        <ambientLight intensity={0.8} />
        <directionalLight
          position={[100, 200, 100]}
          intensity={1.2}
          castShadow
        />
        <directionalLight
          position={[-100, 150, -100]}
          intensity={0.4}
        />

        {/* Ground Grid for Depth & Orientation */}
        <Grid
          position={[0, -0.5, 0]}
          args={[1000, 600]}
          cellSize={20}
          cellThickness={0.8}
          cellColor="#1e293b"
          sectionSize={100}
          sectionThickness={1.2}
          sectionColor="#334155"
          fadeDistance={700}
          fadeStrength={1}
        />

        {/* 1. Track Sections */}
        {tracks.map((track) => (
          <RailwayTrack
            key={track.block_id}
            track={track}
            state={blockStates.get(track.block_id)}
            isSelected={selectedEntity?.type === 'block' && selectedEntity.id === track.block_id}
            onSelect={() => onSelectEntity({ type: 'block', id: track.block_id, data: track })}
          />
        ))}

        {/* 2. Stations & Junctions */}
        {nodes.map((node) => (
          <StationNode
            key={node.id}
            node={node}
            isSelected={selectedEntity?.type === 'asset' && selectedEntity.id === node.id}
            onSelect={() => onSelectEntity({ type: 'asset', id: node.id, data: node })}
          />
        ))}

        {/* 3. Trains Moving along Corridor */}
        {trainPositions.map((tp) => (
          <TrainMarker
            key={tp.train.id}
            trainPos={tp}
            isSelected={selectedEntity?.type === 'train' && selectedEntity.id === tp.train.id}
            onSelect={() => onSelectEntity({ type: 'train', id: tp.train.id, data: tp.train })}
          />
        ))}

        {/* 4. Active Maintenance Possession Volumes */}
        {tracks.map((track) => {
          const state = blockStates.get(track.block_id);
          if (state && (state.status === 'active_maintenance' || state.status === 'shadow_block')) {
            return (
              <MaintenanceBlockVolume
                key={`vol_${track.block_id}`}
                track={track}
                jobId={state.activeJobId || 'JOB-ACTIVE'}
                department={state.department || 'Engineering'}
                isShadow={state.isShadow}
                shadowJobs={state.shadowWith}
                isSelected={selectedEntity?.type === 'job' && selectedEntity.id === state.activeJobId}
                onSelect={() => {
                  const job = scenario?.jobs.find(j => j.id === state.activeJobId);
                  onSelectEntity({ type: 'job', id: state.activeJobId || 'JOB', data: job || { id: state.activeJobId, department: state.department, block_id: track.block_id } });
                }}
              />
            );
          }
          return null;
        })}

        {/* 5. Physical OHE Masts & Critical Track Assets */}
        {oheMasts.slice(0, 24).map((mast) => (
          <AssetMarker
            key={mast.id}
            oheMast={mast}
            isSelected={selectedEntity?.id === mast.id}
            onSelect={() => onSelectEntity({ type: 'asset', id: mast.id, data: mast })}
          />
        ))}

        {assets.map((ast) => (
          <AssetMarker
            key={ast.asset_id}
            asset={ast}
            isSelected={selectedEntity?.id === ast.asset_id}
            onSelect={() => onSelectEntity({ type: 'asset', id: ast.asset_id, data: ast })}
          />
        ))}

        {/* 6. Operational Conflicts */}
        {conflicts.map((conf) => (
          <ConflictMarker
            key={conf.id}
            conflict={conf}
            isSelected={selectedEntity?.type === 'conflict' && selectedEntity.id === conf.id}
            onSelect={() => onSelectEntity({ type: 'conflict', id: conf.id, data: conf })}
          />
        ))}
      </Canvas>
    </div>
  );
};
