import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';

import { ThreeDErrorBoundary } from '../components/3d/ThreeDErrorBoundary';
import { PerfInstrumentationPanel } from '../components/3d/PerfInstrumentationPanel';
import { updatePerfMetrics } from '../components/3d/perfStore';
import { generateStressNetworkFixture } from '../fixtures/stressFixture';

// Problematic component to trigger ErrorBoundary
const CrashComponent: React.FC = () => {
  throw new Error("Simulated WebGL Context Lost (WEBGL_CONTEXT_LOST)");
};

describe('WebGL Performance & Resilience Suite', () => {
  it('ThreeDErrorBoundary catches errors and provides honest fallback controls', () => {
    // Suppress React error boundary console output in test
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const onFallback = vi.fn();

    render(
      <ThreeDErrorBoundary onFallbackTo2D={onFallback}>
        <CrashComponent />
      </ThreeDErrorBoundary>
    );

    // Assert honest error alert
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/3D WebGL Initialization Failure/i)).toBeInTheDocument();
    expect(screen.getByText(/Simulated WebGL Context Lost/i)).toBeInTheDocument();

    // Assert retry button
    const retryBtn = screen.getByRole('button', { name: /Retry WebGL Scene/i });
    expect(retryBtn).toBeInTheDocument();

    // Assert fallback button
    const fallbackBtn = screen.getByRole('button', { name: /Switch to 2D Schematic/i });
    expect(fallbackBtn).toBeInTheDocument();
    fireEvent.click(fallbackBtn);
    expect(onFallback).toHaveBeenCalledTimes(1);

    consoleErrorSpy.mockRestore();
  });

  it('ThreeDErrorBoundary renders normal children when healthy', () => {
    render(
      <ThreeDErrorBoundary>
        <div data-testid="healthy-canvas">Healthy 3D Canvas</div>
      </ThreeDErrorBoundary>
    );

    expect(screen.getByTestId('healthy-canvas')).toBeInTheDocument();
  });

  it('generateStressNetworkFixture generates 1,000 blocks and thousands of entities with valid finite coordinates', () => {
    const fixture = generateStressNetworkFixture();
    const { geometry, scenario, assets } = fixture;

    expect(geometry.tracks.length).toBe(1000);
    expect(geometry.blocks.length).toBe(1000);
    expect(geometry.nodes.length).toBe(500);
    expect(scenario.trains.length).toBe(2000);
    expect(assets.length).toBe(5000);
    expect(geometry.conflicts.length).toBe(2000);
    expect(geometry.ohe_masts.length).toBe(10000);

    // Verify coordinates are strictly finite numbers
    for (let i = 0; i < 50; i++) {
      const trk = geometry.tracks[i];
      expect(Number.isFinite(trk.start_coord.x)).toBe(true);
      expect(Number.isFinite(trk.start_coord.y)).toBe(true);
      expect(Number.isFinite(trk.start_coord.z)).toBe(true);
      expect(trk.length_km).toBeGreaterThan(0);
      expect(trk.chainage_end).toBeGreaterThan(trk.chainage_start);
    }
  });

  it('PerfInstrumentationPanel renders live WebGL telemetry metrics', () => {
    updatePerfMetrics({
      fps: 58,
      frameTimeMs: 17.2,
      drawCalls: 45,
      triangles: 12500,
      geometries: 82,
      textures: 14,
      visibleEntities: 350,
      totalEntities: 1000
    });

    render(<PerfInstrumentationPanel isVisible={true} />);

    expect(screen.getByRole('region', { name: /3D WebGL Performance Instrumentation/i })).toBeInTheDocument();
    expect(screen.getByText(/58 FPS/i)).toBeInTheDocument();
    expect(screen.getByText(/17.2 ms/i)).toBeInTheDocument();
    expect(screen.getByText(/45/i)).toBeInTheDocument();
    expect(screen.getByText(/350 \/ 1000/i)).toBeInTheDocument();
  });
});
