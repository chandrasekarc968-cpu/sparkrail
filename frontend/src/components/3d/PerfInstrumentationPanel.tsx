import React, { useState, useEffect } from 'react';
import { perfMetricsStore, type PerfMetrics } from './perfStore';

interface PerfInstrumentationPanelProps {
  isVisible?: boolean;
  onToggle?: () => void;
}

export const PerfInstrumentationPanel: React.FC<PerfInstrumentationPanelProps> = ({
  isVisible = true,
  onToggle
}) => {
  const [metrics, setMetrics] = useState<PerfMetrics>(perfMetricsStore.current);

  useEffect(() => {
    const listener = (m: PerfMetrics) => setMetrics({ ...m });
    perfMetricsStore.listeners.add(listener);
    return () => {
      perfMetricsStore.listeners.delete(listener);
    };
  }, []);

  if (!isVisible) return null;

  const fpsColor = metrics.fps >= 50 ? '#10b981' : metrics.fps >= 30 ? '#f59e0b' : '#ef4444';

  return (
    <div
      role="region"
      aria-label="3D WebGL Performance Instrumentation"
      style={{
        position: 'absolute',
        top: '12px',
        right: '12px',
        backgroundColor: 'rgba(15, 23, 42, 0.88)',
        backdropFilter: 'blur(8px)',
        border: '1px solid #334155',
        borderRadius: '8px',
        padding: '10px 14px',
        color: '#f8fafc',
        fontFamily: 'monospace',
        fontSize: '11px',
        boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
        zIndex: 40,
        minWidth: '180px',
        pointerEvents: 'auto'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', borderBottom: '1px solid #334155', paddingBottom: '4px' }}>
        <span style={{ fontWeight: 800, color: '#38bdf8', letterSpacing: '0.5px' }}>⚡ WEBGL TELEMETRY</span>
        {onToggle && (
          <button
            onClick={onToggle}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '10px' }}
            title="Minimize instrumentation panel"
          >
            ✕
          </button>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ color: '#94a3b8' }}>Frame Rate:</span>
        <span style={{ fontWeight: 800, color: fpsColor }}>{metrics.fps} FPS</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ color: '#94a3b8' }}>Frame Time:</span>
        <span>{metrics.frameTimeMs} ms</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ color: '#94a3b8' }}>Draw Calls:</span>
        <span style={{ color: metrics.drawCalls > 100 ? '#f59e0b' : '#38bdf8' }}>{metrics.drawCalls}</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ color: '#94a3b8' }}>Visible Entities:</span>
        <span>{metrics.visibleEntities} / {metrics.totalEntities}</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ color: '#94a3b8' }}>Geometries:</span>
        <span>{metrics.geometries}</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span style={{ color: '#94a3b8' }}>Textures:</span>
        <span>{metrics.textures}</span>
      </div>
    </div>
  );
};
