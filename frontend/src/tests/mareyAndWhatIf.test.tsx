import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MareyChart } from '../components/charts/MareyChart';
import { WhatIfSimulatorModal } from '../components/shared/WhatIfSimulatorModal';
import { setDemoModeEnabled } from '../api/client';
import type { Scenario, OptimizedSchedule } from '../api/types';

const mockScenario: Scenario = {
  id: 'test-scenario',
  name: 'Prayagraj Corridor Test',
  blocks: [
    {
      id: 'B1',
      track_id: 'UP_MAIN',
      start_station: 'SFG',
      end_station: 'PRYJ',
      chainage_start: 0.0,
      chainage_end: 10.0,
      length_km: 10.0,
      speed_limit_kmh: 130,
      description: 'Subedarganj to Prayagraj',
    },
    {
      id: 'B8',
      track_id: 'UP_MAIN',
      start_station: 'JIA',
      end_station: 'MZP',
      chainage_start: 70.0,
      chainage_end: 80.0,
      length_km: 10.0,
      speed_limit_kmh: 130,
      description: 'Jigna to Mirzapur',
    },
  ],
  trains: [
    {
      id: '12301',
      name: 'Vande Bharat Express',
      category: 'premium',
      priority: 1,
      scheduled_start: 6.0,
      scheduled_end: 7.5,
      route: ['B1', 'B8'],
      origin: 'SFG',
      destination: 'MZP',
      gross_tonnage_tonnes: 450,
      is_loaded_freight: false,
      train_type: 'vande_bharat',
      crew_duty_remaining_hours: 6.5,
    },
    {
      id: 'BOXN_COAL_1',
      name: 'Loaded Coal Rake BCN/E',
      category: 'freight',
      priority: 3,
      scheduled_start: 8.0,
      scheduled_end: 10.5,
      route: ['B1', 'B8'],
      origin: 'SFG',
      destination: 'MZP',
      gross_tonnage_tonnes: 5200,
      is_loaded_freight: true,
      train_type: 'freight_heavy_coal',
      crew_duty_remaining_hours: 3.0,
    },
  ],
  jobs: [
    {
      id: 'J1',
      department: 'Engineering',
      block_id: 'B1',
      duration: 3,
      preferred_start_window: [8, 14],
      safety_clearance_required: 'OHE_ISOLATION',
      urgency_score: 8,
      required_resources: { bcm_machine: 1 },
      tci_inputs: {
        safety_severity: 8,
        traffic_impact: 6,
        degradation_indicator: 7,
        overdue_days: 10,
      },
    },
  ],
  resources: [],
  fixed_blocks: [],
};

const mockSchedule: OptimizedSchedule = {
  scenario_id: 'test-scenario',
  solver: 'SCIP',
  status: 'Optimal',
  objective_value: 120.5,
  scheduled_jobs: [
    {
      job_id: 'J1',
      block_id: 'B1',
      start_time: 9.0,
      end_time: 12.0,
      track_id: 'UP_MAIN',
      department: 'Engineering',
      tci: 74.2,
      is_shadow_block: false,
    },
  ],
  unscheduled_jobs: [],
  train_delays: {},
  total_closure_time: 3.0,
  kpis: {
    total_scheduled_blocks: 1,
    pdd_score: 91.5,
    passenger_train_punctuality: 98.2,
    freight_throughput_km: 450,
    shadow_block_savings_hours: 1.5,
  },
};

describe('Interactive Digital Marey Chart (Time-Distance)', () => {
  it('renders physical station chainage labels on the Y-axis', () => {
    render(
      <MareyChart
        scenario={mockScenario}
        schedule={mockSchedule}
      />
    );

    // Station codes and names
    expect(screen.getAllByText(/Subedarganj/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Mirzapur/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/SFG/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/MZP/i).length).toBeGreaterThan(0);
  });

  it('renders operational legend categories for train lines and possession blocks', () => {
    render(
      <MareyChart
        scenario={mockScenario}
        schedule={mockSchedule}
      />
    );

    expect(screen.getByText(/Vande Bharat \/ Rajdhani/i)).toBeInTheDocument();
    expect(screen.getByText(/Loaded Coal\/Mineral \(5000t\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Civil Block/i)).toBeInTheDocument();
    expect(screen.getByText(/25kV OHE Block/i)).toBeInTheDocument();
  });

  it('supports Hindi language bilingual toggle', () => {
    render(
      <MareyChart
        scenario={mockScenario}
        schedule={mockSchedule}
        lang="hi"
      />
    );

    expect(screen.getAllByText(/सूबेदारगंज/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/मिर्जापुर/i).length).toBeGreaterThan(0);
  });
});

describe('What-If Scenario Simulator Modal', () => {
  beforeEach(() => {
    setDemoModeEnabled(true);
  });

  it('renders scenario injection parameters and runs hypothetical simulation', async () => {
    const handleClose = vi.fn();
    const handleCommit = vi.fn();

    render(
      <WhatIfSimulatorModal
        isOpen={true}
        onClose={handleClose}
        scenario={mockScenario}
        onScenarioCommitted={handleCommit}
      />
    );

    expect(screen.getByText(/"What-If" Sandbox & Scenario Simulator/i)).toBeInTheDocument();
    expect(screen.getByText(/Sr\. DOM Staging Mode/i)).toBeInTheDocument();

    // Verify disruption types are selectable
    expect(screen.getByText(/Extend Machine Duration/i)).toBeInTheDocument();
    expect(screen.getByText(/Loco Failure/i)).toBeInTheDocument();
    expect(screen.getByText(/Speed Restriction/i)).toBeInTheDocument();

    // Click Run What-If Simulation
    const runBtn = screen.getByText(/Run What-If Simulation/i);
    fireEvent.click(runBtn);

    // Await simulation delta report
    await waitFor(() => {
      expect(screen.getByText(/Comparative Delta Report/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Total Delay Delta/i)).toBeInTheDocument();
    expect(screen.getByText(/Regulated Freight/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Kinetic Energy Loss/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Chief Controller Briefing/i)).toBeInTheDocument();
  });

  it('supports Hindi XAI translation in delta report', async () => {
    render(
      <WhatIfSimulatorModal
        isOpen={true}
        onClose={vi.fn()}
        scenario={mockScenario}
      />
    );

    const runBtn = screen.getByText(/Run What-If Simulation/i);
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByText(/Comparative Delta Report/i)).toBeInTheDocument();
    });

    // Toggle Hindi
    const hiBtn = screen.getByText('हिंदी');
    fireEvent.click(hiBtn);

    // Verify Hindi headers appear
    expect(screen.getByText(/तुलनात्मक डेल्टा रिपोर्ट/i)).toBeInTheDocument();
  });
});
