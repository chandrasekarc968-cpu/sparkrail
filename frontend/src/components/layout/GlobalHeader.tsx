import { useState } from 'react';
import {
  Bell,
  RefreshCw,
  Server,
  Wifi,
  WifiOff,
  Menu,
  CheckCircle2,
  AlertTriangle,
  ChevronDown
} from 'lucide-react';
import { useAppContext } from '../../context/useAppContext';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { mockEvents } from '../../api/mockData';

interface GlobalHeaderProps {
  onToggleMobileNav: () => void;
}

export function GlobalHeader({ onToggleMobileNav }: GlobalHeaderProps) {
  const {
    isDemoMode,
    division,
    setDivision,
    divisions,
    planningHorizon,
    connectionStatus,
    lastRefresh,
    refreshData,
  } = useAppContext();

  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    refreshData();
    setTimeout(() => setIsRefreshing(false), 400);
  };

  const formatTimestamp = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    } catch {
      return "--:--:--";
    }
  };

  const unreadAlerts = mockEvents.filter((e) => e.level === "critical" || e.level === "warning");

  return (
    <header className="h-16 border-b border-neutral-200 bg-white px-4 sm:px-6 flex items-center justify-between z-30 shrink-0 select-none">
      {/* Left: Mobile Toggle & Division / Horizon */}
      <div className="flex items-center space-x-3 sm:space-x-4 min-w-0">
        <button
          type="button"
          onClick={onToggleMobileNav}
          className="lg:hidden p-2 rounded-md text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100 min-h-[44px] min-w-[44px] flex items-center justify-center"
          aria-label="Open navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Division Selector */}
        <div className="flex items-center space-x-2">
          <label htmlFor="division-select" className="text-xs font-semibold text-neutral-500 uppercase tracking-wider hidden sm:inline">
            Division
          </label>
          <div className="relative">
            <select
              id="division-select"
              value={division}
              onChange={(e) => setDivision(e.target.value)}
              className="appearance-none bg-neutral-50 border border-neutral-300 rounded text-xs font-bold text-neutral-900 py-1.5 pl-2.5 pr-7 focus:outline-none focus:ring-2 focus:ring-accent-500 cursor-pointer min-h-[36px]"
              aria-label="Select railway division"
            >
              {divisions.map((d) => (
                <option key={d.code} value={d.code}>
                  {d.name} ({d.code})
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-neutral-500 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>

        {/* Planning Horizon Tag */}
        <div className="hidden md:flex items-center space-x-1.5 border-l border-neutral-200 pl-3">
          <span className="text-xs text-neutral-500 font-medium">Horizon:</span>
          <Badge variant="neutral" size="sm" className="font-mono text-neutral-800 bg-neutral-100 border-neutral-300">
            {planningHorizon}
          </Badge>
        </div>
      </div>

      {/* Right: Connection Status, Refresh, Notifications, User Profile */}
      <div className="flex items-center space-x-2 sm:space-x-4">
        {/* Backend Connection Indicator */}
        <div className="flex items-center">
          {connectionStatus === "connected" && (
            <div
              className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded bg-op-green-light/40 border border-op-green/30 text-op-green-dark text-xs font-semibold"
              title="Connected to SparkRail FastAPI Backend"
            >
              <Wifi className="w-3.5 h-3.5 text-op-green-dark" />
              <span className="hidden sm:inline">Connected</span>
            </div>
          )}
          {connectionStatus === "demo" && (
            <div
              className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded bg-op-amber-light/40 border border-op-amber/40 text-op-amber-dark text-xs font-semibold"
              title="Running on deterministic local railway simulation data"
            >
              <Server className="w-3.5 h-3.5 text-op-amber-dark" />
              <span>Demo mode</span>
            </div>
          )}
          {connectionStatus === "offline" && (
            <div
              className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded bg-op-red-light/40 border border-op-red/30 text-op-red-dark text-xs font-semibold"
              title="Backend unreachable. Please verify API server."
            >
              <WifiOff className="w-3.5 h-3.5 text-op-red-dark" />
              <span className="hidden sm:inline">Offline</span>
            </div>
          )}
        </div>

        {/* Last Refresh & Manual Sync */}
        <div className="hidden lg:flex items-center space-x-1.5 text-xs text-neutral-500 font-mono">
          <span>Synced:</span>
          <span className="font-bold text-neutral-800 tabular-nums">
            {formatTimestamp(lastRefresh)}
          </span>
        </div>

        <Button
          variant="ghost"
          size="icon"
          onClick={handleManualRefresh}
          isLoading={isRefreshing}
          aria-label="Refresh operational data"
          className="text-neutral-600 hover:text-neutral-900"
          title="Refresh operational data"
        >
          <RefreshCw className="w-4 h-4" />
        </Button>

        {/* Notifications Control */}
        <div className="relative">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              setShowNotifications(!showNotifications);
              setShowUserMenu(false);
            }}
            aria-label="Open operational alerts"
            aria-expanded={showNotifications}
            className="text-neutral-600 hover:text-neutral-900 relative"
          >
            <Bell className="w-4 h-4" />
            {unreadAlerts.length > 0 && (
              <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-op-red animate-pulse" />
            )}
          </Button>

          {/* Notifications Dropdown Panel */}
          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-white border border-neutral-200 rounded-md shadow-lg z-50 overflow-hidden animate-in fade-in-50 duration-100">
              <div className="px-4 py-3 border-b border-neutral-100 bg-neutral-50 flex items-center justify-between">
                <span className="text-xs font-bold text-neutral-900 uppercase tracking-wider">
                  Operational Alerts
                </span>
                <span className="text-[11px] font-semibold text-neutral-500 tabular-nums">
                  {unreadAlerts.length} Active
                </span>
              </div>
              <div className="max-h-72 overflow-y-auto divide-y divide-neutral-100">
                {mockEvents.slice(0, 4).map((evt) => (
                  <div key={evt.id} className="p-3 text-xs hover:bg-neutral-50 transition-colors">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-neutral-800 flex items-center gap-1.5">
                        {evt.level === "critical" && (
                          <AlertTriangle className="w-3.5 h-3.5 text-op-red shrink-0" />
                        )}
                        {evt.level === "warning" && (
                          <AlertTriangle className="w-3.5 h-3.5 text-op-amber shrink-0" />
                        )}
                        {evt.level === "info" && (
                          <CheckCircle2 className="w-3.5 h-3.5 text-op-green shrink-0" />
                        )}
                        {evt.source || "System"}
                      </span>
                      <span className="text-[10px] text-neutral-400 font-mono">
                        {new Date(evt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <p className="text-neutral-600 leading-relaxed">{evt.message}</p>
                  </div>
                ))}
              </div>
              <div className="p-2 border-t border-neutral-100 bg-neutral-50 text-center">
                <button
                  type="button"
                  onClick={() => setShowNotifications(false)}
                  className="text-xs text-accent-600 hover:text-accent-700 font-medium py-1"
                >
                  Dismiss Alerts
                </button>
              </div>
            </div>
          )}
        </div>

        {/* User Profile Menu */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setShowUserMenu(!showUserMenu);
              setShowNotifications(false);
            }}
            className="flex items-center space-x-2 pl-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 rounded p-1 min-h-[44px]"
            aria-label="User profile menu"
            aria-expanded={showUserMenu}
          >
            <div className="w-8 h-8 rounded bg-neutral-800 text-neutral-100 flex items-center justify-center font-mono text-xs font-bold shadow-xs">
              IR
            </div>
            <div className="hidden xl:flex flex-col text-left">
              <span className="text-xs font-bold text-neutral-900 leading-tight">IR-CTR-8842</span>
              <span className="text-[10px] text-neutral-500 leading-tight">Chief Controller</span>
            </div>
          </button>

          {/* User Menu Dropdown */}
          {showUserMenu && (
            <div className="absolute right-0 mt-2 w-56 bg-white border border-neutral-200 rounded-md shadow-lg z-50 p-2 text-xs">
              <div className="px-3 py-2 border-b border-neutral-100 mb-1">
                <p className="font-bold text-neutral-900">Chief Block Controller</p>
                <p className="text-[11px] text-neutral-500 font-mono">Prayagraj Control Room</p>
                <div className="mt-1.5 flex items-center gap-1 text-[10px] text-neutral-500">
                  <span>Duty Mode:</span>
                  <Badge variant={isDemoMode ? "warning" : "success"} size="sm">
                    {isDemoMode ? "Simulation" : "Live Operations"}
                  </Badge>
                </div>
              </div>
              <div className="px-3 py-1.5 text-neutral-600 hover:bg-neutral-100 rounded cursor-pointer">
                COA Telemetry Settings
              </div>
              <div className="px-3 py-1.5 text-neutral-600 hover:bg-neutral-100 rounded cursor-pointer">
                Safety Handover Log
              </div>
              <div className="border-t border-neutral-100 mt-1 pt-1">
                <div
                  onClick={() => setShowUserMenu(false)}
                  className="px-3 py-1.5 text-op-red hover:bg-op-red/10 rounded cursor-pointer font-semibold"
                >
                  End Shift / Lock Station
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
