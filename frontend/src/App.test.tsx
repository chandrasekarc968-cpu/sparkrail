import { render, screen } from '@testing-library/react';
import App from './App';
import { describe, it, expect } from 'vitest';

describe('App', () => {
  it('renders SparkRail brand name in sidebar', () => {
    render(<App />);
    expect(screen.getByText('SparkRail')).toBeInTheDocument();
  });
});
