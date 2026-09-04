import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TCIBadge } from '../components/shared/TCIBadge';

describe('TCIBadge', () => {
  it('renders critical score with accessible label and red variant', () => {
    render(<TCIBadge score={89.9} />);
    expect(screen.getByText('89.9')).toBeInTheDocument();
    expect(screen.getByText('CRITICAL')).toBeInTheDocument();
    const badge = screen.getByLabelText(/Task Criticality Index 89.9, level CRITICAL/i);
    expect(badge).toBeInTheDocument();
  });

  it('renders high score for values between 60 and 79.9', () => {
    render(<TCIBadge score={65.4} />);
    expect(screen.getByText('65.4')).toBeInTheDocument();
    expect(screen.getByText('HIGH')).toBeInTheDocument();
  });

  it('renders medium score for values between 40 and 59.9', () => {
    render(<TCIBadge score={48.5} />);
    expect(screen.getByText('48.5')).toBeInTheDocument();
    expect(screen.getByText('MEDIUM')).toBeInTheDocument();
  });

  it('renders low score for values below 40', () => {
    render(<TCIBadge score={31.2} />);
    expect(screen.getByText('31.2')).toBeInTheDocument();
    expect(screen.getByText('LOW')).toBeInTheDocument();
  });
});
