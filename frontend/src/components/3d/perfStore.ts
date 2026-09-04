export interface PerfMetrics {
  fps: number;
  frameTimeMs: number;
  drawCalls: number;
  triangles: number;
  geometries: number;
  textures: number;
  visibleEntities: number;
  totalEntities: number;
  lastUpdateMs: number;
}

export const perfMetricsStore = {
  current: {
    fps: 60,
    frameTimeMs: 16.6,
    drawCalls: 0,
    triangles: 0,
    geometries: 0,
    textures: 0,
    visibleEntities: 0,
    totalEntities: 0,
    lastUpdateMs: 0
  } as PerfMetrics,
  listeners: new Set<(metrics: PerfMetrics) => void>()
};

export function updatePerfMetrics(metrics: Partial<PerfMetrics>): void {
  perfMetricsStore.current = { ...perfMetricsStore.current, ...metrics };
  perfMetricsStore.listeners.forEach(fn => fn(perfMetricsStore.current));
}
