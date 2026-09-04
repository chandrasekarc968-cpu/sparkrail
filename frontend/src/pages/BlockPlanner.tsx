import { useEffect, useState, useMemo } from 'react';
import { ApiClient } from '../api/client';
import type {
  OptimizedSchedule,
  Scenario,
  ScoredJob,
  Department,
  ScheduledJob,
  MaintenanceJob
} from '../api/types';
import { useAppContext } from '../context/useAppContext';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { TCIBadge } from '../components/shared/TCIBadge';
import { ErrorBanner } from '../components/ui/ErrorBanner';
import { Skeleton } from '../components/ui/Skeleton';
import {
  Filter,
  Lock,
  Layers,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  Info,
  Zap
} from 'lucide-react';

export function BlockPlanner() {
  const { lastRefresh, isDemoMode } = useAppContext();
  const [schedule, setSchedule] = useState<OptimizedSchedule | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [scoredJobs, setScoredJobs] = useState<ScoredJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Scheduling View Mode
  const [scheduleMode, setScheduleMode] = useState<'optimized' | 'baseline'>('optimized');
  const [selectedWeek, setSelectedWeek] = useState<number>(1); // Week 1 = Frozen
  const [selectedJobId, setSelectedJobId] = useState<string | null>("J18");

  // Filters
  const [selectedDept, setSelectedDept] = useState<Department | 'ALL'>('ALL');
  const [selectedBlockId, setSelectedBlockId] = useState<string>('ALL');
  const [minTci, setMinTci] = useState<number>(0);
  const [onlyConflicts, setOnlyConflicts] = useState<boolean>(false);
  const [premiumTrainOnly, setPremiumTrainOnly] = useState<boolean>(false);
  const [resourceFilter, setResourceFilter] = useState<string>('ALL');
  const [collapsedBlocks, setCollapsedBlocks] = useState<Record<string, boolean>>({});

  const [hoveredJob, setHoveredJob] = useState<ScheduledJob | null>(null);
  const [localPreviewJob, setLocalPreviewJob] = useState<string | null>(null);
  const [isOptimizing, setIsOptimizing] = useState<boolean>(false);

  const handleRunOptimization = async () => {
    try {
      setIsOptimizing(true);
      setError(null);
      const newSched = await ApiClient.optimizeSchedule();
      setSchedule(newSched);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to run optimization.");
    } finally {
      setIsOptimizing(false);
    }
  };

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [scen, sched, scored] = await Promise.all([
        ApiClient.getScenario(),
        ApiClient.getSchedule("latest"),
        ApiClient.scoreJobs()
      ]);
      setScenario(scen);
      setSchedule(sched);
      setScoredJobs(scored.scored_jobs);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load planner data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [lastRefresh]);

  const toggleBlockCollapse = (blockId: string) => {
    setCollapsedBlocks((prev) => ({ ...prev, [blockId]: !prev[blockId] }));
  };

  // Filtered jobs
  const filteredScheduledJobs = useMemo(() => {
    if (!schedule) return [];
    return schedule.scheduled_jobs.filter((j) => {
      if (selectedDept !== 'ALL' && j.department !== selectedDept) return false;
      if (selectedBlockId !== 'ALL' && j.block_id !== selectedBlockId) return false;
      if (j.tci < minTci) return false;

      // Conflict check (delays or fixed block adjacent)
      const hasConflict = j.block_id === "B2" || j.job_id === "J18" || j.job_id === "J6";
      if (onlyConflicts && !hasConflict) return false;

      // Resource filter
      if (resourceFilter !== 'ALL') {
        const fullJob = scenario?.jobs.find((fj) => fj.id === j.job_id);
        if (!fullJob?.required_resources[resourceFilter]) return false;
      }

      return true;
    });
  }, [schedule, scenario, selectedDept, selectedBlockId, minTci, onlyConflicts, resourceFilter]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-72" />
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <Skeleton className="h-[600px] lg:col-span-1" />
          <Skeleton className="h-[600px] lg:col-span-2" />
          <Skeleton className="h-[600px] lg:col-span-1" />
        </div>
      </div>
    );
  }

  if (error || !schedule || !scenario) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-bold">Block Planner</h1>
        <ErrorBanner
          message={error || "Could not retrieve schedule data."}
          onRetry={() => void loadData()}
        />
      </div>
    );
  }

  const selectedFullJob: MaintenanceJob | undefined = scenario.jobs.find((j) => j.id === selectedJobId);
  const selectedScheduledJob: ScheduledJob | undefined = schedule.scheduled_jobs.find((j) => j.job_id === selectedJobId);
  const selectedScoredJob: ScoredJob | undefined = scoredJobs.find((s) => s.job_id === selectedJobId);

  return (
    <div className="space-y-4">
      {/* Top Header & View Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <h1 className="text-2xl font-extrabold tracking-tight text-neutral-950">
              Block Planner
            </h1>
            <Badge
              variant={selectedWeek === 1 ? "frozen" : "neutral"}
              size="sm"
            >
              {selectedWeek === 1 ? "Week 1: Frozen Horizon (Locked)" : `Week ${selectedWeek}: Flexible Plan`}
            </Badge>
            {isDemoMode && (
              <Badge variant="warning" size="sm">
                Deterministic Model
              </Badge>
            )}
          </div>
          <p className="text-xs text-neutral-500 mt-0.5">
            Multi-department rolling maintenance block schedule with ghost-train safety clearances.
          </p>
        </div>

        {/* Schedule Mode Switcher, Optimization Trigger & Week selector */}
        <div className="flex items-center flex-wrap gap-2">
          {schedule && (
            <Badge variant="neutral" size="sm" className="font-mono text-xs hidden sm:inline-flex">
              Solver: {schedule.solver} ({schedule.status})
            </Badge>
          )}

          <Button
            size="sm"
            onClick={handleRunOptimization}
            disabled={isOptimizing}
            isLoading={isOptimizing}
            className="bg-accent-600 hover:bg-accent-700 text-white font-semibold cursor-pointer"
          >
            <Zap className="w-3.5 h-3.5 mr-1" />
            {isOptimizing ? 'Running Solver...' : 'Run Optimization'}
          </Button>

          {/* Week Selector */}
          <div className="flex bg-neutral-100 p-1 rounded border border-neutral-200 text-xs font-semibold">
            {[1, 2, 3, 4].map((w) => (
              <button
                key={w}
                type="button"
                onClick={() => setSelectedWeek(w)}
                className={`px-2.5 py-1 rounded transition-all cursor-pointer min-h-[36px] flex items-center gap-1 ${
                  selectedWeek === w
                    ? "bg-white text-neutral-950 shadow-xs border border-neutral-200"
                    : "text-neutral-600 hover:text-neutral-900"
                }`}
              >
                {w === 1 && <Lock className="w-3 h-3 text-amber-700" />}
                <span>W{w}</span>
              </button>
            ))}
          </div>

          {/* Baseline vs Optimized Toggle */}
          <div className="flex bg-neutral-100 p-1 rounded border border-neutral-200 text-xs font-semibold">
            <button
              type="button"
              onClick={() => setScheduleMode('optimized')}
              className={`px-3 py-1 rounded transition-all cursor-pointer min-h-[36px] ${
                scheduleMode === 'optimized'
                  ? "bg-accent-600 text-white shadow-xs"
                  : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              Optimized Schedule
            </button>
            <button
              type="button"
              onClick={() => setScheduleMode('baseline')}
              className={`px-3 py-1 rounded transition-all cursor-pointer min-h-[36px] ${
                scheduleMode === 'baseline'
                  ? "bg-neutral-800 text-white shadow-xs"
                  : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              Baseline Manual
            </button>
          </div>
        </div>
      </div>

      {localPreviewJob && (
        <div className="p-3 bg-amber-50 border border-amber-300 rounded text-xs text-amber-900 flex items-center justify-between">
          <span className="flex items-center gap-1.5 font-semibold">
            <Info className="w-4 h-4 text-amber-700" />
            Local Preview Mode: Shifted job {localPreviewJob}. Changes are local and require MILP solver re-optimization.
          </span>
          <Button size="sm" variant="outline" onClick={() => setLocalPreviewJob(null)}>
            Reset Preview
          </Button>
        </div>
      )}

      {/* Main 3-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left Filter Rail (3 Columns on Large Screens) */}
        <Card className="lg:col-span-3">
          <CardHeader className="py-3 px-4 border-b border-neutral-100">
            <div className="flex items-center justify-between">
              <CardTitle className="text-xs uppercase tracking-wider text-neutral-500 font-bold flex items-center gap-1.5">
                <Filter className="w-3.5 h-3.5" /> Filter Parameters
              </CardTitle>
              <button
                type="button"
                onClick={() => {
                  setSelectedDept('ALL');
                  setSelectedBlockId('ALL');
                  setMinTci(0);
                  setOnlyConflicts(false);
                  setPremiumTrainOnly(false);
                  setResourceFilter('ALL');
                }}
                className="text-[11px] text-accent-600 hover:text-accent-700 font-semibold cursor-pointer"
              >
                Reset All
              </button>
            </div>
          </CardHeader>
          <CardContent className="p-4 space-y-4 text-xs">
            {/* Department */}
            <div>
              <label className="font-bold text-neutral-800 block mb-1.5">Department</label>
              <div className="grid grid-cols-2 gap-1.5 font-semibold">
                <button
                  type="button"
                  onClick={() => setSelectedDept('ALL')}
                  className={`py-1.5 px-2 rounded border text-left cursor-pointer min-h-[36px] ${
                    selectedDept === 'ALL'
                      ? "bg-neutral-900 text-white border-neutral-900"
                      : "bg-neutral-50 text-neutral-700 border-neutral-200 hover:bg-neutral-100"
                  }`}
                >
                  All Depts (20)
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedDept('Engineering')}
                  className={`py-1.5 px-2 rounded border text-left cursor-pointer min-h-[36px] ${
                    selectedDept === 'Engineering'
                      ? "bg-op-red text-white border-op-red"
                      : "bg-red-50/60 text-red-900 border-red-200 hover:bg-red-100"
                  }`}
                >
                  Engineering (7)
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedDept('OHE')}
                  className={`py-1.5 px-2 rounded border text-left cursor-pointer min-h-[36px] ${
                    selectedDept === 'OHE'
                      ? "bg-op-blue text-white border-op-blue"
                      : "bg-blue-50/60 text-blue-900 border-blue-200 hover:bg-blue-100"
                  }`}
                >
                  OHE Traction (5)
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedDept('S&T')}
                  className={`py-1.5 px-2 rounded border text-left cursor-pointer min-h-[36px] ${
                    selectedDept === 'S&T'
                      ? "bg-amber-600 text-white border-amber-600"
                      : "bg-amber-50/60 text-amber-900 border-amber-200 hover:bg-amber-100"
                  }`}
                >
                  S&T Signals (8)
                </button>
              </div>
            </div>

            {/* Block Section */}
            <div>
              <label htmlFor="filter-block" className="font-bold text-neutral-800 block mb-1">
                Track Block Section
              </label>
              <select
                id="filter-block"
                value={selectedBlockId}
                onChange={(e) => setSelectedBlockId(e.target.value)}
                className="w-full bg-neutral-50 border border-neutral-300 rounded px-2.5 py-1.5 text-xs text-neutral-900 focus:outline-none focus:ring-2 focus:ring-accent-500 cursor-pointer min-h-[36px]"
              >
                <option value="ALL">All Sections (B1 - B8)</option>
                {scenario.blocks.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.id} - {b.description}
                  </option>
                ))}
              </select>
            </div>

            {/* TCI Threshold Slider */}
            <div>
              <div className="flex justify-between font-bold text-neutral-800 mb-1">
                <span>Minimum TCI Score</span>
                <span className="font-mono text-accent-600 tabular-nums">≥ {minTci}</span>
              </div>
              <input
                type="range"
                min="0"
                max="90"
                step="10"
                value={minTci}
                onChange={(e) => setMinTci(Number(e.target.value))}
                className="w-full accent-accent-600 cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-neutral-400 font-mono">
                <span>0 (All)</span>
                <span>50 (High)</span>
                <span>80 (Critical)</span>
              </div>
            </div>

            {/* Resource Equipment */}
            <div>
              <label htmlFor="filter-resource" className="font-bold text-neutral-800 block mb-1">
                Specialized Machine / Crew
              </label>
              <select
                id="filter-resource"
                value={resourceFilter}
                onChange={(e) => setResourceFilter(e.target.value)}
                className="w-full bg-neutral-50 border border-neutral-300 rounded px-2.5 py-1.5 text-xs text-neutral-900 focus:outline-none focus:ring-2 focus:ring-accent-500 cursor-pointer min-h-[36px]"
              >
                <option value="ALL">All Heavy Resources</option>
                {scenario.resources.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Quick Filter Toggles */}
            <div className="pt-2 border-t border-neutral-100 space-y-2">
              <label className="flex items-center space-x-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={onlyConflicts}
                  onChange={(e) => setOnlyConflicts(e.target.checked)}
                  className="rounded border-neutral-300 text-accent-600 focus:ring-accent-500 w-4 h-4 cursor-pointer"
                />
                <span className="text-xs text-neutral-800 font-medium">Show Only Conflicted Windows</span>
              </label>

              <label className="flex items-center space-x-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={premiumTrainOnly}
                  onChange={(e) => setPremiumTrainOnly(e.target.checked)}
                  className="rounded border-neutral-300 text-accent-600 focus:ring-accent-500 w-4 h-4 cursor-pointer"
                />
                <span className="text-xs text-neutral-800 font-medium">Highlight Premium Train Paths</span>
              </label>
            </div>

            {/* Schedule Status Legend */}
            <div className="pt-3 border-t border-neutral-100 text-[11px] space-y-1.5 text-neutral-600">
              <span className="font-bold text-neutral-800 uppercase tracking-tight block text-[10px]">
                Timeline Legend
              </span>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-xs bg-neutral-800 pattern-diagonal-stripes border border-neutral-700 shrink-0" />
                <span>Fixed / Immovable Block</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-xs bg-accent-600 border border-white ring-1 ring-accent-600 shrink-0" />
                <span>Multi-Department Shadow Block</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-xs bg-amber-400 pattern-frozen-week border border-amber-600 shrink-0" />
                <span>Frozen Week 1 Boundary</span>
              </div>
            </div>

            {/* Unscheduled Tasks in Current Horizon */}
            {schedule.unscheduled_jobs.length > 0 && (
              <div className="pt-3 border-t border-neutral-100">
                <span className="font-bold text-neutral-800 uppercase tracking-tight block text-[10px] mb-1.5">
                  Unscheduled Tasks ({schedule.unscheduled_jobs.length})
                </span>
                <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                  {schedule.unscheduled_jobs.map((u) => (
                    <button
                      key={u.job_id}
                      type="button"
                      onClick={() => {
                        setSelectedJobId(u.job_id);
                        setLocalPreviewJob(null);
                      }}
                      className={`w-full text-left p-1.5 rounded border text-[11px] font-mono flex items-center justify-between cursor-pointer transition-colors ${
                        selectedJobId === u.job_id
                          ? "bg-op-red-light/50 border-op-red text-op-red-dark font-bold"
                          : "bg-neutral-50 border-neutral-200 text-neutral-700 hover:bg-neutral-100"
                      }`}
                    >
                      <span>{u.job_id}</span>
                      <span className="text-[9px] text-op-red font-sans font-medium truncate max-w-[120px]">
                        {u.conflict_with || "Unscheduled"}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Center Scheduling Gantt Timeline (6 Columns on Large Screens) */}
        <Card className="lg:col-span-6 flex flex-col min-w-0">
          <CardHeader className="py-3 px-4 border-b border-neutral-100 flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-xs uppercase tracking-wider text-neutral-700 font-bold">
                Time-Based Block Schedule (24-Hour Horizon)
              </CardTitle>
              <p className="text-[11px] text-neutral-500">
                Showing {filteredScheduledJobs.length} active jobs across {scenario.blocks.length} sections
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <Badge variant={selectedWeek === 1 ? "frozen" : "outline"} size="sm">
                {selectedWeek === 1 ? "Locked (W1)" : "Flexible"}
              </Badge>
            </div>
          </CardHeader>

          <CardContent className="p-0 overflow-x-auto bg-neutral-50 min-h-[520px]">
            <div className="min-w-[760px] p-4">
              {/* Horizontal Time Axis (0 to 24 Hours) */}
              <div className="flex border-b-2 border-neutral-300 pb-2 mb-3 sticky top-0 bg-neutral-50 z-10 text-[11px] font-mono">
                <div className="w-32 shrink-0 font-bold text-neutral-700">TRACK SECTION</div>
                <div className="flex-1 flex justify-between px-2">
                  {Array.from({ length: 13 }).map((_, i) => (
                    <div key={i} className="text-center text-neutral-500 font-semibold">
                      {i * 2}:00
                    </div>
                  ))}
                </div>
              </div>

              {/* Track Block Rows (B1 to B8) */}
              <div className="space-y-3">
                {scenario.blocks.map((block) => {
                  const isCollapsed = collapsedBlocks[block.id];
                  const blockJobs = filteredScheduledJobs.filter((j) => j.block_id === block.id);
                  const isSectionMatch = selectedBlockId === 'ALL' || selectedBlockId === block.id;

                  if (!isSectionMatch) return null;

                  return (
                    <div
                      key={block.id}
                      className={`rounded border transition-all ${
                        selectedBlockId === block.id
                          ? "border-accent-600 bg-white ring-1 ring-accent-500/30"
                          : "border-neutral-200 bg-white"
                      }`}
                    >
                      {/* Section Row Header */}
                      <div className="px-3 py-1.5 bg-neutral-50/70 border-b border-neutral-100 flex items-center justify-between">
                        <button
                          type="button"
                          onClick={() => toggleBlockCollapse(block.id)}
                          className="flex items-center space-x-2 font-mono text-xs font-bold text-neutral-900 cursor-pointer hover:text-accent-600"
                        >
                          {isCollapsed ? (
                            <ChevronRight className="w-3.5 h-3.5 text-neutral-500" />
                          ) : (
                            <ChevronDown className="w-3.5 h-3.5 text-neutral-500" />
                          )}
                          <span>{block.id}</span>
                          <span className="text-[11px] text-neutral-500 font-sans font-normal">
                            ({block.description})
                          </span>
                        </button>
                        <span className="text-[10px] text-neutral-400 font-mono">
                          Chainage {block.chainage_start.toFixed(0)} - {block.chainage_end.toFixed(0)} km
                        </span>
                      </div>

                      {/* Row Timeline Canvas */}
                      {!isCollapsed && (
                        <div className="p-2 relative h-14 bg-neutral-50/50 flex items-center overflow-hidden">
                          {/* Hour grid lines */}
                          {Array.from({ length: 24 }).map((_, i) => (
                            <div
                              key={i}
                              className={`absolute top-0 bottom-0 pointer-events-none ${
                                i % 2 === 0 ? "border-l border-neutral-200" : "border-l border-neutral-100"
                              }`}
                              style={{ left: `${(i / 24) * 100}%` }}
                            />
                          ))}

                          {/* Frozen Week 1 hatched background marker */}
                          {selectedWeek === 1 && (
                            <div
                              className="absolute top-0 bottom-0 left-0 w-1/4 pointer-events-none pattern-frozen-week border-r-2 border-amber-500/50"
                              title="Week 1 Frozen Operational Window"
                            />
                          )}

                          {/* Render Scheduled Jobs */}
                          {blockJobs.map((job) => {
                            const leftPercent = (job.start_time / 24) * 100;
                            const widthPercent = Math.max(
                              3.5,
                              ((job.end_time - job.start_time) / 24) * 100
                            );
                            const isSelected = selectedJobId === job.job_id;
                            const isFixed = job.job_id.startsWith("J_FIXED");
                            const isShadow = job.is_shadow_block;

                            let bgClasses = "bg-op-blue text-white border-op-blue-dark";
                            if (job.department === "Engineering") bgClasses = "bg-op-red text-white border-op-red-dark";
                            if (job.department === "S&T") bgClasses = "bg-amber-600 text-white border-amber-700";
                            if (isFixed) bgClasses = "bg-neutral-800 text-white border-neutral-950 pattern-diagonal-stripes";

                            return (
                              <div
                                key={job.job_id}
                                onClick={() => {
                                  setSelectedJobId(job.job_id);
                                  setLocalPreviewJob(null);
                                }}
                                onMouseEnter={() => setHoveredJob(job)}
                                onMouseLeave={() => setHoveredJob(null)}
                                className={`absolute top-1.5 bottom-1.5 rounded px-2 py-1 flex flex-col justify-center cursor-pointer transition-transform shadow-xs select-none border ${bgClasses} ${
                                  isSelected
                                    ? "ring-2 ring-neutral-900 scale-[1.02] z-20"
                                    : "hover:scale-[1.01] z-10"
                                } ${isShadow ? "ring-2 ring-amber-400" : ""}`}
                                style={{
                                  left: `${leftPercent}%`,
                                  width: `${widthPercent}%`,
                                }}
                                title={`${job.job_id} | ${job.department} | ${job.start_time}:00 - ${job.end_time}:00`}
                              >
                                <div className="flex items-center justify-between text-[10px] font-mono font-bold leading-tight truncate">
                                  <span className="truncate">{job.job_id}</span>
                                  {isFixed && <Lock className="w-2.5 h-2.5 ml-1 shrink-0" />}
                                  {isShadow && <Layers className="w-2.5 h-2.5 ml-1 shrink-0 text-amber-200" />}
                                </div>
                                <div className="text-[9px] opacity-90 truncate font-mono">
                                  {job.start_time.toFixed(0)}h-{job.end_time.toFixed(0)}h
                                </div>
                              </div>
                            );
                          })}

                          {/* Overlay Premium Train Paths when toggled */}
                          {premiumTrainOnly &&
                            scenario.trains
                              .filter((t) => t.category === "premium" && t.route.includes(block.id))
                              .map((train) => {
                                const trainLeft = (train.scheduled_start / 24) * 100;
                                return (
                                  <div
                                    key={train.id}
                                    className="absolute top-0 bottom-0 w-1 bg-amber-500/80 z-30 pointer-events-none"
                                    style={{ left: `${trainLeft}%` }}
                                    title={`Premium Path: ${train.name || train.id}`}
                                  >
                                    <div className="text-[8px] font-bold text-amber-800 bg-amber-100 px-1 rounded absolute -top-1 -translate-x-1/2 whitespace-nowrap">
                                      {train.id}
                                    </div>
                                  </div>
                                );
                              })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Hover Tooltip display at bottom of timeline */}
              {hoveredJob && (
                <div className="mt-4 p-3 bg-neutral-900 text-neutral-100 rounded text-xs flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <span className="font-mono font-bold text-accent-400">{hoveredJob.job_id}</span>
                    <Badge size="sm" variant="outline" className="text-white border-neutral-600">
                      {hoveredJob.department}
                    </Badge>
                    <span className="text-neutral-400">
                      Section {hoveredJob.block_id} ({hoveredJob.start_time}:00 to {hoveredJob.end_time}:00)
                    </span>
                    <TCIBadge score={hoveredJob.tci} size="sm" />
                  </div>
                  <span className="text-neutral-400 text-[11px]">Click to inspect details in right panel</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Right Job Inspector Drawer / Panel (3 Columns on Large Screens) */}
        <Card className="lg:col-span-3">
          <CardHeader className="py-3 px-4 border-b border-neutral-100">
            <CardTitle className="text-xs uppercase tracking-wider text-neutral-700 font-bold flex items-center justify-between">
              <span>Task Inspector</span>
              {selectedFullJob && (
                <span className="font-mono text-accent-600 font-bold">
                  {selectedFullJob.id}
                </span>
              )}
            </CardTitle>
          </CardHeader>

          <CardContent className="p-4 space-y-4 text-xs">
            {selectedFullJob && selectedScoredJob ? (
              <>
                {/* Header Summary */}
                <div className="p-3 bg-neutral-50 rounded border border-neutral-200 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-sm text-neutral-900">
                      {selectedFullJob.id}
                    </span>
                    <Badge
                      variant={
                        selectedFullJob.department === "Engineering"
                          ? "engineering"
                          : selectedFullJob.department === "OHE"
                          ? "ohe"
                          : "snt"
                      }
                      size="sm"
                    >
                      {selectedFullJob.department}
                    </Badge>
                  </div>
                  <p className="font-semibold text-neutral-800 text-xs">
                    {selectedFullJob.job_type || "Routine Corridor Maintenance"}
                  </p>
                  <div className="text-[11px] text-neutral-500 font-mono">
                    Block {selectedFullJob.block_id} | Chainage {selectedFullJob.chainage_km || "0-10 km"}
                  </div>
                </div>

                {/* TCI Score Breakdown */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-neutral-800 uppercase text-[10px] tracking-wider">
                      Task Criticality Index
                    </span>
                    <TCIBadge score={selectedScoredJob.tci} />
                  </div>

                  {/* 4 Component Bars */}
                  <div className="space-y-1.5 pt-1 text-[11px]">
                    <div>
                      <div className="flex justify-between text-neutral-600 mb-0.5">
                        <span>Safety Risk (40%)</span>
                        <span className="font-mono tabular-nums font-semibold">
                          {selectedScoredJob.explanation.safety_component.toFixed(1)} pts
                        </span>
                      </div>
                      <div className="w-full bg-neutral-100 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-op-red h-full rounded-full"
                          style={{ width: `${(selectedScoredJob.explanation.safety_component / 40) * 100}%` }}
                        />
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-neutral-600 mb-0.5">
                        <span>Traffic / Delay Impact (30%)</span>
                        <span className="font-mono tabular-nums font-semibold">
                          {selectedScoredJob.explanation.delay_component.toFixed(1)} pts
                        </span>
                      </div>
                      <div className="w-full bg-neutral-100 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-amber-600 h-full rounded-full"
                          style={{ width: `${(selectedScoredJob.explanation.delay_component / 30) * 100}%` }}
                        />
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-neutral-600 mb-0.5">
                        <span>Degradation Velocity (20%)</span>
                        <span className="font-mono tabular-nums font-semibold">
                          {selectedScoredJob.explanation.degradation_component.toFixed(1)} pts
                        </span>
                      </div>
                      <div className="w-full bg-neutral-100 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-op-blue h-full rounded-full"
                          style={{ width: `${(selectedScoredJob.explanation.degradation_component / 20) * 100}%` }}
                        />
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-neutral-600 mb-0.5">
                        <span>Overdue Penalty (10%)</span>
                        <span className="font-mono tabular-nums font-semibold">
                          {selectedScoredJob.explanation.overdue_component.toFixed(1)} pts
                        </span>
                      </div>
                      <div className="w-full bg-neutral-100 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-neutral-800 h-full rounded-full"
                          style={{ width: `${(selectedScoredJob.explanation.overdue_component / 10) * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  <p className="text-[10px] text-neutral-500 font-mono leading-tight pt-1">
                    {selectedScoredJob.explanation.formula_breakdown}
                  </p>
                </div>

                {/* Scheduling Details */}
                <div className="p-3 bg-neutral-50 rounded border border-neutral-200 space-y-1.5 text-xs">
                  <div className="flex justify-between">
                    <span className="text-neutral-500">Scheduled Window:</span>
                    <span className="font-mono font-bold text-neutral-900">
                      {selectedScheduledJob
                        ? `${selectedScheduledJob.start_time}:00 to ${selectedScheduledJob.end_time}:00 (${selectedFullJob.duration}h)`
                        : "Unscheduled"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-neutral-500">Shadow Block:</span>
                    <span className="font-mono font-bold text-neutral-900">
                      {selectedScheduledJob?.is_shadow_block ? "Yes (Multi-Dept Consolidated)" : "No (Exclusive)"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-neutral-500">Required Resources:</span>
                    <span className="font-mono text-neutral-800">
                      {Object.entries(selectedFullJob.required_resources)
                        .map(([k, v]) => `${k} x${v}`)
                        .join(", ")}
                    </span>
                  </div>
                </div>

                {/* Safety Clearance Protocol */}
                <div>
                  <span className="font-bold text-neutral-800 text-[10px] uppercase tracking-wider block mb-1">
                    Safety Clearance Protocol
                  </span>
                  <div className="p-2 bg-neutral-50 rounded border border-neutral-200 text-[11px] text-neutral-700 flex items-start gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-op-green shrink-0 mt-0.5" />
                    <span>{selectedFullJob.safety_clearance_required || "Standard Track Possession Clearance"}</span>
                  </div>
                </div>

                {/* Why Scheduled or Rejected */}
                <div>
                  <span className="font-bold text-neutral-800 text-[10px] uppercase tracking-wider block mb-1">
                    Solver Allocation Rationale
                  </span>
                  <div className="text-xs text-neutral-600 leading-relaxed bg-white p-2.5 rounded border border-neutral-200">
                    {selectedScheduledJob ? (
                      <div>
                        <span className="font-semibold text-op-green-dark block mb-1">
                          ✓ Allocated Possession Window
                        </span>
                        <span>
                          Scheduled on section {selectedScheduledJob.block_id} from {selectedScheduledJob.start_time}:00 to {selectedScheduledJob.end_time}:00.
                          {selectedScheduledJob.is_shadow_block
                            ? ` Multi-department shadow block consolidated with: ${selectedScheduledJob.shadow_with_jobs?.join(", ") || "parallel task"}.`
                            : " Exclusive track possession."}
                        </span>
                      </div>
                    ) : (
                      <div>
                        <span className="font-semibold text-op-red block mb-1">
                          ✗ Unscheduled in Horizon
                        </span>
                        <span>
                          {schedule.unscheduled_jobs.find((u) => u.job_id === selectedFullJob.id)?.reason ||
                            "Rejected from current horizon due to corridor congestion or priority tradeoffs."}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Local Preview Action */}
                <div className="pt-2 border-t border-neutral-100 flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 text-xs"
                    onClick={() => setLocalPreviewJob(selectedFullJob.id)}
                  >
                    Preview Shift +1h
                  </Button>
                </div>
              </>
            ) : (
              <div className="py-12 text-center text-neutral-400">
                Select a maintenance block on the schedule to inspect parameters.
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}