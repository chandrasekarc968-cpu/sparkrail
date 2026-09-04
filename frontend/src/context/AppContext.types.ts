import type { DivisionInfo } from '../api/types';

export type BackendConnectionStatus = "connected" | "demo" | "offline";

export interface AppContextType {
  isDemoMode: boolean;
  setDemoMode: (val: boolean) => void;
  division: string;
  setDivision: (code: string) => void;
  divisions: DivisionInfo[];
  planningHorizon: string;
  setPlanningHorizon: (horizon: string) => void;
  connectionStatus: BackendConnectionStatus;
  lastRefresh: string;
  refreshData: () => void;
  checkConnection: () => Promise<void>;
  activeNotificationCount: number;
  isOptimizationRunning: boolean;
  setIsOptimizationRunning: (val: boolean) => void;
}
