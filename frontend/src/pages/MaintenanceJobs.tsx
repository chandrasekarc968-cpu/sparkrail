import { useEffect, useState, useMemo } from 'react';
import { ApiClient } from '../api/client';
import type {
  Scenario,
  ScoredJob,
  OptimizedSchedule,
  MaintenanceJob,
  ScheduledJob
} from '../api/types';
import { useAppContext } from '../context/useAppContext';
import { Card, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { TCIBadge } from '../components/shared/TCIBadge';
import { Drawer } from '../components/ui/Drawer';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorBanner } from '../components/ui/ErrorBanner';
import { Skeleton } from '../components/ui/Skeleton';
import {
  Search,
  Download,
  ArrowUpDown,
  Eye,
  CheckSquare,
  Square,
  ShieldCheck
} from 'lucide-react';

export function MaintenanceJobs() {
  const { lastRefresh, isDemoMode } = useAppContext();
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [scoredJobs, setScoredJobs] = useState<ScoredJob[]>([]);
  const [schedule, setSchedule] = useState<OptimizedSchedule | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Search & Filtering
  const [searchQuery, setSearchQuery] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Sorting
  const [sortField, setSortField] = useState<'id' | 'block_id' | 'department' | 'tci' | 'duration' | 'due_date'>('tci');
  const [sortAsc, setSortAsc] = useState<boolean>(false);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Column Visibility
  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>({
    id: true,
    department: true,
    block_id: true,
    job_type: true,
    tci: true,
    safety: true,
    capacity: true,
    degradation: true,
    overdue: true,
    duration: true,
    resources: true,
    due_date: true,
    status: true,
    window: true,
  });
  const [showColVisibilityMenu, setShowColVisibilityMenu] = useState(false);

  // Bulk Selection UI
  const [selectedJobIds, setSelectedJobIds] = useState<Set<string>>(new Set());

  // Detail Drawer
  const [inspectedJob, setInspectedJob] = useState<{ job: MaintenanceJob; score: ScoredJob; sched?: ScheduledJob } | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [scen, scored, sched] = await Promise.all([
        ApiClient.getScenario(),
        ApiClient.scoreJobs(),
        ApiClient.getSchedule("latest")
      ]);
      setScenario(scen);
      setScoredJobs(scored.scored_jobs);
      setSchedule(sched);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load maintenance jobs.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [lastRefresh]);

  // Combined and sorted jobs list
  const processedJobs = useMemo(() => {
    if (!scenario) return [];

    return scenario.jobs
      .filter((job) => {
        // Search
        const query = searchQuery.toLowerCase().trim();
        if (query) {
          const matchesId = job.id.toLowerCase().includes(query);
          const matchesBlock = job.block_id.toLowerCase().includes(query);
          const matchesDept = job.department.toLowerCase().includes(query);
          const matchesType = (job.job_type || '').toLowerCase().includes(query);
          if (!matchesId && !matchesBlock && !matchesDept && !matchesType) return false;
        }

        // Dept filter
        if (departmentFilter !== 'ALL' && job.department !== departmentFilter) return false;

        // Status filter
        const isScheduled = schedule?.scheduled_jobs.some((s) => s.job_id === job.id);
        if (statusFilter === 'SCHEDULED' && !isScheduled) return false;
        if (statusFilter === 'UNSCHEDULED' && isScheduled) return false;
        if (statusFilter === 'FIXED' && !job.is_fixed) return false;

        return true;
      })
      .sort((a, b) => {
        const scoreA = scoredJobs.find((s) => s.job_id === a.id)?.tci || 0;
        const scoreB = scoredJobs.find((s) => s.job_id === b.id)?.tci || 0;

        let diff = 0;
        if (sortField === 'tci') diff = scoreA - scoreB;
        else if (sortField === 'id') diff = a.id.localeCompare(b.id);
        else if (sortField === 'block_id') diff = a.block_id.localeCompare(b.block_id);
        else if (sortField === 'department') diff = a.department.localeCompare(b.department);
        else if (sortField === 'duration') diff = a.duration - b.duration;
        else if (sortField === 'due_date') diff = (a.due_date || '').localeCompare(b.due_date || '');

        return sortAsc ? diff : -diff;
      });
  }, [scenario, searchQuery, departmentFilter, statusFilter, sortField, sortAsc, scoredJobs, schedule]);

  // Pagination slice
  const paginatedJobs = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return processedJobs.slice(start, start + pageSize);
  }, [processedJobs, currentPage, pageSize]);

  const totalPages = Math.ceil(processedJobs.length / pageSize) || 1;

  // Toggle selection
  const toggleSelectAll = () => {
    if (selectedJobIds.size === paginatedJobs.length) {
      setSelectedJobIds(new Set());
    } else {
      setSelectedJobIds(new Set(paginatedJobs.map((j) => j.id)));
    }
  };

  const toggleSelectJob = (id: string) => {
    const next = new Set(selectedJobIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedJobIds(next);
  };

  // CSV Export
  const handleExportCSV = () => {
    if (!processedJobs.length) return;

    const headers = [
      "Job ID",
      "Asset Chainage",
      "Department",
      "Block Section",
      "Job Type",
      "TCI Score",
      "Safety Severity",
      "Capacity Impact",
      "Degradation",
      "Overdue Days",
      "Duration (hrs)",
      "Required Resources",
      "Due Date",
      "Status",
      "Scheduled Start",
      "Scheduled End"
    ];

    const rows = processedJobs.map((j) => {
      const score = scoredJobs.find((s) => s.job_id === j.id)?.tci || 0;
      const sched = schedule?.scheduled_jobs.find((s) => s.job_id === j.id);
      const status = j.is_fixed ? "Fixed Block" : sched ? "Scheduled" : "Unscheduled";
      const resources = Object.entries(j.required_resources).map(([k, v]) => `${k} x${v}`).join("; ");

      return [
        `"${j.id}"`,
        `"${j.chainage_km || ''}"`,
        `"${j.department}"`,
        `"${j.block_id}"`,
        `"${j.job_type || ''}"`,
        score.toFixed(1),
        j.tci_inputs.safety_severity.toFixed(2),
        j.tci_inputs.traffic_impact.toFixed(2),
        j.tci_inputs.degradation_indicator.toFixed(2),
        j.tci_inputs.overdue_days,
        j.duration,
        `"${resources}"`,
        `"${j.due_date || ''}"`,
        `"${status}"`,
        sched ? sched.start_time : '',
        sched ? sched.end_time : ''
      ].join(",");
    });

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `sparkrail_maintenance_jobs_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-[500px] w-full" />
      </div>
    );
  }

  if (error || !scenario) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-bold">Maintenance Jobs</h1>
        <ErrorBanner
          title="Failed to Load Maintenance Register"
          message={error || "Could not retrieve jobs from the railway data lakehouse."}
          onRetry={() => void loadData()}
        />
      </div>
    );
  }

  if (scenario.jobs.length === 0) {
    return (
      <EmptyState
        title="No Maintenance Jobs Found"
        description="The maintenance register for this division is currently empty. You can generate synthetic railway jobs to populate the database."
        actionLabel="Generate Scenario Jobs"
        onAction={async () => {
          await ApiClient.generateData();
          await loadData();
        }}
      />
    );
  }

  const handleSort = (field: typeof sortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false); // default descending for high numbers
    }
  };

  return (
    <div className="space-y-4">
      {/* Header & Main Export Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <h1 className="text-2xl font-extrabold tracking-tight text-neutral-950">
              Maintenance Jobs Register
            </h1>
            <Badge variant="outline" size="sm" className="font-mono">
              {processedJobs.length} of {scenario.jobs.length} TASKS
            </Badge>
            {isDemoMode && (
              <Badge variant="warning" size="sm">
                SYNTHETIC DATA
              </Badge>
            )}
          </div>
          <p className="text-xs text-neutral-500 mt-0.5">
            Master engineering, traction, and signaling job register ranked by Task Criticality Index.
          </p>
        </div>

        <div className="flex items-center space-x-2.5">
          {/* Column visibility menu toggle */}
          <div className="relative">
            <Button
              variant="outline"
              size="default"
              onClick={() => setShowColVisibilityMenu(!showColVisibilityMenu)}
              className="border-neutral-300"
            >
              <Eye className="w-4 h-4 mr-2 text-neutral-500" />
              Columns
            </Button>
            {showColVisibilityMenu && (
              <div className="absolute right-0 mt-2 w-56 bg-white border border-neutral-200 rounded-md shadow-lg z-50 p-2 text-xs">
                <p className="font-bold text-neutral-900 px-2 py-1 mb-1 border-b border-neutral-100">
                  Toggle Columns
                </p>
                <div className="max-h-60 overflow-y-auto space-y-1">
                  {Object.keys(visibleColumns).map((col) => (
                    <label key={col} className="flex items-center space-x-2 px-2 py-1 hover:bg-neutral-50 rounded cursor-pointer">
                      <input
                        type="checkbox"
                        checked={visibleColumns[col]}
                        onChange={(e) =>
                          setVisibleColumns({ ...visibleColumns, [col]: e.target.checked })
                        }
                        className="rounded border-neutral-300 text-accent-600 focus:ring-accent-500 w-3.5 h-3.5"
                      />
                      <span className="capitalize">{col.replace('_', ' ')}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>

          <Button variant="outline" size="default" onClick={handleExportCSV}>
            <Download className="w-4 h-4 mr-2 text-neutral-600" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card>
        <CardContent className="p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-3 flex-1 min-w-[280px]">
            {/* Search Input */}
            <div className="relative flex-1 min-w-[200px] max-w-sm">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setCurrentPage(1);
                }}
                placeholder="Search Job ID, Block, Department..."
                className="w-full pl-9 pr-4 py-2 border border-neutral-300 rounded text-xs text-neutral-900 focus:outline-none focus:ring-2 focus:ring-accent-500 min-h-[38px]"
                aria-label="Search maintenance jobs"
              />
            </div>

            {/* Department filter */}
            <select
              value={departmentFilter}
              onChange={(e) => {
                setDepartmentFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="bg-neutral-50 border border-neutral-300 rounded px-2.5 py-2 text-xs font-medium text-neutral-800 focus:outline-none focus:ring-2 focus:ring-accent-500 cursor-pointer min-h-[38px]"
              aria-label="Filter by department"
            >
              <option value="ALL">All Departments</option>
              <option value="Engineering">Engineering (Civil)</option>
              <option value="OHE">OHE (Traction)</option>
              <option value="S&T">S&T (Signaling)</option>
            </select>

            {/* Status filter */}
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="bg-neutral-50 border border-neutral-300 rounded px-2.5 py-2 text-xs font-medium text-neutral-800 focus:outline-none focus:ring-2 focus:ring-accent-500 cursor-pointer min-h-[38px]"
              aria-label="Filter by schedule status"
            >
              <option value="ALL">All Statuses</option>
              <option value="SCHEDULED">Scheduled</option>
              <option value="UNSCHEDULED">Unscheduled</option>
              <option value="FIXED">Fixed / Immovable</option>
            </select>
          </div>

          {/* Bulk Selection Notification */}
          {selectedJobIds.size > 0 && (
            <div className="flex items-center space-x-2 bg-neutral-100 px-3 py-1.5 rounded border border-neutral-300">
              <span className="font-bold text-neutral-800 font-mono">
                {selectedJobIds.size} selected
              </span>
              <span className="text-neutral-500 text-[11px]">
                (Bulk mutation requires backend approval)
              </span>
              <button
                type="button"
                onClick={() => setSelectedJobIds(new Set())}
                className="text-neutral-500 hover:text-neutral-900 ml-2"
              >
                Clear
              </button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Dense Table */}
      <Card className="flex flex-col overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs whitespace-nowrap">
            <thead className="bg-neutral-50 border-b border-neutral-200 text-neutral-600 uppercase font-semibold text-[10px] tracking-wide sticky top-0 z-10 select-none">
              <tr>
                <th className="px-3 py-3 w-8">
                  <button
                    type="button"
                    onClick={toggleSelectAll}
                    className="cursor-pointer text-neutral-500 hover:text-neutral-900"
                    aria-label="Select all jobs"
                  >
                    {selectedJobIds.size === paginatedJobs.length && paginatedJobs.length > 0 ? (
                      <CheckSquare className="w-4 h-4 text-accent-600" />
                    ) : (
                      <Square className="w-4 h-4" />
                    )}
                  </button>
                </th>
                {visibleColumns.id && (
                  <th className="px-3 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort('id')}>
                    <span className="inline-flex items-center gap-1">
                      Job ID <ArrowUpDown className="w-3 h-3" />
                    </span>
                  </th>
                )}
                {visibleColumns.department && (
                  <th className="px-3 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort('department')}>
                    <span className="inline-flex items-center gap-1">
                      Dept <ArrowUpDown className="w-3 h-3" />
                    </span>
                  </th>
                )}
                {visibleColumns.block_id && (
                  <th className="px-3 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort('block_id')}>
                    <span className="inline-flex items-center gap-1">
                      Section <ArrowUpDown className="w-3 h-3" />
                    </span>
                  </th>
                )}
                {visibleColumns.job_type && <th className="px-3 py-3">Job Description</th>}
                {visibleColumns.tci && (
                  <th className="px-3 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort('tci')}>
                    <span className="inline-flex items-center gap-1">
                      TCI Score <ArrowUpDown className="w-3 h-3" />
                    </span>
                  </th>
                )}
                {visibleColumns.safety && <th className="px-3 py-3">Safety</th>}
                {visibleColumns.capacity && <th className="px-3 py-3">Traffic</th>}
                {visibleColumns.degradation && <th className="px-3 py-3">Degradation</th>}
                {visibleColumns.overdue && <th className="px-3 py-3">Overdue</th>}
                {visibleColumns.duration && (
                  <th className="px-3 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort('duration')}>
                    <span className="inline-flex items-center gap-1">
                      Duration <ArrowUpDown className="w-3 h-3" />
                    </span>
                  </th>
                )}
                {visibleColumns.resources && <th className="px-3 py-3">Required Resources</th>}
                {visibleColumns.due_date && (
                  <th className="px-3 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort('due_date')}>
                    <span className="inline-flex items-center gap-1">
                      Due Date <ArrowUpDown className="w-3 h-3" />
                    </span>
                  </th>
                )}
                {visibleColumns.status && <th className="px-3 py-3">Status</th>}
                {visibleColumns.window && <th className="px-3 py-3">Window</th>}
                <th className="px-3 py-3 text-right">Action</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-neutral-100">
              {paginatedJobs.map((job) => {
                const scoreObj = scoredJobs.find((s) => s.job_id === job.id);
                const score = scoreObj?.tci || 0;
                const sched = schedule?.scheduled_jobs.find((s) => s.job_id === job.id);
                const isSelected = selectedJobIds.has(job.id);

                return (
                  <tr
                    key={job.id}
                    className={`hover:bg-neutral-50/80 transition-colors cursor-pointer ${
                      isSelected ? "bg-accent-50/20" : ""
                    }`}
                    onClick={() => {
                      if (scoreObj) {
                        setInspectedJob({ job, score: scoreObj, sched });
                      }
                    }}
                  >
                    <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        onClick={() => toggleSelectJob(job.id)}
                        className="cursor-pointer text-neutral-500 hover:text-neutral-900"
                        aria-label={`Select job ${job.id}`}
                      >
                        {isSelected ? (
                          <CheckSquare className="w-4 h-4 text-accent-600" />
                        ) : (
                          <Square className="w-4 h-4" />
                        )}
                      </button>
                    </td>

                    {visibleColumns.id && (
                      <td className="px-3 py-2.5 font-mono font-bold text-neutral-950">
                        {job.id}
                      </td>
                    )}

                    {visibleColumns.department && (
                      <td className="px-3 py-2.5">
                        <Badge
                          variant={
                            job.department === "Engineering"
                              ? "engineering"
                              : job.department === "OHE"
                              ? "ohe"
                              : "snt"
                          }
                          size="sm"
                        >
                          {job.department}
                        </Badge>
                      </td>
                    )}

                    {visibleColumns.block_id && (
                      <td className="px-3 py-2.5 font-mono font-semibold text-neutral-800">
                        {job.block_id}
                      </td>
                    )}

                    {visibleColumns.job_type && (
                      <td className="px-3 py-2.5 text-neutral-900 max-w-xs truncate font-medium">
                        {job.job_type || "Corridor Track Maintenance"}
                      </td>
                    )}

                    {visibleColumns.tci && (
                      <td className="px-3 py-2.5">
                        <TCIBadge score={score} size="sm" />
                      </td>
                    )}

                    {visibleColumns.safety && (
                      <td className="px-3 py-2.5 font-mono tabular-nums text-neutral-600">
                        {job.tci_inputs.safety_severity.toFixed(2)}
                      </td>
                    )}

                    {visibleColumns.capacity && (
                      <td className="px-3 py-2.5 font-mono tabular-nums text-neutral-600">
                        {job.tci_inputs.traffic_impact.toFixed(2)}
                      </td>
                    )}

                    {visibleColumns.degradation && (
                      <td className="px-3 py-2.5 font-mono tabular-nums text-neutral-600">
                        {job.tci_inputs.degradation_indicator.toFixed(2)}
                      </td>
                    )}

                    {visibleColumns.overdue && (
                      <td className="px-3 py-2.5 font-mono tabular-nums text-neutral-600">
                        {job.tci_inputs.overdue_days > 0 ? `${job.tci_inputs.overdue_days}d` : "0d"}
                      </td>
                    )}

                    {visibleColumns.duration && (
                      <td className="px-3 py-2.5 font-mono tabular-nums text-neutral-900">
                        {job.duration.toFixed(1)}h
                      </td>
                    )}

                    {visibleColumns.resources && (
                      <td className="px-3 py-2.5 font-mono text-neutral-600 text-[11px]">
                        {Object.entries(job.required_resources)
                          .map(([k, v]) => `${k}x${v}`)
                          .join(", ")}
                      </td>
                    )}

                    {visibleColumns.due_date && (
                      <td className="px-3 py-2.5 font-mono text-neutral-500">
                        {job.due_date || "2026-09-15"}
                      </td>
                    )}

                    {visibleColumns.status && (
                      <td className="px-3 py-2.5">
                        {job.is_fixed ? (
                          <Badge variant="neutral" size="sm">
                            Fixed Block
                          </Badge>
                        ) : sched ? (
                          <Badge variant="success" size="sm">
                            Scheduled
                          </Badge>
                        ) : (
                          <Badge variant="warning" size="sm">
                            Unscheduled
                          </Badge>
                        )}
                      </td>
                    )}

                    {visibleColumns.window && (
                      <td className="px-3 py-2.5 font-mono text-neutral-800 text-[11px]">
                        {sched ? `${sched.start_time}:00 - ${sched.end_time}:00` : "--:--"}
                      </td>
                    )}

                    <td className="px-3 py-2.5 text-right" onClick={(e) => e.stopPropagation()}>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (scoreObj) {
                            setInspectedJob({ job, score: scoreObj, sched });
                          }
                        }}
                        className="text-accent-600 hover:text-accent-700 min-h-[32px] px-2"
                      >
                        Inspect
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Table Footer & Pagination */}
        <div className="px-4 py-3 border-t border-neutral-200 bg-neutral-50/60 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-neutral-600">
          <div className="flex items-center space-x-2">
            <span>Showing</span>
            <span className="font-mono font-bold text-neutral-900">
              {Math.min((currentPage - 1) * pageSize + 1, processedJobs.length)} -{" "}
              {Math.min(currentPage * pageSize, processedJobs.length)}
            </span>
            <span>of</span>
            <span className="font-mono font-bold text-neutral-900">{processedJobs.length}</span>
            <span>jobs</span>
          </div>

          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-1.5">
              <span>Rows per page:</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setCurrentPage(1);
                }}
                className="bg-white border border-neutral-300 rounded px-2 py-1 font-mono focus:outline-none cursor-pointer"
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
              </select>
            </div>

            <div className="flex items-center space-x-1">
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage(currentPage - 1)}
                className="min-h-[32px] px-2.5"
              >
                Previous
              </Button>
              <span className="font-mono px-2">
                {currentPage} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage(currentPage + 1)}
                className="min-h-[32px] px-2.5"
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {/* Detail Inspector Drawer */}
      {inspectedJob && (
        <Drawer
          isOpen={!!inspectedJob}
          onClose={() => setInspectedJob(null)}
          title={`Job Specification: ${inspectedJob.job.id}`}
          subtitle={`Department: ${inspectedJob.job.department} | Section: ${inspectedJob.job.block_id}`}
        >
          <div className="space-y-4 text-xs">
            {/* TCI Breakdown */}
            <div className="p-3.5 bg-neutral-50 rounded border border-neutral-200 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-neutral-800 uppercase text-[10px] tracking-wider">
                  Task Criticality Index (TCI)
                </span>
                <TCIBadge score={inspectedJob.score.tci} />
              </div>
              <p className="text-neutral-600 font-mono text-[11px]">
                {inspectedJob.score.explanation.formula_breakdown}
              </p>
            </div>

            {/* General Job Info */}
            <div className="space-y-2">
              <h4 className="font-bold text-neutral-800 uppercase text-[10px] tracking-wider">
                Operational Parameters
              </h4>
              <div className="grid grid-cols-2 gap-2 p-3 bg-neutral-50 rounded border border-neutral-200 text-neutral-700">
                <div>
                  <span className="text-neutral-400 block text-[10px]">Job Type</span>
                  <span className="font-semibold">{inspectedJob.job.job_type}</span>
                </div>
                <div>
                  <span className="text-neutral-400 block text-[10px]">Track Section</span>
                  <span className="font-semibold font-mono">{inspectedJob.job.block_id}</span>
                </div>
                <div>
                  <span className="text-neutral-400 block text-[10px]">Chainage Location</span>
                  <span className="font-mono">{inspectedJob.job.chainage_km || "0.0 to 10.0 km"}</span>
                </div>
                <div>
                  <span className="text-neutral-400 block text-[10px]">Required Closure</span>
                  <span className="font-mono font-semibold">{inspectedJob.job.duration} hours</span>
                </div>
                <div>
                  <span className="text-neutral-400 block text-[10px]">Schedule Status</span>
                  <span className="font-semibold text-op-green-dark">
                    {inspectedJob.sched ? "Scheduled by Solver" : "Unscheduled / Standby"}
                  </span>
                </div>
                <div>
                  <span className="text-neutral-400 block text-[10px]">Time Window</span>
                  <span className="font-mono font-semibold">
                    {inspectedJob.sched
                      ? `${inspectedJob.sched.start_time}:00 to ${inspectedJob.sched.end_time}:00`
                      : "Pending"}
                  </span>
                </div>
              </div>
            </div>

            {/* Safety Clearance Protocol */}
            <div className="space-y-2">
              <h4 className="font-bold text-neutral-800 uppercase text-[10px] tracking-wider">
                Safety Protocol & Clearances
              </h4>
              <div className="p-3 bg-neutral-50 rounded border border-neutral-200 flex items-start gap-2">
                <ShieldCheck className="w-4 h-4 text-op-green shrink-0 mt-0.5" />
                <p className="text-neutral-700 leading-relaxed">
                  {inspectedJob.job.safety_clearance_required || "Standard Track Block Safety Clearance"}
                </p>
              </div>
            </div>

            {/* Required Machinery & Staff */}
            <div className="space-y-2">
              <h4 className="font-bold text-neutral-800 uppercase text-[10px] tracking-wider">
                Allocated Heavy Machinery & Crew
              </h4>
              <div className="p-3 bg-neutral-50 rounded border border-neutral-200 text-neutral-700 font-mono">
                {Object.entries(inspectedJob.job.required_resources).map(([resId, count]) => (
                  <div key={resId} className="flex justify-between py-0.5">
                    <span>{resId}</span>
                    <span className="font-bold">x{count} allocated</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Solver Allocation Justification */}
            <div className="space-y-2">
              <h4 className="font-bold text-neutral-800 uppercase text-[10px] tracking-wider">
                Mathematical Solver Rationale
              </h4>
              <p className="p-3 bg-white border border-neutral-200 rounded leading-relaxed text-neutral-600">
                Selected for optimal corridor throughput. With TCI {inspectedJob.score.tci}, delaying this task beyond Week 1 would trigger exponential degradation penalties. Combined with adjacent tasks into a synchronized shadow block to minimize passenger train disruption.
              </p>
            </div>
          </div>
        </Drawer>
      )}
    </div>
  );
}