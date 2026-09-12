import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';

vi.mock('@react-three/drei', () => ({
  Html: ({ children }: { children: React.ReactNode }) => <div data-testid="r3f-html">{children}</div>,
  OrbitControls: () => null,
  Grid: () => null
}));

vi.mock('@react-three/fiber', () => ({
  Canvas: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useThree: () => ({
    camera: { position: { set: vi.fn() }, lookAt: vi.fn() },
    gl: { dispose: vi.fn() }
  })
}));

import { ConflictMarker } from '../components/3d/ConflictMarker';
import { MaintenanceBlockVolume } from '../components/3d/MaintenanceBlockVolume';
import { PlanningInspector } from '../components/3d/PlanningInspector';
import { TimelineController } from '../components/3d/TimelineController';
import { Accessible2DNetwork } from '../components/3d/Accessible2DNetwork';
import { mockNetworkGeometry, mockSchedule, mockConflicts } from '../api/mockData';
import { validateNetworkGeometryContract, GeometryContractError } from '../api/geometryValidator';
import type { TrackGeometry, ConflictItem } from '../api/types';

describe('Phase 12 Production Readiness & Safety Boundaries (3D Digital Twin)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('Safety Boundary #6: Immutable Active Possessions', () => {
    const mockTrack: TrackGeometry = {
      block_id: 'B1',
      name: 'Subedarganj to Prayagraj (B1)',
      start_coord: { x: -400, y: 0, z: 0 },
      end_coord: { x: -300, y: 0, z: 2 },
      path_points: [{ x: -400, y: 0, z: 0 }, { x: -300, y: 0, z: 2 }],
      length_km: 10,
      chainage_start: 0,
      chainage_end: 10,
      elevation_profile: [0, 0],
      track_type: 'Mainline',
      electrification: '25kV AC',
      speed_limit_kmh: 110
    };

    it('renders GRANTED possession with visible lock indicator and immutable active tag', () => {
      render(
        <MaintenanceBlockVolume
          track={mockTrack}
          jobId="J_FIXED_1"
          department="Engineering"
          status="GRANTED"
          isLocked={true}
          isSelected={false}
          showLabel={true}
        />
      );

      expect(screen.getByText('🔒 IMMUTABLE ACTIVE')).toBeInTheDocument();
      expect(screen.getByLabelText(/Locked and Immutable/i)).toBeInTheDocument();
    });

    it('renders IN_PROGRESS possession with lock indicator and active status', () => {
      render(
        <MaintenanceBlockVolume
          track={mockTrack}
          jobId="J18"
          department="Engineering"
          status="IN_PROGRESS"
          isLocked={true}
          isSelected={false}
          showLabel={true}
        />
      );

      expect(screen.getByText('🔒 IMMUTABLE ACTIVE')).toBeInTheDocument();
      expect(screen.getByText('J18')).toBeInTheDocument();
    });

    it('displays immutable lock warning card in PlanningInspector for locked possessions', () => {
      const onClose = vi.fn();
      render(
        <PlanningInspector
          entity={{
            type: 'job',
            id: 'J_FIXED_1',
            data: {
              id: 'J_FIXED_1',
              department: 'Engineering',
              block_id: 'B1',
              duration: 4,
              lifecycle_state: 'GRANTED',
              is_locked: true,
              source_system: 'TMS_SURVEY',
              source_record_id: 'TMS-B1-01',
              schema_version: '1.0.0',
              validation_status: 'VALIDATED'
            }
          }}
          onClose={onClose}
          schedule={mockSchedule}
        />
      );

      expect(screen.getByText(/IMMUTABLE ACTIVE/i)).toBeInTheDocument();
      expect(screen.getByText(/IMMUTABLE POSSESSION ENVELOPE/i)).toBeInTheDocument();
      expect(screen.getByText(/track limits and execution windows are strictly locked against UI edits/i)).toBeInTheDocument();
    });
  });

  describe('Critical Conflict & Approval Blocking', () => {
    it('prominently flags critical conflicts with APPROVAL BLOCKED tag', () => {
      const criticalConflict: ConflictItem = {
        id: 'CONF-TEST-CRIT',
        conflict_type: 'train_versus_possession',
        severity: 'CRITICAL',
        block_id: 'B4',
        title: 'Collision Hazard on B4',
        description: 'Scheduled freight path enters active 25kV traction isolated possession.',
        affected_jobs: ['J14'],
        affected_trains: ['T1'],
        time_window: { start: 10, end: 12 },
        suggested_resolution: 'Reschedule freight service via loop line or delay possession start.',
        position: { x: -50, y: 1.8, z: 2 },
        blocks_approval: true
      };

      render(
        <ConflictMarker
          conflict={criticalConflict}
          isSelected={false}
          showLabel={true}
        />
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('CRITICAL')).toBeInTheDocument();
      expect(screen.getByText('🚫 APPROVAL BLOCKED')).toBeInTheDocument();
      expect(screen.getByText('Collision Hazard on B4')).toBeInTheDocument();
    });

    it('shows BLOCKS APPROVAL badge in Conflict Inspector', () => {
      render(
        <PlanningInspector
          entity={{
            type: 'conflict',
            id: 'CONF-FIXED-FB1',
            data: {
              ...mockConflicts[0],
              blocks_approval: true,
              source_system: 'SAFETY_ENGINE',
              validation_status: 'VALIDATED'
            }
          }}
          onClose={vi.fn()}
          schedule={mockSchedule}
        />
      );

      expect(screen.getByText('BLOCKS APPROVAL')).toBeInTheDocument();
      expect(screen.getByText('CRITICAL')).toBeInTheDocument();
      expect(screen.getByText(/Mega Block Lock on B1/i)).toBeInTheDocument();
    });
  });

  describe('Data Provenance, Stale Telemetry & Validation Status', () => {
    it('displays complete entity provenance card in PlanningInspector', () => {
      render(
        <PlanningInspector
          entity={{
            type: 'asset',
            id: 'AST-TRK-B1-04',
            data: {
              name: 'Girder Bridge 42 Pier Bearing',
              asset_type: 'Rail',
              block_id: 'B1',
              chainage_start_km: 4.5,
              chainage_end_km: 6.2,
              health_score: 34,
              defect_severity: 'Critical',
              observed_defect_type: 'Bridge Girder Bedplate Deflection > 8mm',
              last_ultrasonic_test: '2026-08-28',
              days_overdue: 0,
              source_system: 'TRC-09 Ultrasonic Car',
              source_record_id: 'USFD-2026-08-28-091',
              schema_version: '1.0.0',
              coordinate_reference_system: 'LOCAL_CORRIDOR',
              confidence: 0.96,
              data_freshness_seconds: 45,
              validation_status: 'VALIDATED'
            }
          }}
          onClose={vi.fn()}
          schedule={mockSchedule}
        />
      );

      expect(screen.getByText(/Data Lineage & Provenance/i)).toBeInTheDocument();
      expect(screen.getByText('VALIDATED')).toBeInTheDocument();
      expect(screen.getByText(/TRC-09 Ultrasonic Car/i)).toBeInTheDocument();
      expect(screen.getByText(/USFD-2026-08-28-091/i)).toBeInTheDocument();
      expect(screen.getByText(/96%/i)).toBeInTheDocument();
      expect(screen.getByText(/45s ago/i)).toBeInTheDocument();
      expect(screen.getByText(/CRITICAL SAFETY NOTICE/i)).toBeInTheDocument();
    });

    it('renders stale telemetry warning in TimelineController when data age exceeds threshold', () => {
      render(
        <TimelineController
          currentTime={10.0}
          onTimeChange={vi.fn()}
          isPlaying={false}
          onTogglePlay={vi.fn()}
          playbackSpeed={1}
          onSpeedChange={vi.fn()}
          timeWindow="today"
          onWindowChange={vi.fn()}
          maxHorizonHours={24}
          activePossessionsCount={3}
          activeTrainsCount={2}
          isStale={true}
          staleSeconds={345}
        />
      );

      expect(screen.getByRole('status')).toBeInTheDocument();
      expect(screen.getByText(/STALE TELEMETRY: Data age is 345s/i)).toBeInTheDocument();
      expect(screen.getByText('UNVALIDATED FIX')).toBeInTheDocument();
    });

    it('supports 1x, 5x, 15x, and 60x playback speeds in TimelineController', () => {
      const onSpeedChange = vi.fn();
      render(
        <TimelineController
          currentTime={0}
          onTimeChange={vi.fn()}
          isPlaying={false}
          onTogglePlay={vi.fn()}
          playbackSpeed={1}
          onSpeedChange={onSpeedChange}
          timeWindow="today"
          onWindowChange={vi.fn()}
          maxHorizonHours={24}
          activePossessionsCount={0}
          activeTrainsCount={0}
        />
      );

      const speeds = [1, 5, 15, 60];
      for (const spd of speeds) {
        const btn = screen.getByRole('button', { name: `${spd}x` });
        expect(btn).toBeInTheDocument();
        fireEvent.click(btn);
        expect(onSpeedChange).toHaveBeenCalledWith(spd);
      }
    });
  });

  describe('Accessible 2D Schematic Fallback', () => {
    it('renders SVG corridor schematic and accessible table without WebGL', () => {
      const onSelect = vi.fn();
      render(
        <Accessible2DNetwork
          geometry={mockNetworkGeometry}
          schedule={mockSchedule}
          currentTime={4.0}
          trainPositions={[]}
          blockStates={new Map([
            ['B1', { status: 'fixed_block' }],
            ['B4', { status: 'active_maintenance' }]
          ])}
          onSelectEntity={onSelect}
          selectedEntityId="B1"
        />
      );

      expect(screen.getByRole('region', { name: /Accessible 2D Corridor Schematic View/i })).toBeInTheDocument();
      expect(screen.getByText(/Corridor Operational Status Table/i)).toBeInTheDocument();
      expect(screen.getByText(/Subedarganj - Mirzapur Mainline/i)).toBeInTheDocument();

      // Station codes present in SVG
      expect(screen.getByText('SFG')).toBeInTheDocument();
      expect(screen.getByText('MZP')).toBeInTheDocument();

      // Inspect button triggers selection
      const inspectButtons = screen.getAllByRole('button', { name: 'Inspect' });
      expect(inspectButtons.length).toBeGreaterThan(0);
      fireEvent.click(inspectButtons[0]);
      expect(onSelect).toHaveBeenCalled();
    });
  });

  describe('Zero-Invention & Invariant Rejection Verification', () => {
    it('rejects geometry missing CRS contract', () => {
      const invalidGeo = {
        ...mockNetworkGeometry,
        coordinate_system: undefined
      };

      expect(() => {
        validateNetworkGeometryContract(invalidGeo, false);
      }).toThrowError(GeometryContractError);
    });

    it('rejects possession geometry with reversed extent', () => {
      const reversedExtentGeo = {
        ...mockNetworkGeometry,
        possessions: [
          {
            id: 'POSS_REV',
            referenced_block_id: 'B1',
            chainage_start_km: 25.0,
            chainage_end_km: 10.0, // Reversed!
            status: 'REQUESTED'
          }
        ]
      };

      expect(() => {
        validateNetworkGeometryContract(reversedExtentGeo, false);
      }).toThrowError(/invalid extent/i);
    });

    it('rejects GRANTED possession if is_locked is false (Safety Boundary #6)', () => {
      const unlockedGrantedGeo = {
        ...mockNetworkGeometry,
        possessions: [
          {
            id: 'POSS_UNLOCKED',
            referenced_block_id: 'B1',
            chainage_start_km: 10.0,
            chainage_end_km: 20.0,
            status: 'GRANTED',
            is_locked: false // Unsafe! Must be locked.
          }
        ]
      };

      expect(() => {
        validateNetworkGeometryContract(unlockedGrantedGeo, false);
      }).toThrowError(/must be visibly locked/i);
    });
  });

  describe('Synthetic 80km Corridor Benchmarks', () => {
    it('validates 80km corridor geometry in under 50ms', () => {
      const start = performance.now();
      const validated = validateNetworkGeometryContract(mockNetworkGeometry, false);
      const elapsed = performance.now() - start;

      expect(validated).toBeDefined();
      expect(elapsed).toBeLessThan(50);
    });

    it('maintains stability during 100 rapid timeline updates', () => {
      const onTimeChange = vi.fn();
      const { rerender } = render(
        <TimelineController
          currentTime={0}
          onTimeChange={onTimeChange}
          isPlaying={true}
          onTogglePlay={vi.fn()}
          playbackSpeed={1}
          onSpeedChange={vi.fn()}
          timeWindow="today"
          onWindowChange={vi.fn()}
          maxHorizonHours={24}
          activePossessionsCount={2}
          activeTrainsCount={3}
        />
      );

      const start = performance.now();
      for (let t = 0.1; t < 10.0; t += 0.1) {
        rerender(
          <TimelineController
            currentTime={t}
            onTimeChange={onTimeChange}
            isPlaying={true}
            onTogglePlay={vi.fn()}
            playbackSpeed={1}
            onSpeedChange={vi.fn()}
            timeWindow="today"
            onWindowChange={vi.fn()}
            maxHorizonHours={24}
            activePossessionsCount={2}
            activeTrainsCount={3}
          />
        );
      }
      const duration = performance.now() - start;
      expect(duration).toBeLessThan(500); // 100 updates in < 500ms
    });
  });
});
