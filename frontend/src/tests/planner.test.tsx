import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { BlockPlanner } from '../pages/BlockPlanner';
import { AppProvider } from '../context/AppContext';
import { setDemoModeEnabled } from '../api/client';

describe('BlockPlanner Page', () => {
  beforeEach(() => {
    setDemoModeEnabled(true);
  });

  it('renders block sections B1 through B8 on timeline', async () => {
    render(
      <AppProvider>
        <BlockPlanner />
      </AppProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Block Planner')).toBeInTheDocument();
    });

    // Check for section headers
    expect(screen.getAllByText('B1').length).toBeGreaterThan(0);
    expect(screen.getAllByText('B4').length).toBeGreaterThan(0);
    expect(screen.getAllByText('B8').length).toBeGreaterThan(0);
  });

  it('displays Frozen Week 1 treatment by default', async () => {
    render(
      <AppProvider>
        <BlockPlanner />
      </AppProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Week 1: Frozen Horizon/i)).toBeInTheDocument();
    });
  });

  it('renders task inspector with component breakdown bars for selected job', async () => {
    render(
      <AppProvider>
        <BlockPlanner />
      </AppProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Task Inspector/i)).toBeInTheDocument();
    });

    // Verify TCI components are displayed
    expect(screen.getByText(/Safety Risk \(40%\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Traffic \/ Delay Impact \(30%\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Degradation Velocity \(20%\)/i)).toBeInTheDocument();
  });
});
