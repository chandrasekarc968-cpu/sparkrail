import React from 'react';
import type { TimeWindowPreset } from '../../hooks/usePlanningSimulation';

interface TimelineControllerProps {
  currentTime: number;
  onTimeChange: (newTime: number) => void;
  isPlaying: boolean;
  onTogglePlay: () => void;
  playbackSpeed: number;
  onSpeedChange: (speed: number) => void;
  timeWindow: TimeWindowPreset;
  onWindowChange: (preset: TimeWindowPreset) => void;
  maxHorizonHours: number;
  activePossessionsCount: number;
  activeTrainsCount: number;
}

export const TimelineController: React.FC<TimelineControllerProps> = ({
  currentTime,
  onTimeChange,
  isPlaying,
  onTogglePlay,
  playbackSpeed,
  onSpeedChange,
  timeWindow,
  onWindowChange,
  maxHorizonHours,
  activePossessionsCount,
  activeTrainsCount
}) => {
  // Format hours to Day X, HH:MM
  const formatTime = (hours: number): string => {
    const day = Math.floor(hours / 24) + 1;
    const remHours = hours % 24;
    const h = Math.floor(remHours);
    const m = Math.floor((remHours - h) * 60);
    return `Day ${day} • ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')} (T+${hours.toFixed(1)}h)`;
  };

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '16px',
        left: '16px',
        right: '16px',
        zIndex: 20,
        backgroundColor: 'rgba(255, 255, 255, 0.96)',
        borderRadius: '8px',
        boxShadow: '0 4px 16px rgba(0, 0, 0, 0.12)',
        border: '1px solid #cbd5e1',
        padding: '12px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        fontFamily: 'system-ui, sans-serif'
      }}
      role="region"
      aria-label="Operations Timeline Controller"
    >
      {/* Top Bar: Playback Controls + Current Time Badge + Presets */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Play / Pause */}
          <button
            onClick={onTogglePlay}
            style={{
              padding: '6px 14px',
              backgroundColor: isPlaying ? '#e11d48' : '#0284c7',
              color: '#ffffff',
              border: 'none',
              borderRadius: '4px',
              fontWeight: 700,
              fontSize: '12px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
            title={isPlaying ? "Pause simulation replay (Space)" : "Play simulation replay (Space)"}
            aria-label={isPlaying ? "Pause Timeline" : "Play Timeline"}
          >
            <span>{isPlaying ? '❚❚ Pause' : '▶ Play'}</span>
          </button>

          {/* Reset to 0 */}
          <button
            onClick={() => onTimeChange(0)}
            style={subBtnStyle}
            title="Reset to origin T+0.0h"
            aria-label="Reset Time to Origin"
          >
            ⏮ Reset
          </button>

          {/* Playback Speed */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '2px', backgroundColor: '#f1f5f9', padding: '2px', borderRadius: '4px' }}>
            {[0.5, 1, 2, 5].map((spd) => (
              <button
                key={spd}
                onClick={() => onSpeedChange(spd)}
                style={{
                  ...speedBtnStyle,
                  backgroundColor: playbackSpeed === spd ? '#0f172a' : 'transparent',
                  color: playbackSpeed === spd ? '#ffffff' : '#475569'
                }}
                title={`Playback speed ${spd}x`}
              >
                {spd}x
              </button>
            ))}
          </div>
        </div>

        {/* Current Time Display */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              padding: '4px 12px',
              backgroundColor: '#0f172a',
              color: '#38bdf8',
              fontFamily: 'monospace',
              fontWeight: 800,
              fontSize: '13px',
              borderRadius: '4px',
              letterSpacing: '0.5px'
            }}
            aria-live="polite"
          >
            {formatTime(currentTime)}
          </div>

          <div style={{ display: 'flex', gap: '8px', fontSize: '11px', color: '#475569', fontWeight: 600 }}>
            <span>Possessions: <strong>{activePossessionsCount}</strong></span>
            <span>•</span>
            <span>Trains Running: <strong>{activeTrainsCount}</strong></span>
          </div>
        </div>

        {/* Horizon Presets */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          {(['today', '48h', 'week', 'rbp'] as TimeWindowPreset[]).map((preset) => (
            <button
              key={preset}
              onClick={() => onWindowChange(preset)}
              style={{
                ...presetBtnStyle,
                backgroundColor: timeWindow === preset ? '#0284c7' : '#f8fafc',
                color: timeWindow === preset ? '#ffffff' : '#334155',
                borderColor: timeWindow === preset ? '#0284c7' : '#cbd5e1'
              }}
            >
              {preset === 'today' ? 'Today (24h)' : preset === '48h' ? '48 Hours' : preset === 'week' ? 'Week (7d)' : 'RBP (28d)'}
            </button>
          ))}
        </div>
      </div>

      {/* Scrubber Bar */}
      <div style={{ position: 'relative', width: '100%', paddingTop: '4px' }}>
        <input
          type="range"
          min={0}
          max={maxHorizonHours}
          step={0.1}
          value={currentTime}
          onChange={(e) => onTimeChange(parseFloat(e.target.value))}
          style={{
            width: '100%',
            height: '8px',
            accentColor: '#0284c7',
            cursor: 'ew-resize'
          }}
          aria-label="Corridor Timeline Scrubber"
        />

        {/* Week 1 Frozen Boundary Marker if horizon > 7 days */}
        {maxHorizonHours > 168 && (
          <div
            style={{
              position: 'absolute',
              left: `${(168 / maxHorizonHours) * 100}%`,
              top: '0px',
              height: '24px',
              width: '2px',
              backgroundColor: '#06b6d4',
              zIndex: 2
            }}
            title="Week 1 Frozen Horizon Boundary"
          >
            <span style={{ position: 'absolute', top: '-14px', left: '-20px', fontSize: '9px', fontWeight: 700, color: '#0891b2', whiteSpace: 'nowrap' }}>
              W1 Frozen
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

const subBtnStyle: React.CSSProperties = {
  padding: '5px 10px',
  backgroundColor: '#f8fafc',
  color: '#0f172a',
  border: '1px solid #cbd5e1',
  borderRadius: '4px',
  fontSize: '11px',
  fontWeight: 600,
  cursor: 'pointer'
};

const speedBtnStyle: React.CSSProperties = {
  padding: '3px 7px',
  border: 'none',
  borderRadius: '3px',
  fontSize: '10px',
  fontWeight: 700,
  cursor: 'pointer'
};

const presetBtnStyle: React.CSSProperties = {
  padding: '4px 8px',
  border: '1px solid',
  borderRadius: '4px',
  fontSize: '11px',
  fontWeight: 600,
  cursor: 'pointer'
};
