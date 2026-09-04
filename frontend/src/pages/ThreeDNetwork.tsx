import React, { useState, useMemo, useEffect } from 'react';
import { useNetworkData } from '../hooks/useNetworkData';
import { useScheduleData } from '../hooks/useScheduleData';
import { usePlanningSimulation, type TrainPosition } from '../hooks/usePlanningSimulation';

import { NetworkScene } from '../components/3d/NetworkScene';
import { Accessible2DNetwork } from '../components/3d/Accessible2DNetwork';
import { SceneControls } from '../components/3d/SceneControls';
import { TimelineController } from '../components/3d/TimelineController';
import { PlanningInspector } from '../components/3d/PlanningInspector';
import { PerfInstrumentationPanel } from '../components/3d/PerfInstrumentationPanel';
import { generateStressNetworkFixture } from '../fixtures/stressFixture';

export const ThreeDNetwork: React.FC = () => {
  const {
    geometry,
    scenario,
    assets,
    capabilities,
    loading: networkLoading,
    error: networkError,
    lastRefreshed,
    refresh: refreshNetwork,
    isDemo
  } = useNetworkData();

  const {
    schedule,
    kpis,
    loading: scheduleLoading,
    optimizing,
    solverProgress,
    viewMode,
    setViewMode,
    freezeWeek1,
    setFreezeWeek1,
    runOptimization
  } = useScheduleData();

  const [stressMode, setStressMode] = useState<boolean>(false);
  const [showPerfPanel, setShowPerfPanel] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      return new URLSearchParams(window.location.search).get('perf') === 'true';
    }
    return false;
  });

  const stressData = useMemo(() => {
    if (!stressMode) return null;
    return generateStressNetworkFixture();
  }, [stressMode]);

  const activeGeometry = stressMode ? stressData?.geometry || geometry : geometry;
  const activeScenario = stressMode ? stressData?.scenario || scenario : scenario;
  const activeAssets = stressMode
    ? stressData?.assets || assets
    : (activeGeometry?.assets && activeGeometry.assets.length > 0 ? activeGeometry.assets : assets);

  const tracks = useMemo(() => activeGeometry?.tracks || [], [activeGeometry]);

  const {
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
  } = usePlanningSimulation(activeScenario, schedule, tracks, isDemo);

  const [is2DView, setIs2DView] = useState<boolean>(false);
  const [showKpiDrawer, setShowKpiDrawer] = useState<boolean>(true);

  // Keyboard navigation shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.code === 'Space') {
        e.preventDefault();
        setIsPlaying((prev: boolean) => !prev);
      } else if (e.code === 'KeyR') {
        setCurrentTime(0);
      } else if (e.code === 'Digit1') {
        setPlaybackSpeed(1);
      } else if (e.code === 'Digit2') {
        setPlaybackSpeed(2);
      } else if (e.code === 'Digit5') {
        setPlaybackSpeed(5);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [setIsPlaying, setCurrentTime, setPlaybackSpeed]);

  const activePossessions = useMemo(() => {
    let count = 0;
    blockStates.forEach((s: { status: string }) => {
      if (s.status === 'active_maintenance' || s.status === 'shadow_block' || s.status === 'fixed_block') {
        count++;
      }
    });
    return count;
  }, [blockStates]);

  const movingTrainsCount = useMemo(() => {
    return trainPositions.filter((tp: TrainPosition) => tp.isMoving).length;
  }, [trainPositions]);

  const conflicts = schedule?.conflicts || geometry?.conflicts || [];

  if (networkLoading || scheduleLoading) {
    return (
      <div style={fullScreenCenter}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>⚡</div>
          <h2 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: 700, color: '#0f172a' }}>
            Initializing 3D Railway Corridor Scene...
          </h2>
          <p style={{ margin: 0, fontSize: '13px', color: '#64748b' }}>
            Loading track geometry, station nodes, and PySCIPOpt block allocation schedule.
          </p>
        </div>
      </div>
    );
  }

  if (networkError || !geometry) {
    return (
      <div style={fullScreenCenter}>
        <div style={{ maxWidth: '480px', padding: '24px', backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #fecaca', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
          <h3 style={{ margin: '0 0 8px 0', color: '#dc2626', fontSize: '16px' }}>Network Loading Error</h3>
          <p style={{ fontSize: '13px', color: '#475569', marginBottom: '16px' }}>
            {networkError || "Could not retrieve railway network geometry."}
          </p>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button onClick={() => refreshNetwork()} style={primaryBtnStyle}>
              Retry Connection
            </button>
            <button onClick={() => setIs2DView(true)} style={secondaryBtnStyle}>
              Open 2D Schematic
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: 'calc(100vh - 56px)', display: 'flex', flexDirection: 'column', overflow: 'hidden', backgroundColor: '#f8fafc', position: 'relative' }}>
      {/* 1. Operational Control Room Header */}
      <header
        style={{
          height: '48px',
          backgroundColor: '#ffffff',
          borderBottom: '1px solid #cbd5e1',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
          zIndex: 30
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '16px' }}>🛰</span>
            <span style={{ fontWeight: 800, fontSize: '14px', color: '#0f172a' }}>
              3D Railway Corridor
            </span>
          </div>
          <span style={{ color: '#cbd5e1' }}>|</span>
          <span style={{ fontSize: '12px', color: '#475569', fontWeight: 600 }}>
            {geometry.division} • {geometry.line_name} ({geometry.total_length_km} km)
          </span>

          {/* Badges */}
          <span style={badgeTagStyle(isDemo ? '#d97706' : '#059669')}>
            {isDemo ? 'DEMO MODE' : 'LIVE BACKEND'}
          </span>
          {geometry.is_synthetic && (
            <span style={badgeTagStyle('#475569')}>
              SYNTHETIC CORRIDOR
            </span>
          )}
          {schedule?.is_fallback && (
            <span style={badgeTagStyle('#dc2626')} title="Schedule produced via Non-Optimal Heuristic Fallback">
              NON-OPTIMAL FALLBACK
            </span>
          )}
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ fontSize: '11px', color: '#64748b' }}>
            Refreshed: {lastRefreshed.toLocaleTimeString()}
          </div>

          <button
            onClick={() => setStressMode(prev => !prev)}
            style={{
              ...secondaryBtnStyle,
              backgroundColor: stressMode ? '#7c3aed' : '#ffffff',
              color: stressMode ? '#ffffff' : '#0f172a',
              borderColor: stressMode ? '#6d28d9' : '#cbd5e1'
            }}
            title="Toggle deterministic 1,000-block, 5,000-asset stress test fixture"
          >
            {stressMode ? '⚡ Stress: 1,000 Blocks (ON)' : '⚡ Stress Fixture'}
          </button>

          <button
            onClick={() => setShowPerfPanel(prev => !prev)}
            style={{
              ...secondaryBtnStyle,
              backgroundColor: showPerfPanel ? '#0284c7' : '#ffffff',
              color: showPerfPanel ? '#ffffff' : '#0f172a',
              borderColor: showPerfPanel ? '#0369a1' : '#cbd5e1'
            }}
            title="Toggle WebGL performance instrumentation (FPS, draw calls, memory)"
          >
            {showPerfPanel ? '📊 Telemetry (ON)' : '📊 Telemetry'}
          </button>

          <button
            onClick={() => runOptimization()}
            disabled={optimizing}
            style={{
              ...primaryBtnStyle,
              backgroundColor: optimizing ? '#94a3b8' : '#0284c7',
              cursor: optimizing ? 'wait' : 'pointer'
            }}
            title="Trigger PySCIPOpt MILP rolling block optimization"
            aria-label="Run AI Block Planning"
          >
            {optimizing ? '⚡ Solving MILP...' : '⚡ Run AI Block Planning'}
          </button>

          <button
            onClick={() => setShowKpiDrawer(prev => !prev)}
            style={secondaryBtnStyle}
            title="Toggle KPI & Conflict Analytics Drawer"
          >
            {showKpiDrawer ? 'Hide KPIs' : 'Show KPIs'}
          </button>
        </div>
      </header>

      {/* 2. Top AI Planning & Schedule Filter Workspace Bar */}
      <div
        style={{
          padding: '8px 16px',
          backgroundColor: '#f1f5f9',
          borderBottom: '1px solid #cbd5e1',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '8px',
          fontSize: '12px',
          zIndex: 20
        }}
      >
        {/* Schedule View Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontWeight: 700, color: '#334155' }}>Schedule View:</span>
          {(['optimized', 'baseline', 'conflicts_only', 'shadow_only'] as const).map(mode => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              style={{
                padding: '4px 8px',
                borderRadius: '4px',
                border: '1px solid',
                borderColor: viewMode === mode ? '#0284c7' : '#cbd5e1',
                backgroundColor: viewMode === mode ? '#0284c7' : '#ffffff',
                color: viewMode === mode ? '#ffffff' : '#334155',
                fontWeight: 600,
                fontSize: '11px',
                cursor: 'pointer'
              }}
            >
              {mode === 'optimized' ? 'AI Optimized' : mode === 'baseline' ? 'Manual Baseline' : mode === 'conflicts_only' ? 'Conflicts Only' : 'Shadow Blocks Only'}
            </button>
          ))}
        </div>

        {/* Frozen Week 1 Toggle & Solver Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer', fontWeight: 600, color: '#334155' }}>
            <input
              type="checkbox"
              checked={freezeWeek1}
              onChange={(e) => setFreezeWeek1(e.target.checked)}
              style={{ accentColor: '#0284c7' }}
            />
            Freeze Week 1 Window
          </label>

          <div style={{ fontSize: '11px', color: '#475569' }}>
            Solver: <strong>{capabilities?.solver_name || schedule?.solver || 'PySCIPOpt'}</strong>
          </div>
        </div>
      </div>

      {/* 3. Collapsible KPI & Conflict Metric Strip */}
      {showKpiDrawer && kpis && (
        <div
          style={{
            padding: '8px 16px',
            backgroundColor: '#ffffff',
            borderBottom: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            overflowX: 'auto',
            zIndex: 20
          }}
        >
          <div style={kpiPillStyle}>
            <span style={{ color: '#64748b', fontSize: '10px' }}>BLOCK UTILIZATION (BUE)</span>
            <span style={{ fontWeight: 800, color: '#0f172a', fontSize: '13px' }}>
              {kpis.bue_percent.toFixed(1)}% <span style={{ fontSize: '10px', color: '#16a34a' }}>({(kpis.bue_percent - kpis.bue_baseline_percent).toFixed(1)}% vs base)</span>
            </span>
          </div>

          <div style={kpiPillStyle}>
            <span style={{ color: '#64748b', fontSize: '10px' }}>SHADOW BLOCK RATIO</span>
            <span style={{ fontWeight: 800, color: '#059669', fontSize: '13px' }}>
              {kpis.sbr_percent.toFixed(1)}% ({kpis.consolidated_blocks} groups)
            </span>
          </div>

          <div style={kpiPillStyle}>
            <span style={{ color: '#64748b', fontSize: '10px' }}>TOTAL CLOSURE TIME</span>
            <span style={{ fontWeight: 800, color: '#0f172a', fontSize: '13px' }}>
              {kpis.total_closure_hours.toFixed(1)}h <span style={{ fontSize: '10px', color: '#16a34a' }}>(-{(kpis.baseline_closure_hours - kpis.total_closure_hours).toFixed(1)}h saved)</span>
            </span>
          </div>

          <div style={kpiPillStyle}>
            <span style={{ color: '#64748b', fontSize: '10px' }}>PUNCTUALITY DELAY (PII)</span>
            <span style={{ fontWeight: 800, color: kpis.pii_delays > 10 ? '#dc2626' : '#0284c7', fontSize: '13px' }}>
              {kpis.pii_delays.toFixed(1)} min <span style={{ fontSize: '10px', color: '#16a34a' }}>(-{(kpis.pii_baseline_delays - kpis.pii_delays).toFixed(0)}m impact)</span>
            </span>
          </div>

          <div style={kpiPillStyle}>
            <span style={{ color: '#64748b', fontSize: '10px' }}>ACTIVE CONFLICTS</span>
            <span style={{ fontWeight: 800, color: conflicts.length > 0 ? '#dc2626' : '#16a34a', fontSize: '13px' }}>
              {conflicts.length} critical / major
            </span>
          </div>
        </div>
      )}

      {/* Solver Progress Banner if running */}
      {optimizing && (
        <div style={{ padding: '6px 16px', backgroundColor: '#e0f2fe', color: '#0369a1', fontSize: '11px', fontWeight: 600, borderBottom: '1px solid #bae6fd' }}>
          ⚡ {solverProgress || 'Solving railway block allocation...'}
        </div>
      )}

      {/* 4. Main Viewport Area (3D WebGL Scene or 2D Schematic Fallback) */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {/* Floating Viewport Controls */}
        <SceneControls
          cameraMode={cameraMode}
          onSetCameraMode={setCameraMode}
          onResetCamera={() => {
            setCameraMode('default');
            setFocusTarget(null);
          }}
          onFitNetwork={() => {
            setCameraMode('default');
            setFocusTarget([0, 0, 0]);
          }}
          is2DView={is2DView}
          onToggle2D={() => setIs2DView(prev => !prev)}
        />

        {/* Scene Viewport */}
        {is2DView ? (
          <Accessible2DNetwork
            geometry={activeGeometry}
            schedule={schedule}
            currentTime={currentTime}
            trainPositions={trainPositions}
            blockStates={blockStates}
            onSelectEntity={selectEntity}
            selectedEntityId={selectedEntity?.id}
          />
        ) : (
          <NetworkScene
            geometry={activeGeometry!}
            scenario={activeScenario}
            schedule={schedule}
            assets={activeAssets}
            trainPositions={trainPositions}
            blockStates={blockStates}
            cameraMode={cameraMode}
            selectedEntity={selectedEntity}
            onSelectEntity={selectEntity}
            focusTarget={focusTarget}
            onFallbackTo2D={() => setIs2DView(true)}
          />
        )}

        {/* Development WebGL Performance Instrumentation Panel */}
        <PerfInstrumentationPanel
          isVisible={showPerfPanel}
          onToggle={() => setShowPerfPanel(false)}
        />

        {/* Detail Inspector Drawer (Right Side) */}
        {selectedEntity && (
          <PlanningInspector
            entity={selectedEntity}
            onClose={() => selectEntity(null)}
            schedule={schedule}
          />
        )}

        {/* Bottom Timeline Controller */}
        <TimelineController
          currentTime={currentTime}
          onTimeChange={setCurrentTime}
          isPlaying={isPlaying}
          onTogglePlay={() => setIsPlaying((prev: boolean) => !prev)}
          playbackSpeed={playbackSpeed}
          onSpeedChange={setPlaybackSpeed}
          timeWindow={timeWindow}
          onWindowChange={setTimeWindow}
          maxHorizonHours={maxHorizonHours}
          activePossessionsCount={activePossessions}
          activeTrainsCount={movingTrainsCount}
        />
      </div>
    </div>
  );
};

const fullScreenCenter: React.CSSProperties = {
  width: '100%',
  height: 'calc(100vh - 56px)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  backgroundColor: '#f8fafc'
};

const primaryBtnStyle: React.CSSProperties = {
  padding: '6px 12px',
  backgroundColor: '#0284c7',
  color: '#ffffff',
  border: 'none',
  borderRadius: '4px',
  fontWeight: 700,
  fontSize: '11px',
  cursor: 'pointer'
};

const secondaryBtnStyle: React.CSSProperties = {
  padding: '6px 12px',
  backgroundColor: '#f8fafc',
  color: '#0f172a',
  border: '1px solid #cbd5e1',
  borderRadius: '4px',
  fontWeight: 600,
  fontSize: '11px',
  cursor: 'pointer'
};

const kpiPillStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  padding: '4px 10px',
  backgroundColor: '#f8fafc',
  border: '1px solid #e2e8f0',
  borderRadius: '6px',
  whiteSpace: 'nowrap'
};

const badgeTagStyle = (bg: string): React.CSSProperties => ({
  fontSize: '9.5px',
  fontWeight: 800,
  letterSpacing: '0.4px',
  padding: '2px 6px',
  borderRadius: '3px',
  backgroundColor: bg,
  color: '#ffffff'
});
