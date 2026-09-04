import { useEffect, useState, useCallback } from 'react';
import { ApiClient } from '../api/client';
import type { OptimizedSchedule, Scenario, ScoredJob, SystemEvent } from '../api/types';
import { useAppContext } from '../context/useAppContext';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { TCIBadge } from '../components/shared/TCIBadge';
import { OptimizationModal } from '../components/shared/OptimizationModal';
import { ConflictModal } from '../components/shared/ConflictModal';
import { ErrorBanner } from '../components/ui/ErrorBanner';
import { Skeleton } from '../components/ui/Skeleton';
import {
  Play,
  Activity,
  AlertTriangle,
  CheckCircle2,
  ArrowRight
} from 'lucide-react';
import { Link } from 'react-router-dom';

export function Overview() {
  const { division, lastRefresh, isDemoMode } = useAppContext();
  const [schedule, setSchedule] = useState<OptimizedSchedule | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [scoredJobs, setScoredJobs] = useState<ScoredJob[]>([]);
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isOptimizeModalOpen, setIsOptimizeModalOpen] = useState(false);
  const [isConflictModalOpen, setIsConflictModalOpen] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [scen, sched, scored, evts] = await Promise.all([
        ApiClient.getScenario(),
        ApiClient.getSchedule("latest"),
        ApiClient.scoreJobs(),
        ApiClient.getEvents()
      ]);
      setScenario(scen);
      setSchedule(sched);
      setScoredJobs(scored.scored_jobs);
      setEvents(evts);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load operations data from backend.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData, lastRefresh]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-10 w-48" />
        </div>
        <Skeleton className="h-32 w-full" />
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Skeleton className="h-96 lg:col-span-2" />
          <Skeleton className="h-96" />
        </div>
      </div>
    );
  }

  if (error || !schedule || !scenario) {
    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-xl font-bold tracking-tight">Operations Overview</h1>
        </div>
        <ErrorBanner
          title="Corridor Telemetry Disconnected"
          message={error || "Could not retrieve schedule or scenario data."}
          onRetry={() => void loadData()}
        />
      </div>
    );
  }

  const kpi = schedule.kpi_metrics;

  // Top 5 High-TCI Jobs
  const sortedJobs = [...scoredJobs].sort((a, b) => b.tci - a.tci).slice(0, 5);

  // Active blocks: blocks with jobs running between hour 2.0 and 8.0 in scenario
  const activeBlockIds = new Set(
    schedule.scheduled_jobs
      .filter((j) => j.start_time <= 6.0 && j.end_time >= 2.0)
      .map((j) => j.block_id)
  );

  return (
    <div className="space-y-6">
      {/* Top Banner / Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <h1 className="text-2xl font-extrabold tracking-tight text-neutral-950">
              Operations Overview
            </h1>
            <Badge variant="outline" size="sm" className="font-mono">
              {division} CONTROL ROOM
            </Badge>
            {isDemoMode && (
              <Badge variant="warning" size="sm">
                SIMULATION DATA
              </Badge>
            )}
          </div>
          <p className="text-xs text-neutral-500 mt-0.5">
            Real-time track block synchronization, asset criticality queue, and train conflict surveillance.
          </p>
        </div>

        <div className="flex items-center space-x-2.5">
          <Button
            variant="outline"
            size="default"
            onClick={() => setIsConflictModalOpen(true)}
            className="border-neutral-300"
          >
            <Activity className="w-4 h-4 mr-2 text-op-amber-dark" />
            Review Conflicts
          </Button>

          <Button
            size="default"
            onClick={() => setIsOptimizeModalOpen(true)}
          >
            <Play className="w-4 h-4 mr-2 fill-current" />
            Run Optimization
          </Button>
        </div>
      </div>

      {/* 1. Dominant Operations Summary Area */}
      <div className="bg-white border border-neutral-200 rounded-md p-5 shadow-xs">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-op-green animate-pulse" />
              <span className="text-xs font-bold uppercase tracking-wider text-op-green-dark">
                Division Status: Operational with Active Coordinated Blocks
              </span>
            </div>
            <h2 className="text-xl font-bold text-neutral-900 tracking-tight">
              24-Hour Corridor Optimization Horizon: 20 Jobs Synced Across 8 Blocks
            </h2>
            <p className="text-xs text-neutral-600 max-w-2xl leading-relaxed">
              Classical MILP solver formulated special ghost-train reservations, eliminating 38.0 hours of train delay compared to manual heuristics. 3 multi-department shadow blocks active on sections B2, B5, and B7.
            </p>
          </div>

          <div className="flex items-center gap-4 shrink-0 bg-neutral-50 p-3.5 rounded border border-neutral-200">
            <div className="text-center px-3 border-r border-neutral-200">
              <p className="text-[10px] uppercase font-bold text-neutral-500">Track Availability</p>
              <p className="text-xl font-extrabold text-op-green-dark font-mono tabular-nums">91.2%</p>
              <p className="text-[10px] text-neutral-400">Normal 85.0%</p>
            </div>
            <div className="text-center px-3 border-r border-neutral-200">
              <p className="text-[10px] uppercase font-bold text-neutral-500">Delay Avoidance</p>
              <p className="text-xl font-extrabold text-accent-600 font-mono tabular-nums">
                -38.0h
              </p>
              <p className="text-[10px] text-op-green font-semibold">90.5% cut</p>
            </div>
            <div className="text-center px-3">
              <p className="text-[10px] uppercase font-bold text-neutral-500">Solver Engine</p>
              <p className="text-sm font-extrabold text-neutral-800 font-mono mt-1">PySCIPOpt</p>
              <p className="text-[10px] text-neutral-500">0.0% Gap</p>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Compact KPI Rail (8 high-signal metrics) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
        <div className="bg-white border border-neutral-200 rounded p-3">
          <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-tight truncate">Active Blocks</p>
          <div className="text-xl font-extrabold text-neutral-900 font-mono tabular-nums mt-0.5">
            {activeBlockIds.size}
          </div>
          <p className="text-[10px] text-op-amber-dark font-medium mt-0.5">B1, B4 active now</p>
        </div>

        <div className="bg-white border border-neutral-200 rounded p-3">
          <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-tight truncate">Scheduled Jobs</p>
          <div className="text-xl font-extrabold text-neutral-900 font-mono tabular-nums mt-0.5">
            {schedule.scheduled_jobs.length}
          </div>
          <p className="text-[10px] text-neutral-500 mt-0.5">Week 37 Program</p>
        </div>

        <div className="bg-white border border-neutral-200 rounded p-3">
          <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-tight truncate">High-TCI Queue</p>
          <div className="text-xl font-extrabold text-op-red font-mono tabular-nums mt-0.5">
            {scoredJobs.filter((j) => j.tci >= 70).length}
          </div>
          <p className="text-[10px] text-op-red-dark font-medium mt-0.5">Urgent Safety</p>
        </div>

        <div className="bg-white border border-neutral-200 rounded p-3">
          <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-tight truncate">Train Delays (PII)</p>
          <div className="text-xl font-extrabold text-op-green font-mono tabular-nums mt-0.5">
            {kpi?.pii_delays.toFixed(1)}h
          </div>
          <p className="text-[10px] text-op-green-dark font-medium mt-0.5">Baseline: {kpi?.pii_baseline_delays.toFixed(0)}h</p>
        </div>

        <div className="bg-white border border-neutral-200 rounded p-3">
          <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-tight truncate">Shadow Block (SBR)</p>
          <div className="text-xl font-extrabold text-accent-600 font-mono tabular-nums mt-0.5">
            {kpi?.sbr_percent.toFixed(1)}%
          </div>
          <p className="text-[10px] text-neutral-500 mt-0.5">{kpi?.consolidated_blocks} Multi-dept</p>
        </div>

        <div className="bg-white border border-neutral-200 rounded p-3">
          <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-tight truncate">Block Efficiency (BUE)</p>
          <div className="text-xl font-extrabold text-neutral-900 font-mono tabular-nums mt-0.5">
            {kpi?.bue_percent.toFixed(1)}%
          </div>
          <p className="text-[10px] text-op-green font-medium mt-0.5">Baseline 100%</p>
        </div>

        <div className="bg-white border border-neutral-200 rounded p-3">
          <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-tight truncate">Mean Time to Grant</p>
          <div className="text-xl font-extrabold text-neutral-900 font-mono tabular-nums mt-0.5">
            {kpi?.mttg_minutes ?? 22.5}m
          </div>
          <p className="text-[10px] text-op-green-dark font-medium mt-0.5">-62% approval lag</p>
        </div>

        <div className="bg-white border border-neutral-200 rounded p-3">
          <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-tight truncate">Critical Asset Alerts</p>
          <div className="text-xl font-extrabold text-op-red font-mono tabular-nums mt-0.5">
            2
          </div>
          <p className="text-[10px] text-op-red-dark font-medium mt-0.5">USFD & Bridge</p>
        </div>
      </div>

      {/* 3. Today's Timeline Strip (Hour 0 to 24 Track Occupancy Ribbon) */}
      <Card>
        <CardHeader className="py-3 px-5 flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-sm">Today's Corridor Timeline Strip (00:00 to 24:00)</CardTitle>
            <p className="text-[11px] text-neutral-500">Track closure windows and train movements across block sections B1 to B8</p>
          </div>
          <Link to="/planner" className="text-xs font-semibold text-accent-600 hover:text-accent-700 flex items-center gap-1">
            Open Full Planner <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </CardHeader>
        <CardContent className="p-4 bg-neutral-50 overflow-x-auto">
          <div className="min-w-[720px] space-y-2">
            {/* Hour marker headers */}
            <div className="flex border-b border-neutral-200 pb-1 text-[10px] font-mono text-neutral-400">
              <div className="w-16 shrink-0 font-bold text-neutral-600">SECTION</div>
              <div className="flex-1 flex justify-between px-1">
                {Array.from({ length: 9 }).map((_, i) => (
                  <span key={i}>{i * 3}:00</span>
                ))}
              </div>
            </div>

            {/* Block timeline rows */}
            {scenario.blocks.map((b) => {
              const jobsOnBlock = schedule.scheduled_jobs.filter((j) => j.block_id === b.id);
              return (
                <div key={b.id} className="flex items-center h-7 text-xs">
                  <div className="w-16 shrink-0 font-mono font-bold text-neutral-800 flex items-center gap-1">
                    <span>{b.id}</span>
                    {activeBlockIds.has(b.id) && (
                      <span className="w-1.5 h-1.5 rounded-full bg-op-red" title="Active block" />
                    )}
                  </div>
                  <div className="flex-1 relative h-6 bg-white rounded border border-neutral-200 overflow-hidden">
                    {/* Hour grid markings */}
                    {Array.from({ length: 8 }).map((_, i) => (
                      <div
                        key={i}
                        className="absolute top-0 bottom-0 border-l border-neutral-100 pointer-events-none"
                        style={{ left: `${((i + 1) / 8) * 100}%` }}
                      />
                    ))}

                    {/* Maintenance blocks */}
                    {jobsOnBlock.map((job) => {
                      const left = (job.start_time / 24) * 100;
                      const width = ((job.end_time - job.start_time) / 24) * 100;
                      const isFixed = job.job_id.startsWith("J_FIXED");
                      const isShadow = job.is_shadow_block;

                      let bg = "bg-op-blue/80 border-op-blue text-white";
                      if (job.department === "Engineering") bg = "bg-op-red/80 border-op-red text-white";
                      if (job.department === "S&T") bg = "bg-amber-600 border-amber-700 text-white";
                      if (isFixed) bg = "bg-neutral-800 border-neutral-900 text-white pattern-diagonal-stripes";

                      return (
                        <div
                          key={job.job_id}
                          className={`absolute top-0.5 bottom-0.5 rounded px-1 text-[10px] font-mono font-bold flex items-center truncate border ${bg} ${
                            isShadow ? "ring-1 ring-white" : ""
                          }`}
                          style={{ left: `${Math.max(0, left)}%`, width: `${Math.min(100, Math.max(4, width))}%` }}
                          title={`${job.job_id} (${job.department}) ${job.start_time}:00-${job.end_time}:00 on ${b.id}`}
                        >
                          <span className="truncate">{job.job_id}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* 4. Ranked Criticality Queue & Network Status & Department Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Ranked Criticality Queue (Top 5 High-TCI Jobs) */}
        <Card className="lg:col-span-2">
          <CardHeader className="py-3 px-5 flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-sm">Ranked Task Criticality Queue (Top 5 Priority)</CardTitle>
              <p className="text-[11px] text-neutral-500">
                Calculated using TCI: 40% Safety + 30% Delay Impact + 20% Degradation + 10% Overdue
              </p>
            </div>
            <Link to="/jobs" className="text-xs font-semibold text-accent-600 hover:text-accent-700">
              View All 20 Jobs →
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs whitespace-nowrap">
                <thead className="bg-neutral-50 border-b border-neutral-200 text-neutral-600 uppercase font-semibold text-[10px]">
                  <tr>
                    <th className="px-4 py-2.5">Rank / ID</th>
                    <th className="px-4 py-2.5">Department</th>
                    <th className="px-4 py-2.5">Section</th>
                    <th className="px-4 py-2.5">Task Description</th>
                    <th className="px-4 py-2.5">TCI Score</th>
                    <th className="px-4 py-2.5">Safety Clearance</th>
                    <th className="px-4 py-2.5">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {sortedJobs.map((item, index) => {
                    const fullJob = scenario.jobs.find((j) => j.id === item.job_id);
                    const isScheduled = schedule.scheduled_jobs.some((j) => j.job_id === item.job_id);
                    return (
                      <tr key={item.job_id} className="hover:bg-neutral-50/70 transition-colors">
                        <td className="px-4 py-3 font-mono font-bold text-neutral-900">
                          #{index + 1} {item.job_id}
                        </td>
                        <td className="px-4 py-3">
                          <Badge
                            variant={
                              fullJob?.department === "Engineering"
                                ? "engineering"
                                : fullJob?.department === "OHE"
                                ? "ohe"
                                : "snt"
                            }
                            size="sm"
                          >
                            {fullJob?.department}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 font-mono font-bold text-neutral-700">
                          {fullJob?.block_id}
                        </td>
                        <td className="px-4 py-3 text-neutral-800 max-w-xs truncate font-medium">
                          {fullJob?.job_type || "Routine Maintenance"}
                        </td>
                        <td className="px-4 py-3">
                          <TCIBadge score={item.tci} size="sm" />
                        </td>
                        <td className="px-4 py-3 text-neutral-500 text-[11px] max-w-xs truncate">
                          {fullJob?.safety_clearance_required}
                        </td>
                        <td className="px-4 py-3">
                          {isScheduled ? (
                            <Badge variant="success" size="sm">
                              Scheduled
                            </Badge>
                          ) : (
                            <Badge variant="warning" size="sm">
                              Pending Review
                            </Badge>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Small Network Status Panel & Department Split */}
        <div className="space-y-6">
          {/* Network Status Panel */}
          <Card>
            <CardHeader className="py-3 px-5">
              <CardTitle className="text-sm">Block Sections Status (B1 to B8)</CardTitle>
              <p className="text-[11px] text-neutral-500">Speed restrictions & active possession</p>
            </CardHeader>
            <CardContent className="p-4 space-y-2.5">
              <div className="grid grid-cols-2 gap-2 text-xs">
                {scenario.blocks.map((block) => {
                  const hasActive = activeBlockIds.has(block.id);
                  return (
                    <div
                      key={block.id}
                      className={`p-2 rounded border flex flex-col justify-between ${
                        hasActive
                          ? "border-op-red/40 bg-op-red-light/30"
                          : "border-neutral-200 bg-neutral-50/70"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-neutral-900">{block.id}</span>
                        {hasActive ? (
                          <span className="text-[9px] font-bold uppercase text-op-red font-mono">BLOCKED</span>
                        ) : (
                          <span className="text-[9px] font-bold uppercase text-op-green font-mono">CLEAR</span>
                        )}
                      </div>
                      <div className="text-[10px] text-neutral-500 truncate mt-1">
                        TSR: {block.speed_restriction_kmh || 100} km/h
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* Department Distribution */}
          <Card>
            <CardHeader className="py-3 px-5">
              <CardTitle className="text-sm">Department Workload Distribution</CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-3 text-xs">
              <div>
                <div className="flex justify-between font-semibold mb-1">
                  <span className="text-red-800 flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-xs bg-op-red" />
                    Engineering (Civil)
                  </span>
                  <span className="font-mono">7 Jobs (14h Closure)</span>
                </div>
                <div className="w-full bg-neutral-100 h-2 rounded-full overflow-hidden">
                  <div className="bg-op-red h-full w-[35%]" />
                </div>
              </div>

              <div>
                <div className="flex justify-between font-semibold mb-1">
                  <span className="text-amber-900 flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-xs bg-amber-600" />
                    S&T (Signaling & Telecom)
                  </span>
                  <span className="font-mono">8 Jobs (16h Closure)</span>
                </div>
                <div className="w-full bg-neutral-100 h-2 rounded-full overflow-hidden">
                  <div className="bg-amber-600 h-full w-[40%]" />
                </div>
              </div>

              <div>
                <div className="flex justify-between font-semibold mb-1">
                  <span className="text-blue-800 flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-xs bg-op-blue" />
                    OHE (Traction Power)
                  </span>
                  <span className="font-mono">5 Jobs (9h Closure)</span>
                </div>
                <div className="w-full bg-neutral-100 h-2 rounded-full overflow-hidden">
                  <div className="bg-op-blue h-full w-[25%]" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* 5. System Events Stream */}
      <Card>
        <CardHeader className="py-3 px-5 flex flex-row items-center justify-between">
          <CardTitle className="text-sm">Recent Operations & Solver Audit Stream</CardTitle>
          <span className="text-[11px] text-neutral-500 font-mono">Live CDC Telemetry Feed</span>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y divide-neutral-100 text-xs">
            {events.slice(0, 4).map((evt) => (
              <div key={evt.id} className="px-5 py-3 flex items-start justify-between hover:bg-neutral-50 transition-colors">
                <div className="flex items-start space-x-3">
                  {evt.level === "critical" && (
                    <AlertTriangle className="w-4 h-4 text-op-red shrink-0 mt-0.5" />
                  )}
                  {evt.level === "warning" && (
                    <AlertTriangle className="w-4 h-4 text-op-amber shrink-0 mt-0.5" />
                  )}
                  {evt.level === "info" && (
                    <CheckCircle2 className="w-4 h-4 text-op-green shrink-0 mt-0.5" />
                  )}
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-neutral-900">{evt.source || "SparkRail Core"}</span>
                      <Badge variant="neutral" size="sm" className="font-mono text-[9px]">
                        {evt.id}
                      </Badge>
                    </div>
                    <p className="text-neutral-700 mt-0.5 leading-relaxed">{evt.message}</p>
                  </div>
                </div>
                <span className="text-[11px] text-neutral-400 font-mono shrink-0 ml-4">
                  {new Date(evt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Modals */}
      <OptimizationModal
        isOpen={isOptimizeModalOpen}
        onClose={() => setIsOptimizeModalOpen(false)}
        onSuccess={() => void loadData()}
      />
      <ConflictModal
        isOpen={isConflictModalOpen}
        onClose={() => setIsConflictModalOpen(false)}
      />
    </div>
  );
}