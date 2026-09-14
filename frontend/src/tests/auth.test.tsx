import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LoginModal } from '../components/shared/LoginModal';
import { ApiClient } from '../api/client';
import type { UserProfile } from '../api/types';

describe('Indian Railways BDMS Authentication Modal & RBAC UI', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockUser: UserProfile = {
    id: 'usr-ddu-001',
    pf_number: 'PF-ECR-90801',
    email: 'srdom.ddu@indianrailways.gov.in',
    full_name: 'R. K. Sharma, IRTS',
    department: 'OPERATING',
    role: 'SR_DOM',
    division_code: 'ECR-DDU',
    zone_code: 'ECR',
    is_active: true,
    capabilities: ['SANCTION_BLOCK', 'EMERGENCY_OVERRIDE', 'VIEW_CORRIDOR']
  };

  it('renders login form and DDU preset officers when unauthenticated', () => {
    render(
      <LoginModal
        isOpen={true}
        onClose={() => {}}
        currentUser={null}
        onLoginSuccess={() => {}}
        onLogoutSuccess={() => {}}
      />
    );

    expect(screen.getByText('CRIS BDMS Secure Portal')).toBeInTheDocument();
    expect(screen.getByText('IR-RBAC 2.0')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/PF-ECR-90801/)).toBeInTheDocument();
    expect(screen.getByText('Authenticate & Sign On')).toBeInTheDocument();

    // Preset officers should be rendered
    expect(screen.getByText('R. K. Sharma, IRTS')).toBeInTheDocument();
    expect(screen.getByText('A. K. Verma, IRSEE')).toBeInTheDocument();
    expect(screen.getByText('Vikas Singh')).toBeInTheDocument();
  });

  it('clicking a preset officer auto-populates credentials', () => {
    render(
      <LoginModal
        isOpen={true}
        onClose={() => {}}
        currentUser={null}
        onLoginSuccess={() => {}}
        onLogoutSuccess={() => {}}
      />
    );

    const ctpcBtn = screen.getByText('A. K. Verma, IRSEE');
    fireEvent.click(ctpcBtn);

    const identifierInput = screen.getByPlaceholderText(/PF-ECR-90801/) as HTMLInputElement;
    expect(identifierInput.value).toBe('PF-ECR-90802');
  });

  it('submits login request and calls onLoginSuccess', async () => {
    const loginSpy = vi.spyOn(ApiClient, 'login').mockResolvedValueOnce({
      access_token: 'mock-jwt-token',
      refresh_token: 'mock-refresh-token',
      token_type: 'bearer',
      expires_in: 900,
      user: mockUser
    });

    const handleLoginSuccess = vi.fn();
    const handleClose = vi.fn();

    render(
      <LoginModal
        isOpen={true}
        onClose={handleClose}
        currentUser={null}
        onLoginSuccess={handleLoginSuccess}
        onLogoutSuccess={() => {}}
      />
    );

    const identifierInput = screen.getByPlaceholderText(/PF-ECR-90801/);
    fireEvent.change(identifierInput, { target: { value: 'PF-ECR-90801' } });

    const submitBtn = screen.getByText('Authenticate & Sign On');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(loginSpy).toHaveBeenCalledWith('PF-ECR-90801', 'RailOps@2026!');
      expect(handleLoginSuccess).toHaveBeenCalledWith(mockUser);
      expect(handleClose).toHaveBeenCalled();
    });
  });

  it('displays active railway session and explicit operational capabilities when logged in', () => {
    render(
      <LoginModal
        isOpen={true}
        onClose={() => {}}
        currentUser={mockUser}
        onLoginSuccess={() => {}}
        onLogoutSuccess={() => {}}
      />
    );

    expect(screen.getAllByText('R. K. Sharma, IRTS').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('SR_DOM').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/PF: PF-ECR-90801/)).toBeInTheDocument();
    expect(screen.getByText('Authorized Operational Capabilities')).toBeInTheDocument();
    expect(screen.getByText('SANCTION_BLOCK')).toBeInTheDocument();
    expect(screen.getByText('EMERGENCY_OVERRIDE')).toBeInTheDocument();
    expect(screen.getByText('End Shift / Logout')).toBeInTheDocument();
  });
});
