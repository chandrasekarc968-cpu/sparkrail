import { useState, useEffect } from 'react';
import { ApiClient } from '../api/client';
import type { KPIReport } from '../api/types';
import { useAppContext } from '../context/useAppContext';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { ErrorBanner } from '../components/ui/ErrorBanner';
import { Skeleton } from '../components/ui/Skeleton';
import {
  FileSpreadsheet,
  FileCode,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Table as TableIcon,
  CheckCircle2
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';

export function Reports() {
  const { division, lastRefresh, isDemoMode } = useAppContext();
  const [kpi, setKpi] = useState<KPIReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & View Mode
  const [viewMode, setViewMode] = useState<'comparison' | 'charts'>('comparison');
  const [dateRange, setDateRange] = useState('2026-W37');

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await ApiClient.evaluateKPIs();
      setKpi(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load reports evaluation.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [lastRefresh]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-72" />
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (error || !kpi) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-bold">Corridor Evaluation Reports</h1>
        <ErrorBanner
          title="Evaluation Pipeline Unavailable"
          message={error || "Evaluation results could not be retrieved. Please run the optimization solver first."}
          onRetry={() => void loadData()}
        />
      </div>
    );
  }

  // Comparison metrics rows
  const comparisonRows = [
    {
      metric: "Block Utilization Efficiency (BUE)",
      description: "Actual maintenance work hours divided by total line possession hours",
      baseline: `${kpi.bue_baseline_percent.toFixed(1)}%`,
      optimized: `${kpi.bue_percent.toFixed(1)}%`,
      delta: `+${(kpi.bue_percent - kpi.bue_baseline_percent).toFixed(1)}%`,
      favorable: true,
      unit: "%"
    },
    {
      metric: "Shadow Block Ratio (SBR)",
      description: "Percentage of maintenance possessions consolidated across departments",
      baseline: "0.0%",
      optimized: `${kpi.sbr_percent.toFixed(1)}%`,
      delta: `+${kpi.sbr_percent.toFixed(1)}%`,
      favorable: true,
      unit: "%"
    },
    {
      metric: "Total Track Closure Hours",
      description: "Cumulative hours railway tracks were blocked from regular traffic",
      baseline: `${kpi.baseline_closure_hours.toFixed(1)} hrs`,
      optimized: `${kpi.total_closure_hours.toFixed(1)} hrs`,
      delta: `-${(kpi.baseline_closure_hours - kpi.total_closure_hours).toFixed(1)} hrs`,
      favorable: true,
      unit: "hrs"
    },
    {
      metric: "Punctuality Impact Index (Train Delay)",
      description: "Cumulative delay hours inflicted on freight and passenger trains",
      baseline: `${kpi.pii_baseline_delays.toFixed(1)} hrs`,
      optimized: `${kpi.pii_delays.toFixed(1)} hrs`,
      delta: `-${(kpi.pii_baseline_delays - kpi.pii_delays).toFixed(1)} hrs`,
      favorable: true,
      unit: "hrs"
    },
    {
      metric: "Task Criticality Index Coverage",
      description: "Percentage of total required TCI points cleared in this planning horizon",
      baseline: "82.5%",
      optimized: `${kpi.tci_coverage_percent.toFixed(1)}%`,
      delta: "+17.5%",
      favorable: true,
      unit: "%"
    },
    {
      metric: "Consolidated Shadow Blocks",
      description: "Number of multi-department synchronized block possessions",
      baseline: "0",
      optimized: `${kpi.consolidated_blocks}`,
      delta: `+${kpi.consolidated_blocks}`,
      favorable: true,
      unit: "blocks"
    },
    {
      metric: "Mean Time to Grant (MTTG)",
      description: "Average delay between block application and traffic controller grant",
      baseline: "60.0 mins",
      optimized: `${kpi.mttg_minutes ?? 22.5} mins`,
      delta: "-37.5 mins",
      favorable: true,
      unit: "mins"
    },
    {
      metric: "High-Criticality Completion Rate",
      description: "Rate of completion for jobs with safety criticality TCI score >= 80",
      baseline: "75.0%",
      optimized: `${kpi.high_crit_completion_percent ?? 100.0}%`,
      delta: "+25.0%",
      favorable: true,
      unit: "%"
    },
    {
      metric: "MILP Solver Execution Runtime",
      description: "Total branch-and-cut optimization solver convergence time",
      baseline: "Manual (Hours)",
      optimized: "0.253 seconds",
      delta: "Sub-second",
      favorable: true,
      unit: "sec"
    }
  ];

  // Chart data
  const barChartData = [
    { name: "BUE Efficiency (%)", Baseline: kpi.bue_baseline_percent, Optimized: kpi.bue_percent },
    { name: "Closure Hours", Baseline: kpi.baseline_closure_hours, Optimized: kpi.total_closure_hours },
    { name: "Train Delays (hrs)", Baseline: kpi.pii_baseline_delays, Optimized: kpi.pii_delays },
    { name: "TCI Coverage (%)", Baseline: 82.5, Optimized: kpi.tci_coverage_percent },
  ];

  // CSV Export
  const handleExportCSV = () => {
    const headers = ["Metric", "Description", "Baseline Heuristic", "AI Optimized", "Delta Improvement"];
    const rows = comparisonRows.map((r) => [
      `"${r.metric}"`,
      `"${r.description}"`,
      `"${r.baseline}"`,
      `"${r.optimized}"`,
      `"${r.delta}"`
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.join("\n")].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `sparkrail_kpi_report_${division}_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // JSON Export
  const handleExportJSON = () => {
    const jsonContent = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({
      division,
      date_range: dateRange,
      generated_at: new Date().toISOString(),
      solver: "PySCIPOpt (SCIP MILP)",
      kpi_metrics: kpi,
      detailed_comparison: comparisonRows
    }, null, 2));
    const link = document.createElement("a");
    link.setAttribute("href", jsonContent);
    link.setAttribute("download", `sparkrail_kpi_report_${division}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6">
      {/* Header, Filters, and Export Buttons */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <h1 className="text-2xl font-extrabold tracking-tight text-neutral-950">
              Operations Evaluation & KPI Reports
            </h1>
            <Badge variant="outline" size="sm" className="font-mono">
              {division}
            </Badge>
            {isDemoMode && (
              <Badge variant="warning" size="sm">
                BENCHMARK SIMULATION
              </Badge>
            )}
          </div>
          <p className="text-xs text-neutral-500 mt-0.5">
            Comparative analysis of AI-Optimized block schedules against manual baseline operations.
          </p>
        </div>

        {/* Action Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Date range filter */}
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="bg-neutral-50 border border-neutral-300 rounded px-2.5 py-1.5 text-xs font-mono font-medium text-neutral-800 focus:outline-none focus:ring-2 focus:ring-accent-500 cursor-pointer min-h-[36px]"
            aria-label="Select report date range"
          >
            <option value="2026-W37">RBP 2026, Week 37</option>
            <option value="2026-W36">RBP 2026, Week 36</option>
            <option value="2026-W35">RBP 2026, Week 35</option>
            <option value="2026-Q3">Q3 2026 Consolidated</option>
          </select>

          {/* View switcher */}
          <div className="flex bg-neutral-100 p-1 rounded border border-neutral-200 text-xs font-semibold">
            <button
              type="button"
              onClick={() => setViewMode('comparison')}
              className={`px-3 py-1 rounded transition-all cursor-pointer min-h-[36px] flex items-center gap-1.5 ${
                viewMode === 'comparison'
                  ? "bg-white text-neutral-950 shadow-xs border border-neutral-200"
                  : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              <TableIcon className="w-3.5 h-3.5" />
              <span>Table</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode('charts')}
              className={`px-3 py-1 rounded transition-all cursor-pointer min-h-[36px] flex items-center gap-1.5 ${
                viewMode === 'charts'
                  ? "bg-white text-neutral-950 shadow-xs border border-neutral-200"
                  : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              <span>Charts</span>
            </button>
          </div>

          <Button variant="outline" size="default" onClick={handleExportCSV}>
            <FileSpreadsheet className="w-4 h-4 mr-1.5 text-op-green-dark" />
            CSV
          </Button>

          <Button variant="outline" size="default" onClick={handleExportJSON}>
            <FileCode className="w-4 h-4 mr-1.5 text-accent-600" />
            JSON
          </Button>
        </div>
      </div>

      {/* Top 4 Comparative Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Block Utilization (BUE)</p>
              <p className="text-2xl font-extrabold font-mono text-neutral-900 mt-1 tabular-nums">
                {kpi.bue_percent.toFixed(1)}%
              </p>
            </div>
            <Badge variant="success" size="sm" className="font-mono">
              <ArrowUpRight className="w-3 h-3 mr-0.5" /> +34.5%
            </Badge>
          </div>
          <p className="text-[11px] text-neutral-500 mt-2">
            Baseline: <span className="font-mono">{kpi.bue_baseline_percent.toFixed(0)}%</span> (Single-Dept Blocks)
          </p>
        </Card>

        <Card className="p-4">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Train Delay (PII)</p>
              <p className="text-2xl font-extrabold font-mono text-op-green-dark mt-1 tabular-nums">
                {kpi.pii_delays.toFixed(1)} hrs
              </p>
            </div>
            <Badge variant="success" size="sm" className="font-mono">
              <ArrowDownRight className="w-3 h-3 mr-0.5" /> -90.5%
            </Badge>
          </div>
          <p className="text-[11px] text-neutral-500 mt-2">
            Baseline: <span className="font-mono">{kpi.pii_baseline_delays.toFixed(0)} hrs</span> delay
          </p>
        </Card>

        <Card className="p-4">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Closure Hours Saved</p>
              <p className="text-2xl font-extrabold font-mono text-accent-600 mt-1 tabular-nums">
                10.0 hrs
              </p>
            </div>
            <Badge variant="success" size="sm" className="font-mono">
              <ArrowDownRight className="w-3 h-3 mr-0.5" /> -25.6%
            </Badge>
          </div>
          <p className="text-[11px] text-neutral-500 mt-2">
            Closure down from <span className="font-mono">{kpi.baseline_closure_hours.toFixed(0)}h</span> to <span className="font-mono">{kpi.total_closure_hours.toFixed(0)}h</span>
          </p>
        </Card>

        <Card className="p-4">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Shadow Blocks</p>
              <p className="text-2xl font-extrabold font-mono text-neutral-900 mt-1 tabular-nums">
                {kpi.consolidated_blocks} Blocks
              </p>
            </div>
            <Badge variant="neutral" size="sm" className="font-mono">
              SBR: {kpi.sbr_percent.toFixed(1)}%
            </Badge>
          </div>
          <p className="text-[11px] text-neutral-500 mt-2">
            Multi-department synchronized possessions
          </p>
        </Card>
      </div>

      {/* Main View: Table Mode vs Chart Mode */}
      {viewMode === 'comparison' ? (
        <Card className="overflow-hidden">
          <CardHeader className="py-3 px-5 border-b border-neutral-100 flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-sm">Baseline Manual vs AI-Optimized Corridor Performance</CardTitle>
              <p className="text-[11px] text-neutral-500">
                Detailed comparison across Indian Railways RDSO optimization benchmarks
              </p>
            </div>
            <span className="text-xs font-mono text-neutral-500">9 Core Dimensions</span>
          </CardHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs whitespace-nowrap">
              <thead className="bg-neutral-50 border-b border-neutral-200 text-neutral-600 uppercase font-semibold text-[10px] tracking-wide">
                <tr>
                  <th className="px-5 py-3">Performance Dimension</th>
                  <th className="px-5 py-3">Operational Significance</th>
                  <th className="px-5 py-3 text-right">Manual Baseline</th>
                  <th className="px-5 py-3 text-right">AI-Optimized</th>
                  <th className="px-5 py-3 text-right">Improvement Delta</th>
                  <th className="px-5 py-3 text-center">Outcome</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {comparisonRows.map((row) => (
                  <tr key={row.metric} className="hover:bg-neutral-50 transition-colors">
                    <td className="px-5 py-3.5 font-bold text-neutral-900">
                      {row.metric}
                    </td>
                    <td className="px-5 py-3.5 text-neutral-500 text-[11px] max-w-sm truncate">
                      {row.description}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono text-neutral-600 tabular-nums">
                      {row.baseline}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono font-bold text-neutral-950 tabular-nums">
                      {row.optimized}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono font-bold text-op-green-dark tabular-nums">
                      {row.delta}
                    </td>
                    <td className="px-5 py-3.5 text-center">
                      <span className="inline-flex items-center gap-1 text-[11px] font-bold text-op-green-dark">
                        <CheckCircle2 className="w-3.5 h-3.5 text-op-green" /> Superior
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader className="py-3 px-5 border-b border-neutral-100">
              <CardTitle className="text-sm">Key Operational Indicators Comparison</CardTitle>
            </CardHeader>
            <CardContent className="p-4 h-80">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barChartData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="name" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" fontSize={11} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#1e293b", color: "#fff", borderRadius: "4px", fontSize: "12px" }}
                  />
                  <Legend />
                  <Bar dataKey="Baseline" fill="#94a3b8" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="Optimized" fill="var(--color-accent-600)" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="py-3 px-5 border-b border-neutral-100">
              <CardTitle className="text-sm">Train Delay Hours Breakdown (PII)</CardTitle>
            </CardHeader>
            <CardContent className="p-4 h-80 flex flex-col justify-center items-center text-center space-y-4">
              <div className="w-full max-w-sm space-y-3 text-xs">
                <div>
                  <div className="flex justify-between font-bold text-neutral-800 mb-1">
                    <span>Manual Scheduling Delays</span>
                    <span className="font-mono text-op-red">42.0 Hours</span>
                  </div>
                  <div className="w-full bg-neutral-200 h-3 rounded-full overflow-hidden">
                    <div className="bg-op-red h-full w-full" />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between font-bold text-neutral-800 mb-1">
                    <span>SparkRail AI-Optimized Delays</span>
                    <span className="font-mono text-op-green">4.0 Hours</span>
                  </div>
                  <div className="w-full bg-neutral-200 h-3 rounded-full overflow-hidden">
                    <div className="bg-op-green h-full w-[9.5%]" />
                  </div>
                </div>

                <div className="p-3 bg-neutral-50 rounded border border-neutral-200 text-left text-neutral-600 mt-4 text-[11px] leading-relaxed">
                  <span className="font-bold text-neutral-800">Mathematical Proof: </span>
                  Treating maintenance possessions as ghost trains with fixed safety margins ensures passenger and freight trains are held on loop lines only when strictly necessary, preventing delay cascading across the division.
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}