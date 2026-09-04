import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { BrowserRouter } from 'react-router-dom';

import { ApiClient } from '../api/client';
import { mockNetworkGeometry, mockSchedule } from '../api/mockData';
import { Accessible2DNetwork } from '../components/3d/Accessible2DNetwork';
import { TimelineController } from '../components/3d/TimelineController';
import { PlanningInspector } from '../components/3d/PlanningInspector';
import { SceneControls } from '../components/3d/SceneControls';
import { AppLayout } from '../components/layout/AppLayout';
import { AppProvider } from '../context/AppContext';

describe('3D Railway Network & Planning Capabilities', () => {
  it('retrieves valid 3D network geometry and planning capabilities from ApiClient', async () => {
    const geometry = await ApiClient.getNetworkGeometry();
    expect(geometry.division).toContain('Prayagraj');
    expect(geometry.tracks).toHaveLength(8);
    expect(geometry.nodes).toHaveLength(9);
    expect(geometry.signals.length).toBeGreaterThanOrEqual(16);
    expect(geometry.ohe_masts.length).toBeGreaterThanOrEqual(24);
    expect(geometry.is_synthetic).toBe(true);

    const capabilities = await ApiClient.getPlanningCapabilities();
    expect(capabilities.solver_name).toContain('PySCIPOpt');
    expect(capabilities.supports_3d_geometry).toBe(true);
    expect(capabilities.demo_mode).toBe(true);
    expect(capabilities.max_blocks_capacity).toBe(100);
  });

  it('renders Accessible2DNetwork schematic view with high-contrast elements and tables', () => {
    const mockBlockStates = new Map([
      ['B1', { status: 'fixed_block', activeJobId: 'FB1' }],
      ['B2', { status: 'conflict', hasConflict: true }],
      ['B3', { status: 'available' }],
      ['B4', { status: 'shadow_block', isShadow: true, activeJobId: 'J1' }]
    ]);

    render(
      <Accessible2DNetwork
        geometry={mockNetworkGeometry}
        schedule={mockSchedule}
        currentTime={4.0}
        trainPositions={[]}
        blockStates={mockBlockStates}
        onSelectEntity={() => {}}
      />
    );

    expect(screen.getByRole('region', { name: /Accessible 2D Corridor Schematic View/i })).toBeInTheDocument();
    expect(screen.getByText(/Subedarganj - Mirzapur/i)).toBeInTheDocument();
    expect(screen.getByText(/Corridor Operational Status Table/i)).toBeInTheDocument();
    expect(screen.getAllByText('B1').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('B4').length).toBeGreaterThanOrEqual(1);
  });

  it('renders TimelineController with scrubber, playback controls, and presets', () => {
    const onTimeChange = vi.fn();
    const onTogglePlay = vi.fn();
    const onSpeedChange = vi.fn();
    const onWindowChange = vi.fn();

    render(
      <TimelineController
        currentTime={5.5}
        onTimeChange={onTimeChange}
        isPlaying={false}
        onTogglePlay={onTogglePlay}
        playbackSpeed={1}
        onSpeedChange={onSpeedChange}
        timeWindow="today"
        onWindowChange={onWindowChange}
        maxHorizonHours={24}
        activePossessionsCount={2}
        activeTrainsCount={3}
      />
    );

    expect(screen.getByRole('region', { name: /Operations Timeline Controller/i })).toBeInTheDocument();
    expect(screen.getByText(/T\+5.5h/i)).toBeInTheDocument();
    expect(screen.getByText(/Possessions:/i)).toBeInTheDocument();
    expect(screen.getByText(/Trains Running:/i)).toBeInTheDocument();

    const playBtn = screen.getByRole('button', { name: /Play Timeline/i });
    fireEvent.click(playBtn);
    expect(onTogglePlay).toHaveBeenCalledOnce();

    const speedBtn = screen.getByRole('button', { name: '2x' });
    fireEvent.click(speedBtn);
    expect(onSpeedChange).toHaveBeenCalledWith(2);

    const weekPresetBtn = screen.getByRole('button', { name: /Week \(7d\)/i });
    fireEvent.click(weekPresetBtn);
    expect(onWindowChange).toHaveBeenCalledWith('week');
  });

  it('renders PlanningInspector with block details and job explainability without fake scores', () => {
    const onClose = vi.fn();

    render(
      <PlanningInspector
        entity={{
          type: 'block',
          id: 'B1',
          data: {
            chainage_start: 0,
            chainage_end: 10,
            description: 'Subedarganj to Prayagraj',
            speed_restriction_kmh: 110,
            electrification_status: '25kV AC',
            signaling_type: 'Automatic'
          }
        }}
        onClose={onClose}
        schedule={mockSchedule}
      />
    );

    expect(screen.getByRole('complementary', { name: /Planning Detail Inspector/i })).toBeInTheDocument();
    expect(screen.getByText('B1')).toBeInTheDocument();
    expect(screen.getByText(/Subedarganj to Prayagraj/i)).toBeInTheDocument();
    expect(screen.getByText(/110 km\/h/i)).toBeInTheDocument();

    const closeBtn = screen.getByRole('button', { name: /Close Inspector/i });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('renders SceneControls and triggers camera and 2D fallback toggles', () => {
    const onReset = vi.fn();
    const onFit = vi.fn();
    const onToggle2D = vi.fn();
    const onSetCameraMode = vi.fn();

    render(
      <SceneControls
        cameraMode="default"
        onSetCameraMode={onSetCameraMode}
        onResetCamera={onReset}
        onFitNetwork={onFit}
        is2DView={false}
        onToggle2D={onToggle2D}
      />
    );

    expect(screen.getByRole('toolbar', { name: /3D Viewport Controls/i })).toBeInTheDocument();

    const fitBtn = screen.getByRole('button', { name: /Fit to Network/i });
    fireEvent.click(fitBtn);
    expect(onFit).toHaveBeenCalledOnce();

    const toggle2DBtn = screen.getByRole('button', { name: /Switch to Accessible 2D Fallback/i });
    fireEvent.click(toggle2DBtn);
    expect(onToggle2D).toHaveBeenCalledOnce();
  });

  it('verifies 3D Network link exists in the application layout navigation', () => {
    render(
      <AppProvider>
        <BrowserRouter>
          <AppLayout>
            <div>Test</div>
          </AppLayout>
        </BrowserRouter>
      </AppProvider>
    );

    const link3D = screen.getByRole('link', { name: /3D Network/i });
    expect(link3D).toBeInTheDocument();
    expect(link3D.getAttribute('href')).toBe('/3d');
  });
});
