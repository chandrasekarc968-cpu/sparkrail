import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { AppProvider } from '../context/AppContext';
import { AppLayout } from '../components/layout/AppLayout';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorBanner } from '../components/ui/ErrorBanner';

describe('Accessibility & Core UI Components', () => {
  it('renders accessible navigation landmark with proper ARIA attributes', () => {
    render(
      <AppProvider>
        <BrowserRouter>
          <AppLayout>
            <div>Test Content</div>
          </AppLayout>
        </BrowserRouter>
      </AppProvider>
    );

    const nav = screen.getByRole('navigation', { name: /Main Navigation/i });
    expect(nav).toBeInTheDocument();

    // Verify all 7 primary navigation links exist
    expect(screen.getByRole('link', { name: /Overview/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Block Planner/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Maintenance Jobs/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Live Operations/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Assets/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Reports/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Settings/i })).toBeInTheDocument();
  });

  it('renders ErrorBanner with alert role for screen readers', () => {
    render(
      <ErrorBanner
        title="Critical Connection Failure"
        message="Unable to reach railway database."
        onRetry={() => {}}
      />
    );

    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(screen.getByText('Critical Connection Failure')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry Request/i })).toBeInTheDocument();
  });

  it('renders EmptyState with explanatory guidance and actionable button', () => {
    render(
      <EmptyState
        title="No Blocks Scheduled"
        description="Please run optimization solver to populate blocks."
        actionLabel="Run Optimization"
        onAction={() => {}}
      />
    );

    expect(screen.getByText('No Blocks Scheduled')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Run Optimization/i })).toBeInTheDocument();
  });
});
