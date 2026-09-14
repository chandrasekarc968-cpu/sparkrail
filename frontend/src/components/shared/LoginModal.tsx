import React, { useState } from 'react';
import {
  ShieldCheck,
  Lock,
  User,
  TrainTrack,
  X,
  AlertCircle,
  KeyRound,
  Sparkles
} from 'lucide-react';
import { ApiClient } from '../../api/client';
import type { UserProfile } from '../../api/types';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: UserProfile | null;
  onLoginSuccess: (user: UserProfile) => void;
  onLogoutSuccess: () => void;
}

const PRESET_OFFICERS = [
  {
    name: "R. K. Sharma, IRTS",
    role: "SR_DOM",
    dept: "OPERATING",
    pf: "PF-ECR-90801",
    email: "srdom.ddu@indianrailways.gov.in",
    desc: "Final block sanctions & emergency overrides"
  },
  {
    name: "A. K. Verma, IRSEE",
    role: "CTPC",
    dept: "TRD",
    pf: "PF-ECR-90802",
    email: "ctpc.ddu@indianrailways.gov.in",
    desc: "OHE electrical section isolation approvals"
  },
  {
    name: "Vikas Singh",
    role: "SSE_PWAY",
    dept: "CIVIL",
    pf: "PF-ECR-90803",
    email: "sse.pway.ddu@indianrailways.gov.in",
    desc: "Civil track maintenance block requisitions"
  },
  {
    name: "P. K. Mishra",
    role: "SSE_SIGNAL",
    dept: "SNT",
    pf: "PF-ECR-90804",
    email: "sse.sig.ddu@indianrailways.gov.in",
    desc: "Interlocking & signal disconnection notices"
  },
  {
    name: "R. N. Yadav",
    role: "STATION_MASTER",
    dept: "OPERATING",
    pf: "PF-ECR-90805",
    email: "sm.ddu@indianrailways.gov.in",
    desc: "Line clear consent & Private Number exchange"
  },
  {
    name: "CRIS Admin",
    role: "SYSTEM_ADMIN",
    dept: "ADMIN",
    pf: "PF-CRIS-00001",
    email: "admin.cris@indianrailways.gov.in",
    desc: "Platform configuration & security audit"
  }
];

