import { useState, useEffect, useCallback, type ReactNode } from 'react';
import type { BackendConnectionStatus } from './AppContext.types';
import { AppContext } from './contextInstance';
import { mockDivisions } from '../api/mockData';
import { ApiClient, isDemoModeEnabled, setDemoModeEnabled } from '../api/client';

export function AppProvider({ children }: { children: ReactNode }) {
  const [isDemoMode, setIsDemoModeState] = useState<boolean>(isDemoModeEnabled());
  const [division, setDivision] = useState<string>("PRYJ");
  const [planningHorizon, setPlanningHorizon] = useState<string>("RBP 2026, Week 37");
  const [lastRefresh, setLastRefresh] = useState<string>(new Date().toISOString());
  const [connectionStatus, setConnectionStatus] = useState<BackendConnectionStatus>(
    isDemoModeEnabled() ? "demo" : "offline"
  );
  const [isOptimizationRunning, setIsOptimizationRunning] = useState<boolean>(false);
  const [activeNotificationCount] = useState<number>(3);

  const checkConnection = useCallback(async () => {
    if (isDemoMode) {
      setConnectionStatus("demo");
      return;
    }
    try {
      const health = await ApiClient.getHealth();
      if (health.status === "ok") {
        setConnectionStatus("connected");
      } else {
        setConnectionStatus("offline");
      }
    } catch {
      setConnectionStatus("offline");
    }
  }, [isDemoMode]);

  const setDemoMode = (val: boolean) => {
    setIsDemoModeState(val);
    setDemoModeEnabled(val);
    setConnectionStatus(val ? "demo" : "offline");
    setLastRefresh(new Date().toISOString());
  };

  const refreshData = useCallback(() => {
    setLastRefresh(new Date().toISOString());
    void checkConnection();
  }, [checkConnection]);

  useEffect(() => {
    void checkConnection();
  }, [checkConnection]);

  return (
    <AppContext.Provider
      value={{
        isDemoMode,
        setDemoMode,
        division,
        setDivision,
        divisions: mockDivisions,
        planningHorizon,
        setPlanningHorizon,
        connectionStatus,
        lastRefresh,
        refreshData,
        checkConnection,
        activeNotificationCount,
        isOptimizationRunning,
        setIsOptimizationRunning,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}
