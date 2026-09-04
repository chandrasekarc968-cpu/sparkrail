import React, { useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { updatePerfMetrics } from './perfStore';

interface PerfStatsCollectorProps {
  visibleCount: number;
  totalCount: number;
}

export const PerfStatsCollector: React.FC<PerfStatsCollectorProps> = ({
  visibleCount,
  totalCount
}) => {
  const { gl } = useThree();
  const lastTimeRef = useRef<number>(0);
  const frameCountRef = useRef<number>(0);
  const fpsRef = useRef<number>(60);

  useFrame(() => {
    const now = performance.now();
    if (lastTimeRef.current === 0) {
      lastTimeRef.current = now;
      return;
    }

    frameCountRef.current++;

    if (now - lastTimeRef.current >= 500) {
      const delta = (now - lastTimeRef.current) / 1000;
      fpsRef.current = Math.round(frameCountRef.current / delta);
      frameCountRef.current = 0;
      lastTimeRef.current = now;

      updatePerfMetrics({
        fps: fpsRef.current,
        frameTimeMs: Math.round((1000 / Math.max(1, fpsRef.current)) * 10) / 10,
        drawCalls: gl.info.render.calls,
        triangles: gl.info.render.triangles,
        geometries: gl.info.memory.geometries,
        textures: gl.info.memory.textures,
        visibleEntities: visibleCount,
        totalEntities: totalCount,
        lastUpdateMs: Math.round(now)
      });
    }
  });

  return null;
};
