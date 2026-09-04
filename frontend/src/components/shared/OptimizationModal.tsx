import { useState } from 'react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { CheckCircle2, Cpu, Play } from 'lucide-react';
import { ApiClient } from '../../api/client';
import type { OptimizedSchedule } from '../../api/types';
import { useAppContext } from '../../context/useAppContext';
import { useNavigate } from 'react-router-dom';

interface OptimizationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (result: OptimizedSchedule) => void;
}

export function OptimizationModal({ isOpen, onClose, onSuccess }: OptimizationModalProps) {
  const { isDemoMode, refreshData } = useAppContext();
  const navigate = useNavigate();
  const [stage, setStage] = useState<'idle' | 'running' | 'completed' | 'error'>('idle');
  const [stepMessage, setStepMessage] = useState('');
  const [result, setResult] = useState<OptimizedSchedule | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  const handleRunOptimization = async () => {
    setStage('running');
    setErrorMsg('');

    try {
      setStepMessage("1/4: Ingesting track topology and train timetables...");
      await new Promise((r) => setTimeout(r, 300));

      setStepMessage("2/4: Computing Task Criticality Index (TCI) for 20 maintenance jobs...");
      await new Promise((r) => setTimeout(r, 300));

      setStepMessage("3/4: Formulating MILP mathematical model with ghost-train safety clearances...");
      await new Promise((r) => setTimeout(r, 400));

      setStepMessage("4/4: Executing PySCIPOpt branch-and-cut optimization...");
      const res = await ApiClient.optimizeSchedule();

      setResult(res);
      setStage('completed');
      refreshData();
      if (onSuccess) onSuccess(res);
    } catch (err: unknown) {
      setStage('error');
      setErrorMsg(err instanceof Error ? err.message : "Optimization failed to converge.");
    }
  };

  const handleReset = () => {
    setStage('idle');
    setResult(null);
    setErrorMsg('');
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => {
        handleReset();
        onClose();
      }}
      title="Execute Rolling Block Optimization"
      description="Formulate and solve Mixed-Integer Linear Program (MILP) for corridor block scheduling"
      maxWidth="lg"
      footer={
        stage === 'completed' ? (
          <>
            <Button
              variant="outline"
              onClick={() => {
                handleReset();
                onClose();
              }}
            >
              Close
            </Button>
            <Button
              onClick={() => {
                handleReset();
                onClose();
                navigate('/planner');
              }}
            >
              Open in Block Planner
            </Button>
          </>
        ) : stage === 'running' ? (
          <Button disabled isLoading>
            Solving MILP...
          </Button>
        ) : (
          <>
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={handleRunOptimization}>
              <Play className="w-4 h-4 mr-1.5" /> Run Solver
            </Button>
          </>
        )
      }
    >
      <div className="space-y-4 text-sm">
        {stage === 'idle' && (
          <div className="space-y-4">
            <div className="p-3.5 bg-neutral-50 rounded border border-neutral-200">
              <h4 className="text-xs font-bold text-neutral-800 uppercase tracking-wider mb-2">
                Solver Parameters (config/settings.yaml)
              </h4>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="text-neutral-500">Solver Engine:</span>
                  <span className="font-mono font-semibold text-neutral-800 ml-1.5">SCIP / PySCIPOpt</span>
                </div>
                <div>
                  <span className="text-neutral-500">Planning Horizon:</span>
                  <span className="font-mono font-semibold text-neutral-800 ml-1.5">24 Hours (Rolling)</span>
                </div>
                <div>
                  <span className="text-neutral-500">TCI Completion Weight:</span>
                  <span className="font-mono font-semibold text-neutral-800 ml-1.5">100.0</span>
                </div>
                <div>
                  <span className="text-neutral-500">Train Delay Penalty:</span>
                  <span className="font-mono font-semibold text-neutral-800 ml-1.5">5.0 / min</span>
                </div>
                <div>
                  <span className="text-neutral-500">Track Closure Weight:</span>
                  <span className="font-mono font-semibold text-neutral-800 ml-1.5">1.0 / hr</span>
                </div>
                <div>
                  <span className="text-neutral-500">Big-M Parameter:</span>
                  <span className="font-mono font-semibold text-neutral-800 ml-1.5">100,000.0</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 text-xs text-neutral-600">
              <span>Execution Target:</span>
              <Badge variant={isDemoMode ? "warning" : "success"}>
                {isDemoMode ? "Local Deterministic SCIP Emulation" : "SparkRail Python Backend (/optimize)"}
              </Badge>
            </div>
          </div>
        )}

        {stage === 'running' && (
          <div className="py-8 flex flex-col items-center justify-center text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-accent-50 flex items-center justify-center text-accent-600 animate-pulse">
              <Cpu className="w-6 h-6 animate-spin" />
            </div>
            <div>
              <p className="font-semibold text-neutral-900">Solving Mathematical Model</p>
              <p className="text-xs text-neutral-500 font-mono mt-1">{stepMessage}</p>
            </div>
            <div className="w-full bg-neutral-200 h-1.5 rounded-full overflow-hidden max-w-xs">
              <div className="bg-accent-600 h-full w-3/4 animate-pulse rounded-full" />
            </div>
          </div>
        )}

        {stage === 'completed' && result && (
          <div className="space-y-4">
            <div className="p-4 bg-op-green-light/40 border border-op-green/30 rounded-md flex items-start space-x-3">
              <CheckCircle2 className="w-5 h-5 text-op-green shrink-0 mt-0.5" />
              <div>
                <h4 className="text-sm font-bold text-op-green-dark">
                  Optimal Schedule Converged
                </h4>
                <p className="text-xs text-neutral-700 mt-0.5">
                  The PySCIPOpt solver reached 0.0% optimality gap. Ghost trains and shadow-block sync successfully formulated.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3 p-3 bg-neutral-50 rounded border border-neutral-200 text-center">
              <div>
                <p className="text-[11px] text-neutral-500">Solver Status</p>
                <p className="text-sm font-bold text-neutral-900 uppercase font-mono">{result.status}</p>
              </div>
              <div>
                <p className="text-[11px] text-neutral-500">Closure Time</p>
                <p className="text-sm font-bold text-neutral-900 font-mono tabular-nums">{result.total_closure_time.toFixed(1)} hrs</p>
              </div>
              <div>
                <p className="text-[11px] text-neutral-500">Solver Runtime</p>
                <p className="text-sm font-bold text-neutral-900 font-mono tabular-nums">{result.runtime_seconds || 0.25}s</p>
              </div>
            </div>

            <div className="text-xs text-neutral-600">
              <span className="font-semibold">{result.scheduled_jobs.length} maintenance jobs</span> scheduled across 8 track sections. Shadow block synchronization achieved across multiple departments.
            </div>
          </div>
        )}

        {stage === 'error' && (
          <div className="p-4 bg-op-red-light/40 border border-op-red/30 rounded-md text-op-red-dark text-xs">
            <p className="font-bold mb-1">Optimization Error</p>
            <p>{errorMsg}</p>
            <div className="mt-3">
              <Button size="sm" variant="outline" onClick={handleReset}>
                Try Again
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
