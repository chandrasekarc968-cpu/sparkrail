import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Box,
  CalendarDays,
  Wrench,
  Activity,
  ShieldAlert,
  BarChart3,
  Sliders,
  TrainTrack,
  X,
  ShieldCheck
} from 'lucide-react';
import { useAppContext } from '../../context/useAppContext';
import { GlobalHeader } from './GlobalHeader';

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const { isDemoMode } = useAppContext();
  const location = useLocation();
  const is3DPage = location.pathname === '/3d';
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);

  const navItems = [
    { name: 'Overview', to: '/overview', icon: LayoutDashboard },
    { name: '3D Network', to: '/3d', icon: Box },
    { name: 'Block Planner', to: '/planner', icon: CalendarDays },
    { name: 'Maintenance Jobs', to: '/jobs', icon: Wrench },
    { name: 'Live Operations', to: '/live', icon: Activity },
    { name: 'Assets', to: '/assets', icon: ShieldAlert },
    { name: 'Reports', to: '/reports', icon: BarChart3 },
    { name: 'Settings', to: '/settings', icon: Sliders },
  ];

  return (
    <div className="flex h-screen bg-neutral-50 text-neutral-900 overflow-hidden font-sans select-none">
      {/* Mobile Drawer Backdrop */}
      {isMobileNavOpen && (
        <div
          className="fixed inset-0 z-40 bg-neutral-900/50 backdrop-blur-xs lg:hidden"
          onClick={() => setIsMobileNavOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar (Desktop Permanent + Mobile Slide-out) */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-neutral-200 flex flex-col transition-transform duration-200 ease-in-out lg:static lg:translate-x-0 ${
          isMobileNavOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand Mark */}
        <div className="h-16 px-5 border-b border-neutral-200 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded bg-neutral-900 flex items-center justify-center text-accent-400 shadow-xs">
              <TrainTrack className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="font-extrabold text-base tracking-tight text-neutral-950">SparkRail</span>
                <span className="text-[9px] font-bold uppercase tracking-widest text-accent-600 bg-accent-500/10 px-1 py-0.5 rounded border border-accent-600/20">
                  AI
                </span>
              </div>
              <p className="text-[10px] text-neutral-500 font-medium tracking-tight">Block Planning System</p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setIsMobileNavOpen(false)}
            className="lg:hidden p-1.5 rounded-md text-neutral-500 hover:text-neutral-900 min-h-[44px] min-w-[44px] flex items-center justify-center"
            aria-label="Close navigation"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1" aria-label="Main Navigation">
          {navItems.map((item) => (
            <NavLink
              key={item.name}
              to={item.to}
              onClick={() => setIsMobileNavOpen(false)}
              className={({ isActive }) =>
                `flex items-center px-3.5 py-2.5 rounded text-sm font-semibold transition-colors min-h-[44px] ${
                  isActive
                    ? 'bg-neutral-100 text-neutral-950 border-l-4 border-accent-600 shadow-xs'
                    : 'text-neutral-600 hover:bg-neutral-50 hover:text-neutral-950'
                }`
              }
            >
              <item.icon className="w-4 h-4 mr-3 shrink-0" aria-hidden="true" />
              <span>{item.name}</span>
            </NavLink>
          ))}
        </nav>

        {/* Sidebar Footer: System Safety Status */}
        <div className="p-3.5 border-t border-neutral-200 bg-neutral-50/60 shrink-0">
          <div className="flex items-center justify-between text-xs text-neutral-600 mb-1">
            <span className="flex items-center gap-1.5 font-semibold text-neutral-800">
              <ShieldCheck className="w-4 h-4 text-op-green" />
              Safety Verification
            </span>
            <span className="text-[10px] text-op-green font-bold uppercase">Active</span>
          </div>
          <p className="text-[11px] text-neutral-500 leading-snug">
            {isDemoMode ? "Deterministic Simulation Mode" : "Connected to SCIP MILP Solver"}
          </p>
          <div className="mt-2 text-[10px] text-neutral-400 font-mono">
            IR-RDSO Spec 2026.04
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <GlobalHeader onToggleMobileNav={() => setIsMobileNavOpen(true)} />
        <main className={is3DPage ? "flex-1 overflow-hidden focus:outline-none" : "flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 focus:outline-none"}>
          {children}
        </main>
      </div>
    </div>
  );
}
