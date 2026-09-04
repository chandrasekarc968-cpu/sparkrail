import { useState } from 'react';
import { useAppContext } from '../context/useAppContext';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { getApiBaseUrl, setApiBaseUrl, ApiClient } from '../api/client';
import {
  Server,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Cpu,
  RefreshCw,
  Shield
} from 'lucide-react';

export function Settings() {
  const {
    isDemoMode,
    setDemoMode,
    division,
    setDivision,
    divisions,
    planningHorizon,
    setPlanningHorizon,
    connectionStatus,
    refreshData
  } = useAppContext();

  const [apiUrl, setApiUrl] = useState(getApiBaseUrl());
  const [isSaved, setIsSaved] = useState(false);
  const [testResult, setTestResult] = useState<{ status: 'idle' | 'testing' | 'success' | 'failed'; message: string }>({
    status: 'idle',
    message: ''
  });

  // Feature Flags
  const [flagGNN, setFlagGNN] = useState(false);
  const [flagDRL, setFlagDRL] = useState(false);
  const [flagXGB, setFlagXGB] = useState(false);

  // Auto-refresh interval
  const [refreshInterval, setRefreshInterval] = useState('30s');

  const handleSaveApiUrl = () => {
    setApiBaseUrl(apiUrl);
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2000);
    refreshData();
  };

  const handleTestConnection = async () => {
    setTestResult({ status: 'testing', message: 'Pinging backend health check...' });
    try {
      const res = await ApiClient.getHealth();
      setTestResult({
        status: 'success',
        message: `Connected successfully. Server reports status: "${res.status}", version: "${res.version}".`
      });
    } catch (err: unknown) {
      setTestResult({
        status: 'failed',
        message: err instanceof Error ? err.message : 'Backend connection refused.'
      });
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-neutral-950">
          System Settings & Backend Configuration
        </h1>
        <p className="text-xs text-neutral-500 mt-0.5">
          Configure API endpoints, simulation replay modes, TCI weighting parameters, and experimental AI flags.
        </p>
      </div>

      {/* 1. Environment & API Base URL Configuration */}
      <Card>
        <CardHeader className="py-3 px-5 border-b border-neutral-100">
          <CardTitle className="text-sm flex items-center gap-2">
            <Server className="w-4 h-4 text-accent-600" />
            Backend Connection & Environment
          </CardTitle>
        </CardHeader>
        <CardContent className="p-5 space-y-5 text-xs">
          {/* Demo Mode Toggle */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 bg-neutral-50 rounded border border-neutral-200">
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-neutral-900 text-sm">Deterministic Simulation Mode</span>
                <Badge variant={isDemoMode ? "warning" : "outline"} size="sm">
                  {isDemoMode ? "Active" : "Disabled"}
                </Badge>
                <Badge variant={connectionStatus === "connected" ? "success" : connectionStatus === "demo" ? "warning" : "danger"} size="sm" className="uppercase font-mono text-[10px]">
                  {connectionStatus}
                </Badge>
              </div>
              <p className="text-neutral-500 text-xs mt-0.5 max-w-lg leading-relaxed">
                When enabled, the frontend runs autonomously against deterministic Indian Railways simulation data (8 blocks, 20 jobs, 10 trains). Disable to route live requests to the FastAPI backend.
              </p>
            </div>

            <button
              type="button"
              onClick={() => setDemoMode(!isDemoMode)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 cursor-pointer shrink-0 ${
                isDemoMode ? "bg-accent-600" : "bg-neutral-300"
              }`}
              aria-label="Toggle Demo Mode"
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  isDemoMode ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>

          {/* API Base URL */}
          <div className="space-y-2">
            <label htmlFor="api-base-url" className="font-bold text-neutral-800 block text-xs">
              FastAPI Backend Base URL
            </label>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                id="api-base-url"
                type="text"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="http://localhost:8000"
                className="flex-1 bg-white border border-neutral-300 rounded px-3 py-2 text-xs font-mono text-neutral-900 focus:outline-none focus:ring-2 focus:ring-accent-500 min-h-[40px]"
              />
              <Button variant="outline" size="default" onClick={handleTestConnection} className="shrink-0">
                <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                Test Ping
              </Button>
              <Button size="default" onClick={handleSaveApiUrl} className="shrink-0">
                {isSaved ? "Saved!" : "Save Endpoint"}
              </Button>
            </div>
            <p className="text-[11px] text-neutral-400">
              Default fallback: <span className="font-mono">http://localhost:8000</span> (managed via .env or localStorage override)
            </p>

            {/* Test result status */}
            {testResult.status === 'success' && (
              <div className="p-3 rounded bg-op-green-light/40 border border-op-green/30 text-op-green-dark flex items-center space-x-2 text-xs">
                <CheckCircle2 className="w-4 h-4 text-op-green shrink-0" />
                <span>{testResult.message}</span>
              </div>
            )}
            {testResult.status === 'failed' && (
              <div className="p-3 rounded bg-op-red-light/40 border border-op-red/30 text-op-red-dark flex items-center space-x-2 text-xs">
                <AlertTriangle className="w-4 h-4 text-op-red shrink-0" />
                <span>{testResult.message}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 2. Operations & Horizon Settings */}
      <Card>
        <CardHeader className="py-3 px-5 border-b border-neutral-100">
          <CardTitle className="text-sm flex items-center gap-2">
            <Sliders className="w-4 h-4 text-accent-600" />
            Operational Parameters & Planning Horizons
          </CardTitle>
        </CardHeader>
        <CardContent className="p-5 space-y-4 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Division */}
            <div>
              <label htmlFor="settings-division" className="font-bold text-neutral-800 block mb-1">
                Active Railway Division
              </label>
              <select
                id="settings-division"
                value={division}
                onChange={(e) => setDivision(e.target.value)}
                className="w-full bg-white border border-neutral-300 rounded px-3 py-2 text-xs text-neutral-900 focus:outline-none focus:ring-2 focus:ring-accent-500 cursor-pointer min-h-[38px]"
              >
                {divisions.map((d) => (
                  <option key={d.code} value={d.code}>
                    {d.name} ({d.zone})
                  </option>
                ))}
              </select>
            </div>

            {/* Planning Horizon */}
            <div>
              <label htmlFor="settings-horizon" className="font-bold text-neutral-800 block mb-1">
                Planning Horizon
              </label>
              <select
                id="settings-horizon"
                value={planningHorizon}
                onChange={(e) => setPlanningHorizon(e.target.value)}
                className="w-full bg-white border border-neutral-300 rounded px-3 py-2 text-xs text-neutral-900 focus:outline-none focus:ring-2 focus:ring-accent-500 cursor-pointer min-h-[38px]"
              >
                <option value="RBP 2026, Week 37">RBP 2026, Week 37 (Rolling Block Program)</option>
                <option value="RBP 2026, Week 38">RBP 2026, Week 38</option>
                <option value="24-Hour Corridor Surge">24-Hour Tactical Surge Plan</option>
                <option value="52-Week Master Schedule">52-Week Annual Master Program</option>
              </select>
            </div>

            {/* Timezone */}
            <div>
              <label className="font-bold text-neutral-800 block mb-1">Operational Timezone</label>
              <input
                type="text"
                disabled
                value="Asia/Kolkata (IST, UTC+05:30)"
                className="w-full bg-neutral-50 border border-neutral-200 rounded px-3 py-2 text-xs text-neutral-500 cursor-not-allowed font-mono min-h-[38px]"
              />
            </div>

            {/* Refresh Interval */}
            <div>
              <label htmlFor="settings-refresh" className="font-bold text-neutral-800 block mb-1">
                Auto-Telemetry Refresh Interval
              </label>
              <select
                id="settings-refresh"
                value={refreshInterval}
                onChange={(e) => setRefreshInterval(e.target.value)}
                className="w-full bg-white border border-neutral-300 rounded px-3 py-2 text-xs text-neutral-900 focus:outline-none focus:ring-2 focus:ring-accent-500 cursor-pointer min-h-[38px]"
              >
                <option value="15s">Every 15 seconds</option>
                <option value="30s">Every 30 seconds</option>
                <option value="60s">Every 60 seconds</option>
                <option value="off">Manual Refresh Only</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 3. Task Criticality Index (TCI) Standard Weights */}
      <Card>
        <CardHeader className="py-3 px-5 border-b border-neutral-100">
          <CardTitle className="text-sm flex items-center gap-2">
            <Shield className="w-4 h-4 text-accent-600" />
            Task Criticality Index (TCI) Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="p-5 space-y-3 text-xs">
          <p className="text-neutral-500 text-xs leading-relaxed">
            TCI balances safety urgency, network capacity impacts, asset degradation velocity, and overdue days. Standard weights defined in <span className="font-mono">config/settings.yaml</span>:
          </p>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
            <div className="p-3 bg-neutral-50 rounded border border-neutral-200 text-center">
              <span className="text-[10px] font-bold uppercase text-neutral-500 block">Safety Risk (w1)</span>
              <span className="text-lg font-bold font-mono text-op-red">0.40</span>
              <span className="text-[10px] text-neutral-400 block mt-0.5">40% Weight</span>
            </div>

            <div className="p-3 bg-neutral-50 rounded border border-neutral-200 text-center">
              <span className="text-[10px] font-bold uppercase text-neutral-500 block">Delay Impact (w2)</span>
              <span className="text-lg font-bold font-mono text-amber-700">0.30</span>
              <span className="text-[10px] text-neutral-400 block mt-0.5">30% Weight</span>
            </div>

            <div className="p-3 bg-neutral-50 rounded border border-neutral-200 text-center">
              <span className="text-[10px] font-bold uppercase text-neutral-500 block">Degradation (w3)</span>
              <span className="text-lg font-bold font-mono text-op-blue">0.20</span>
              <span className="text-[10px] text-neutral-400 block mt-0.5">20% Weight</span>
            </div>

            <div className="p-3 bg-neutral-50 rounded border border-neutral-200 text-center">
              <span className="text-[10px] font-bold uppercase text-neutral-500 block">Overdue Penalty (w4)</span>
              <span className="text-lg font-bold font-mono text-neutral-800">0.10</span>
              <span className="text-[10px] text-neutral-400 block mt-0.5">10% Weight</span>
            </div>
          </div>

          <div className="p-2.5 bg-neutral-50 rounded border border-neutral-200 text-neutral-600 font-mono text-[11px]">
            Formula: TCI = 100 * (0.4*Safety + 0.3*Traffic + 0.2*Degradation + 0.1*log1p(OverdueDays)/log1p(30))
          </div>
        </CardContent>
      </Card>

      {/* 4. Experimental Research Feature Flags */}
      <Card>
        <CardHeader className="py-3 px-5 border-b border-neutral-100">
          <CardTitle className="text-sm flex items-center gap-2">
            <Cpu className="w-4 h-4 text-accent-600" />
            AI & Optimization Modules
          </CardTitle>
        </CardHeader>
        <CardContent className="p-5 space-y-4 text-xs">
          {/* Core Solver Status */}
          <div className="p-3 bg-op-green-light/40 border border-op-green/30 rounded flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-op-green" />
              <div>
                <p className="font-bold text-op-green-dark">PySCIPOpt (SCIP MILP Solver Engine)</p>
                <p className="text-[11px] text-neutral-600">Production Baseline Solver. Big-M = 100,000. Time limit = 60s.</p>
              </div>
            </div>
            <Badge variant="success" size="sm">
              Certified Active
            </Badge>
          </div>

          {/* Flag 1: GNN State Encoder */}
          <div className="flex items-center justify-between p-3 bg-neutral-50 rounded border border-neutral-200">
            <div>
              <p className="font-bold text-neutral-900">Heterogeneous Graph Neural Network (GNN) State Encoder</p>
              <p className="text-[11px] text-neutral-500">
                PyTorch Geometric neural message passing over spatio-temporal track graph.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setFlagGNN(!flagGNN)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none cursor-pointer shrink-0 ${
                flagGNN ? "bg-accent-600" : "bg-neutral-300"
              }`}
              aria-label="Toggle GNN Flag"
            >
              <span
                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  flagGNN ? "translate-x-4" : "translate-x-1"
                }`}
              />
            </button>
          </div>

          {/* Flag 2: DRL Tactical Dispatcher */}
          <div className="flex items-center justify-between p-3 bg-neutral-50 rounded border border-neutral-200">
            <div>
              <p className="font-bold text-neutral-900">Deep Reinforcement Learning (DRL) Tactical Dispatcher</p>
              <p className="text-[11px] text-neutral-500">
                Proximal Policy Optimization (PPO) sub-second conflict avoidance agent trained in SUMO.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setFlagDRL(!flagDRL)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none cursor-pointer shrink-0 ${
                flagDRL ? "bg-accent-600" : "bg-neutral-300"
              }`}
              aria-label="Toggle DRL Flag"
            >
              <span
                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  flagDRL ? "translate-x-4" : "translate-x-1"
                }`}
              />
            </button>
          </div>

          {/* Flag 3: XGBoost Degradation */}
          <div className="flex items-center justify-between p-3 bg-neutral-50 rounded border border-neutral-200">
            <div>
              <p className="font-bold text-neutral-900">XGBoost Non-Linear Track Degradation</p>
              <p className="text-[11px] text-neutral-500">
                Gradient boosted decision trees trained on cumulative Gross Million Tonnes (GMT).
              </p>
            </div>
            <button
              type="button"
              onClick={() => setFlagXGB(!flagXGB)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none cursor-pointer shrink-0 ${
                flagXGB ? "bg-accent-600" : "bg-neutral-300"
              }`}
              aria-label="Toggle XGBoost Flag"
            >
              <span
                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  flagXGB ? "translate-x-4" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        </CardContent>
      </Card>

      {/* 5. System Specifications & Commit Information */}
      <Card>
        <CardHeader className="py-3 px-5 border-b border-neutral-100">
          <CardTitle className="text-sm">Build & Specification Metadata</CardTitle>
        </CardHeader>
        <CardContent className="p-5 text-xs space-y-2 font-mono text-neutral-600">
          <div className="flex justify-between py-1 border-b border-neutral-100">
            <span>System Version:</span>
            <span className="font-bold text-neutral-900">SparkRail AI Block Planning v1.0.0-rc2</span>
          </div>
          <div className="flex justify-between py-1 border-b border-neutral-100">
            <span>Indian Railways Problem Statement:</span>
            <span className="font-bold text-neutral-900">ID 26027 (RDSO Block Planning)</span>
          </div>
          <div className="flex justify-between py-1 border-b border-neutral-100">
            <span>Frontend Architecture:</span>
            <span className="text-neutral-800">React 19 + TypeScript + Vite + Tailwind CSS v4 + OKLCH</span>
          </div>
          <div className="flex justify-between py-1 border-b border-neutral-100">
            <span>Git Reference:</span>
            <span className="text-neutral-800">main @ a87f2e1 (control-room-prod)</span>
          </div>
          <div className="flex justify-between py-1">
            <span>Security Guarantee:</span>
            <span className="text-op-green-dark font-semibold">No tokens or private credentials exposed in client storage</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}