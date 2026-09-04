import { useState, useEffect, useCallback, useRef } from 'react';
import { ApiClient } from '../api/client';
import type { OptimizedSchedule, KPIReport } from '../api/types';

export type ScheduleViewMode = 'optimized' | 'baseline' | 'conflicts_only' | 'shadow_only';

export function useScheduleData() {
  const [schedule, setSchedule] = useState<OptimizedSchedule | null>(null);
  const [kpis, setKpis] = useState<KPIReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [optimizing, setOptimizing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ScheduleViewMode>('optimized');
  const [freezeWeek1, setFreezeWeek1] = useState<boolean>(false);
  const [solverProgress, setSolverProgress] = useState<string>('');
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchSchedule = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);
    try {
      const sched = await ApiClient.getSchedule('latest', controller.signal);
      setSchedule(sched);
      if (sched.kpi_metrics) {
        setKpis(sched.kpi_metrics);
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      console.warn("No active schedule found, optimizing initial baseline:", err);
      // Fallback: trigger optimize to initialize schedule
      try {
        const newSched = await ApiClient.optimizeSchedule(controller.signal);
        setSchedule(newSched);
        if (newSched.kpi_metrics) {
          setKpis(newSched.kpi_metrics);
        }
      } catch (optErr: unknown) {
        if (optErr instanceof DOMException && optErr.name === 'AbortError') {
          return;
        }
        setError(optErr instanceof Error ? optErr.message : "Failed to load schedule");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const runOptimization = useCallback(async () => {
    setOptimizing(true);
    setError(null);
    setSolverProgress('Initializing PySCIPOpt MILP formulation...');
    try {
      setSolverProgress('Formulating track possession and shadow block constraints...');
      await new Promise(r => setTimeout(r, 200));
      setSolverProgress('Solving branch-and-cut optimization problem...');
      const result = await ApiClient.optimizeSchedule();
      setSchedule(result);
      if (result.kpi_metrics) {
        setKpis(result.kpi_metrics);
      }
      setSolverProgress(`Optimization complete: ${result.scheduled_jobs.length} jobs scheduled via ${result.solver}.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Optimization failed");
      setSolverProgress('Optimization failed.');
    } finally {
      setOptimizing(false);
    }
  }, []);

  useEffect(() => {
    fetchSchedule();
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [fetchSchedule]);

  return {
    schedule,
    kpis,
    loading,
    optimizing,
    solverProgress,
    error,
    viewMode,
    setViewMode,
    freezeWeek1,
    setFreezeWeek1,
    runOptimization,
    refresh: fetchSchedule
  };
}
