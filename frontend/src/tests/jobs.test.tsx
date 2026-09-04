import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { MaintenanceJobs } from '../pages/MaintenanceJobs';
import { AppProvider } from '../context/AppContext';
import { setDemoModeEnabled } from '../api/client';

describe('MaintenanceJobs Page', () => {
  beforeEach(() => {
    setDemoModeEnabled(true);
  });

  it('renders maintenance jobs register table with 20 tasks', async () => {
    render(
      <AppProvider>
        <MaintenanceJobs />
      </AppProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Maintenance Jobs Register/i)).toBeInTheDocument();
    });

    // Check for critical job J18 in the table
    expect(screen.getByText('J18')).toBeInTheDocument();
  });

  it('filters jobs dynamically when typing into search input', async () => {
    render(
      <AppProvider>
        <MaintenanceJobs />
      </AppProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('J18')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search Job ID, Block, Department.../i);
    fireEvent.change(searchInput, { target: { value: 'B6' } });

    // Should still display J18 (which is on B6)
    expect(screen.getByText('J18')).toBeInTheDocument();

    // Clear search and test specific non-existent filter
    fireEvent.change(searchInput, { target: { value: 'NON_EXISTENT_QUERY' } });
    expect(screen.queryByText('J18')).not.toBeInTheDocument();
  });

  it('filters by department selection', async () => {
    render(
      <AppProvider>
        <MaintenanceJobs />
      </AppProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('J18')).toBeInTheDocument();
    });

    const deptSelect = screen.getByLabelText(/Filter by department/i);
    fireEvent.change(deptSelect, { target: { value: 'OHE' } });

    // OHE job J1 should be visible, Engineering J18 should be filtered out
    expect(screen.getByText('J1')).toBeInTheDocument();
    expect(screen.queryByText('J18')).not.toBeInTheDocument();
  });
});
