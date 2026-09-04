import React from 'react';
import type { CameraPreset } from '../../hooks/usePlanningSimulation';

interface SceneControlsProps {
  cameraMode: CameraPreset;
  onSetCameraMode: (mode: CameraPreset) => void;
  onResetCamera: () => void;
  onFitNetwork: () => void;
  is2DView: boolean;
  onToggle2D: () => void;
}

export const SceneControls: React.FC<SceneControlsProps> = ({
  cameraMode,
  onSetCameraMode,
  onResetCamera,
  onFitNetwork,
  is2DView,
  onToggle2D
}) => {
  return (
    <div
      style={{
        position: 'absolute',
        top: '16px',
        left: '16px',
        zIndex: 20,
        display: 'flex',
        flexWrap: 'wrap',
        gap: '6px',
        backgroundColor: 'rgba(255, 255, 255, 0.94)',
        padding: '6px 10px',
        borderRadius: '6px',
        boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
        border: '1px solid #cbd5e1',
        fontSize: '12px',
        fontFamily: 'system-ui, sans-serif'
      }}
      role="toolbar"
      aria-label="3D Viewport Controls"
    >
      <button
        onClick={onFitNetwork}
        style={btnStyle}
        title="Zoom and center entire 80km corridor"
        aria-label="Fit to Network"
      >
        <span>⛶</span> Fit Network
      </button>

      <button
        onClick={onResetCamera}
        style={btnStyle}
        title="Reset camera to default perspective angle"
        aria-label="Reset Camera"
      >
        <span>↺</span> Reset Angle
      </button>

      <button
        onClick={() => onSetCameraMode(cameraMode === 'top_down' ? 'default' : 'top_down')}
        style={{ ...btnStyle, backgroundColor: cameraMode === 'top_down' ? '#0284c7' : '#f8fafc', color: cameraMode === 'top_down' ? '#fff' : '#0f172a' }}
        title="Top-down orthographic tracking view"
        aria-label="Top-down View"
      >
        <span>⬇</span> Overhead Top-Down
      </button>

      <button
        onClick={() => onSetCameraMode(cameraMode === 'side_elevation' ? 'default' : 'side_elevation')}
        style={{ ...btnStyle, backgroundColor: cameraMode === 'side_elevation' ? '#0284c7' : '#f8fafc', color: cameraMode === 'side_elevation' ? '#fff' : '#0f172a' }}
        title="Side elevation profile showing gradients & bridges"
        aria-label="Elevation Profile View"
      >
        <span>↔</span> Side Elevation
      </button>

      <div style={{ width: '1px', backgroundColor: '#cbd5e1', margin: '0 4px' }} />

      <button
        onClick={onToggle2D}
        style={{
          ...btnStyle,
          backgroundColor: is2DView ? '#0f172a' : '#f1f5f9',
          color: is2DView ? '#ffffff' : '#0f172a',
          fontWeight: 700
        }}
        title="Switch to accessible high-contrast 2D schematic corridor view"
        aria-label={is2DView ? "Switch to 3D View" : "Switch to Accessible 2D Fallback"}
      >
        <span>{is2DView ? '🌐 3D View' : '🗺 2D Fallback'}</span>
      </button>
    </div>
  );
};

const btnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '4px',
  padding: '5px 9px',
  backgroundColor: '#f8fafc',
  color: '#0f172a',
  border: '1px solid #cbd5e1',
  borderRadius: '4px',
  fontSize: '11px',
  fontWeight: 600,
  cursor: 'pointer',
  transition: 'all 0.15s ease'
};