export function LoginModal({
  isOpen,
  onClose,
  currentUser,
  onLoginSuccess,
  onLogoutSuccess
}: LoginModalProps) {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('RailOps@2026!');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleLogin = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const response = await ApiClient.login(identifier.trim(), password);
      onLoginSuccess(response.user);
      onClose();
    } catch (err: unknown) {
      const errorObj = err as { data?: { detail?: string }; message?: string };
      const msg = errorObj?.data?.detail || errorObj?.message || 'Authentication failed. Verify credentials.';
      setErrorMessage(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setIsLoading(false);
    }
  };

  const handlePresetSelect = (officer: typeof PRESET_OFFICERS[0]) => {
    setIdentifier(officer.pf);
    setPassword('RailOps@2026!');
    setErrorMessage(null);
  };

  const handleLogout = async () => {
    setIsLoading(true);
    try {
      await ApiClient.logout();
      onLogoutSuccess();
      onClose();
    } catch {
      onLogoutSuccess();
      onClose();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/70 backdrop-blur-sm animate-fade-in select-none">
      <div className="relative w-full max-w-xl bg-white rounded-xl shadow-2xl border border-neutral-200 overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 bg-neutral-900 text-white flex items-center justify-between border-b border-neutral-800">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-accent-600/20 border border-accent-500/30 flex items-center justify-center text-accent-400">
              <TrainTrack className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold text-base tracking-tight">CRIS BDMS Secure Portal</span>
                <span className="text-[10px] font-mono bg-accent-500/20 text-accent-300 px-1.5 py-0.5 rounded border border-accent-500/30 font-bold uppercase">
                  IR-RBAC 2.0
                </span>
              </div>
              <p className="text-xs text-neutral-400">Indian Railways Unified Maintenance Command Login</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
            aria-label="Close authentication modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 max-h-[80vh] overflow-y-auto space-y-6">
          {/* Active Session Status */}
          {currentUser ? (
            <div className="p-4 rounded-lg bg-emerald-50 border border-emerald-200">
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold font-mono text-sm shadow-xs">
                    {currentUser.role.slice(0, 2)}
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <p className="font-bold text-neutral-950 text-sm">{currentUser.full_name}</p>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-600/10 text-emerald-700 border border-emerald-300">
                        {currentUser.role}
                      </span>
                    </div>
                    <p className="text-xs text-neutral-600 mt-0.5 font-mono">
                      PF: {currentUser.pf_number} • {currentUser.department} • {currentUser.division_code} ({currentUser.zone_code})
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  disabled={isLoading}
                  className="text-xs font-bold text-red-600 hover:text-red-700 hover:bg-red-50 px-3 py-1.5 rounded border border-red-200 transition-colors"
                >
                  End Shift / Logout
                </button>
              </div>

              {/* Explicit Capabilities */}
              <div className="mt-3 pt-3 border-t border-emerald-200/60">
                <p className="text-[11px] font-bold uppercase tracking-wider text-emerald-900 mb-1.5 flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> Authorized Operational Capabilities
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {currentUser.capabilities.map((cap) => (
                    <span
                      key={cap}
                      className="text-[10px] font-mono font-semibold px-2 py-0.5 bg-white text-neutral-800 rounded border border-emerald-200 shadow-2xs"
                    >
                      {cap}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            /* Login Form */
            <form onSubmit={handleLogin} className="space-y-4">
              {errorMessage && (
                <div className="p-3 rounded-lg bg-red-50 border border-red-200 flex items-start space-x-2.5 text-red-700 text-xs animate-shake">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <div className="flex-1">{errorMessage}</div>
                </div>
              )}

              <div>
                <label className="block text-xs font-bold text-neutral-700 uppercase tracking-wider mb-1.5">
                  Provident Fund (PF) Number or Railway Email
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-400">
                    <User className="w-4 h-4" />
                  </div>
                  <input
                    type="text"
                    required
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    placeholder="e.g. PF-ECR-90801 or srdom.ddu@indianrailways.gov.in"
                    className="w-full pl-9 pr-3 py-2 text-sm border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-neutral-700 uppercase tracking-wider mb-1.5">
                  Secure Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-400">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full pl-9 pr-3 py-2 text-sm border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500 font-mono"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading || !identifier}
                className="w-full py-2.5 px-4 bg-neutral-900 hover:bg-neutral-800 disabled:opacity-50 text-white text-sm font-bold rounded-lg shadow-sm flex items-center justify-center space-x-2 transition-all cursor-pointer"
              >
                <KeyRound className="w-4 h-4 text-accent-400" />
                <span>{isLoading ? 'Authenticating Officer...' : 'Authenticate & Sign On'}</span>
              </button>
            </form>
          )}

          {/* Quick Personnel Switcher for Evaluation */}
          <div className="pt-2 border-t border-neutral-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-neutral-700 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-accent-600" />
                DDU Division Mock Railway Personnel (Click to Fill)
              </span>
              <span className="text-[10px] font-mono text-neutral-400">Pandit Deen Dayal Upadhyaya</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {PRESET_OFFICERS.map((officer) => {
                const isSelected = identifier === officer.pf || identifier === officer.email;
                return (
                  <button
                    key={officer.pf}
                    type="button"
                    onClick={() => handlePresetSelect(officer)}
                    className={`p-2.5 text-left rounded-lg border transition-all text-xs flex flex-col justify-between ${
                      isSelected
                        ? 'border-accent-500 bg-accent-50/50 shadow-2xs ring-1 ring-accent-500'
                        : 'border-neutral-200 bg-neutral-50/50 hover:bg-neutral-100/80 hover:border-neutral-300'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-bold text-neutral-900">{officer.name}</span>
                      <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-neutral-200 text-neutral-800">
                        {officer.role}
                      </span>
                    </div>
                    <p className="text-[11px] text-neutral-500 font-mono mb-1">
                      {officer.pf} • {officer.dept}
                    </p>
                    <p className="text-[10px] text-neutral-600 line-clamp-1 italic">
                      {officer.desc}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Modal Footer Security Notice */}
        <div className="px-6 py-3 bg-neutral-50 border-t border-neutral-200 flex items-center justify-between text-[11px] text-neutral-500">
          <span className="flex items-center gap-1.5 font-medium">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> SHA-256 Tamper-Evident Audit Logging Active
          </span>
          <span className="font-mono text-[10px]">ECR/DDU BDMS v1.0</span>
        </div>
      </div>
    </div>
  );
}
