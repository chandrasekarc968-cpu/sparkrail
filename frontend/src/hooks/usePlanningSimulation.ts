import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import type {
  Scenario,
  OptimizedSchedule,
  TrackGeometry,
  Train,
  Vector3D
} from '../api/types';

export type TimeWindowPreset = 'today' | '48h' | 'week' | 'rbp';
export type CameraPreset = 'default' | 'top_down' | 'side_elevation';

export interface SelectedEntity {
  type: 'block' | 'job' | 'train' | 'asset' | 'conflict';
  id: string;
  data: unknown;
}

export interface TrainPosition {
  train: Train;
  currentBlockId: string;
  position: Vector3D;
  progress: number; // 0.0 to 1.0 along current block
  isMoving: boolean;
  affectedByMaintenance: boolean;
}

export function usePlanningSimulation(
  scenario: Scenario | null,
  schedule: OptimizedSchedule | null,
  tracks: TrackGeometry[]
) {
  const [currentTime, setCurrentTime] = useState<number>(3.5); // Start at 3.5h (mid-morning operations)
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [timeWindow, setTimeWindow] = useState<TimeWindowPreset>('today');
  const [cameraMode, setCameraMode] = useState<CameraPreset>('default');
  const [selectedEntity, setSelectedEntity] = useState<SelectedEntity | null>(null);
  const [focusTarget, setFocusTarget] = useState<[number, number, number] | null>(null);

  // Maximum time based on window preset
  const maxHorizonHours = useMemo(() => {
    switch (timeWindow) {
      case 'today': return 24.0;
      case '48h': return 48.0;
      case 'week': return 168.0;
      case 'rbp': return 672.0;
    }
  }, [timeWindow]);

  // Animation frame loop for timeline replay
  const lastTickRef = useRef<number>(0);
  useEffect(() => {
    if (!isPlaying) return;

    let animId: number;
    const tick = (now: number) => {
      const last = lastTickRef.current === 0 ? now : lastTickRef.current;
      const deltaSec = (now - last) / 1000;
      lastTickRef.current = now;

      // 1 real second = 0.5 simulation hours at 1x speed
      const hoursAdvance = deltaSec * 0.5 * playbackSpeed;
      setCurrentTime(prev => {
        const next = prev + hoursAdvance;
        if (next >= maxHorizonHours) {
          return 0; // loop back in demo replay
        }
        return next;
      });

      animId = requestAnimationFrame(tick);
    };

    lastTickRef.current = performance.now();
    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [isPlaying, playbackSpeed, maxHorizonHours]);

  // Track map for fast spatial coordinate lookup
  const trackMap = useMemo(() => {
    const map = new Map<string, TrackGeometry>();
    tracks.forEach(t => map.set(t.block_id, t));
    return map;
  }, [tracks]);

  // Compute active train positions at currentTime
  const trainPositions = useMemo<TrainPosition[]>(() => {
    if (!scenario || !scenario.trains) return [];

    return scenario.trains.map(train => {
      const { scheduled_start, scheduled_end, route } = train;
      const duration = Math.max(0.1, scheduled_end - scheduled_start);

      // Check if train is active on the network at currentTime
      if (currentTime < scheduled_start) {
        // Train parked at first station
        const firstTrack = trackMap.get(route[0]);
        const pos = firstTrack ? firstTrack.start_coord : { x: -400, y: 0, z: 0 };
        return {
          train,
          currentBlockId: route[0],
          position: pos,
          progress: 0,
          isMoving: false,
          affectedByMaintenance: false
        };
      }

      if (currentTime >= scheduled_end) {
        // Train arrived at terminus
        const lastBlockId = route[route.length - 1];
        const lastTrack = trackMap.get(lastBlockId);
        const pos = lastTrack ? lastTrack.end_coord : { x: 400, y: 0, z: 0 };
        return {
          train,
          currentBlockId: lastBlockId,
          position: pos,
          progress: 1,
          isMoving: false,
          affectedByMaintenance: false
        };
      }

      // Train is running along its route
      const timeInTransit = currentTime - scheduled_start;
      const overallProgress = Math.min(1.0, Math.max(0.0, timeInTransit / duration));
      
      const blockIndex = Math.min(
        route.length - 1,
        Math.floor(overallProgress * route.length)
      );
      const currBlockId = route[blockIndex];
      const track = trackMap.get(currBlockId);

      const blockProgress = (overallProgress * route.length) - blockIndex;
      
      let pos: Vector3D = { x: 0, y: 0, z: 0 };
      if (track) {
        const startX = track.start_coord.x;
        const endX = track.end_coord.x;
        const startZ = track.start_coord.z;
        const endZ = track.end_coord.z;
        const startY = track.start_coord.y;
        const endY = track.end_coord.y;

        pos = {
          x: startX + (endX - startX) * blockProgress,
          y: startY + (endY - startY) * blockProgress + 0.5,
          z: startZ + (endZ - startZ) * blockProgress
        };
      }

      // Check if current block has active maintenance possession
      let affected = false;
      if (schedule && schedule.scheduled_jobs) {
        affected = schedule.scheduled_jobs.some(
          j => j.block_id === currBlockId && currentTime >= j.start_time && currentTime <= j.end_time
        );
      }

      return {
        train,
        currentBlockId: currBlockId,
        position: pos,
        progress: blockProgress,
        isMoving: true,
        affectedByMaintenance: affected
      };
    });
  }, [scenario, currentTime, trackMap, schedule]);

  // Operational state for each block at currentTime
  const blockStates = useMemo(() => {
    const states = new Map<string, {
      status: 'available' | 'active_maintenance' | 'planned_maintenance' | 'fixed_block' | 'conflict' | 'high_risk' | 'frozen_week1' | 'shadow_block';
      activeJobId?: string;
      department?: string;
      isShadow?: boolean;
      shadowWith?: string[];
      hasConflict?: boolean;
      conflictId?: string;
      isFrozen?: boolean;
    }>();

    if (!scenario) return states;

    // Check fixed blocks
    const activeFixed = scenario.fixed_blocks.filter(
      fb => currentTime >= fb.start_time && currentTime <= fb.end_time
    );

    // Check scheduled maintenance
    const activeScheduled = schedule?.scheduled_jobs?.filter(
      j => currentTime >= j.start_time && currentTime <= j.end_time
    ) || [];

    const plannedScheduled = schedule?.scheduled_jobs?.filter(
      j => currentTime < j.start_time
    ) || [];

    // Check conflicts
    const conflicts = schedule?.conflicts || [];

    scenario.blocks.forEach(block => {
      // 1. Conflict priority
      const blockConflict = conflicts.find(c => c.block_id === block.id);
      if (blockConflict && (blockConflict.severity === 'CRITICAL' || blockConflict.severity === 'MAJOR')) {
        states.set(block.id, {
          status: 'conflict',
          hasConflict: true,
          conflictId: blockConflict.id
        });
        return;
      }

      // 2. Fixed immutable block
      const fb = activeFixed.find(f => f.block_id === block.id);
      if (fb) {
        states.set(block.id, {
          status: 'fixed_block',
          department: fb.department || 'Engineering',
          activeJobId: fb.id
        });
        return;
      }

      // 3. Active maintenance (Shadow vs Single)
      const sj = activeScheduled.find(j => j.block_id === block.id);
      if (sj) {
        if (sj.is_shadow_block) {
          states.set(block.id, {
            status: 'shadow_block',
            activeJobId: sj.job_id,
            department: sj.department,
            isShadow: true,
            shadowWith: sj.shadow_with_jobs
          });
        } else {
          states.set(block.id, {
            status: 'active_maintenance',
            activeJobId: sj.job_id,
            department: sj.department
          });
        }
        return;
      }

      // 4. Week 1 Frozen boundary condition
      if (currentTime <= 24.0 * 7 && plannedScheduled.some(p => p.block_id === block.id && p.start_time <= 24.0 * 7)) {
        states.set(block.id, {
          status: 'frozen_week1',
          isFrozen: true
        });
        return;
      }

      // 5. Planned maintenance in future
      const pj = plannedScheduled.find(j => j.block_id === block.id);
      if (pj) {
        states.set(block.id, {
          status: 'planned_maintenance',
          activeJobId: pj.job_id,
          department: pj.department
        });
        return;
      }

      // Default: Available
      states.set(block.id, { status: 'available' });
    });

    return states;
  }, [scenario, schedule, currentTime]);

  const selectEntity = useCallback((entity: SelectedEntity | null) => {
    setSelectedEntity(entity);
    if (!entity) {
      setFocusTarget(null);
      return;
    }

    if (entity.type === 'block') {
      const track = trackMap.get(entity.id);
      if (track) {
        setFocusTarget([track.start_coord.x + 50, track.start_coord.y, track.start_coord.z]);
      }
    } else if (entity.type === 'train') {
      const tp = trainPositions.find(t => t.train.id === entity.id);
      if (tp) {
        setFocusTarget([tp.position.x, tp.position.y, tp.position.z]);
      }
    } else if (entity.type === 'conflict') {
      const pos = (entity.data as { position?: Vector3D })?.position;
      if (pos) {
        setFocusTarget([pos.x, pos.y, pos.z]);
      }
    }
  }, [trackMap, trainPositions]);

  return {
    currentTime,
    setCurrentTime,
    isPlaying,
    setIsPlaying,
    playbackSpeed,
    setPlaybackSpeed,
    timeWindow,
    setTimeWindow,
    cameraMode,
    setCameraMode,
    selectedEntity,
    selectEntity,
    focusTarget,
    setFocusTarget,
    trainPositions,
    blockStates,
    maxHorizonHours
  };
}
