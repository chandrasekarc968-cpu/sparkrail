import React, { useRef, useEffect, useMemo } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { OrbitControls, Grid } from '@react-three/drei';

import { RailwayTrack } from './RailwayTrack';
import { StationNode } from './StationNode';
import { TrainMarker } from './TrainMarker';
import { MaintenanceBlockVolume } from './MaintenanceBlockVolume';
import { ConflictMarker } from './ConflictMarker';
import { InstancedTrackAssets } from './InstancedTrackAssets';
import { ThreeDErrorBoundary } from './ThreeDErrorBoundary';
import { PerfStatsCollector } from './PerfStatsCollector';

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
  onFallbackTo2D?: () => void;
  maxLabelBudget?: number;
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
      maxDistance={800}
      maxPolarAngle={cameraMode === 'top_down' ? 0.05 : Math.PI / 2 - 0.05}
      dampingFactor={0.08}
      enableDamping
    />
  );
}

// Helper component for WebGLRenderer resource disposal on unmount
function RendererDisposer() {
  const { gl } = useThree();
  useEffect(() => {
    return () => {
      try {
        gl.dispose();
      } catch (e) {
        console.warn("WebGLRenderer disposal:", e);
      }
    };
  }, [gl]);
  return null;
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
  focusTarget,
  onFallbackTo2D,
  maxLabelBudget = 25
}) => {
  const tracks = useMemo(() => geometry.tracks || [], [geometry.tracks]);
  const nodes = useMemo(() => geometry.nodes || [], [geometry.nodes]);
  const oheMasts = useMemo(() => geometry.ohe_masts || [], [geometry.ohe_masts]);
  const signals = useMemo(() => geometry.signals || [], [geometry.signals]);
  const conflicts = useMemo(
    () => schedule?.conflicts || geometry.conflicts || [],
    [schedule?.conflicts, geometry.conflicts]
  );

  // Determine Level of Detail (LOD) based on network size
  const isLargeNetwork = tracks.length > 50;
  const globalLod: 'full' | 'simplified' | 'corridor' = isLargeNetwork ? 'simplified' : 'full';

  // Compute budgeted set of IDs that are permitted to render HTML overlays
  const visibleLabelIds = useMemo(() => {
    const ids = new Set<string>();
    let count = 0;

    // 1. Always show selected entity label
    if (selectedEntity) {
      ids.add(selectedEntity.id);
      count++;
    }

    // 2. Always show critical and major conflict labels
    conflicts.forEach(c => {
      if (c.severity === 'CRITICAL' || c.severity === 'MAJOR') {
        ids.add(c.id);
        count++;
      }
    });

    // 3. Active maintenance possession labels
    tracks.forEach(t => {
      if (count >= maxLabelBudget) return;
      const s = blockStates.get(t.block_id);
      if (s && (s.status === 'active_maintenance' || s.status === 'shadow_block')) {
        ids.add(t.block_id);
        count++;
      }
    });

    // 4. Moving trains
    trainPositions.forEach(tp => {
      if (count >= maxLabelBudget) return;
      if (tp.isMoving) {
        ids.add(tp.train.id);
        count++;
      }
    });

    // 5. Junction & Station nodes
    nodes.forEach(n => {
      if (count >= maxLabelBudget) return;
      if (n.node_type === 'junction' || n.node_type === 'terminal') {
        ids.add(n.id);
        count++;
      }
    });

    // 6. Remaining tracks up to budget
    tracks.forEach(t => {
      if (count >= maxLabelBudget) return;
      if (!ids.has(t.block_id)) {
        ids.add(t.block_id);
        count++;
      }
    });

    return ids;
  }, [selectedEntity, conflicts, tracks, blockStates, trainPositions, nodes, maxLabelBudget]);

  const totalEntityCount = tracks.length + nodes.length + trainPositions.length + oheMasts.length + signals.length + assets.length + conflicts.length;
  const visibleEntityCount = tracks.length + nodes.length + trainPositions.length + (isLargeNetwork ? Math.min(200, oheMasts.length) : oheMasts.length) + conflicts.length;

  return (
    <ThreeDErrorBoundary onFallbackTo2D={onFallbackTo2D}>
      <div style={{ width: '100%', height: '100%', position: 'relative' }}>
        <Canvas
          camera={{ position: [0, 160, 260], fov: 45, near: 1, far: 2000 }}
          style={{ background: '#0f172a' }}
          onPointerMissed={() => onSelectEntity(null)}
          gl={{ antialias: true, powerPreference: 'high-performance' }}
        >
          <RendererDisposer />
          <CameraController cameraMode={cameraMode} focusTarget={focusTarget} />
          <PerfStatsCollector visibleCount={visibleEntityCount} totalCount={totalEntityCount} />

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

          {/* Ground Grid */}
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
              showLabel={visibleLabelIds.has(track.block_id)}
              lod={globalLod}
            />
          ))}

          {/* 2. Stations & Junctions */}
          {nodes.map((node) => (
            <StationNode
              key={node.id}
              node={node}
              isSelected={selectedEntity?.type === 'asset' && selectedEntity.id === node.id}
              onSelect={() => onSelectEntity({ type: 'asset', id: node.id, data: node })}
              showLabel={visibleLabelIds.has(node.id)}
            />
          ))}

          {/* 3. Trains Moving along Corridor */}
          {trainPositions.map((tp) => (
            <TrainMarker
              key={tp.train.id}
              trainPos={tp}
              isSelected={selectedEntity?.type === 'train' && selectedEntity.id === tp.train.id}
              onSelect={() => onSelectEntity({ type: 'train', id: tp.train.id, data: tp.train })}
              showLabel={visibleLabelIds.has(tp.train.id)}
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
                  showLabel={visibleLabelIds.has(track.block_id)}
                />
              );
            }
            return null;
          })}

          {/* 5. Instanced Batching for Repeated Trackside Assets (Masts, Signals, Asset Pins) */}
          <InstancedTrackAssets
            oheMasts={oheMasts}
            signals={signals}
            assets={assets}
            onSelectEntity={onSelectEntity}
            selectedId={selectedEntity?.id}
          />

          {/* 6. Operational Conflicts */}
          {conflicts.map((conf) => (
            <ConflictMarker
              key={conf.id}
              conflict={conf}
              isSelected={selectedEntity?.type === 'conflict' && selectedEntity.id === conf.id}
              onSelect={() => onSelectEntity({ type: 'conflict', id: conf.id, data: conf })}
              showLabel={visibleLabelIds.has(conf.id)}
            />
          ))}
        </Canvas>
      </div>
    </ThreeDErrorBoundary>
  );
};
