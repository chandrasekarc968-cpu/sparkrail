import React, { useState, useMemo, useCallback } from 'react';
import {
  Train as TrainIcon,
  Layers,
  Zap,
  Clock,
  UserCheck,
  RefreshCw
} from 'lucide-react';
import type { Scenario, ScheduledJob, Train, Department, OptimizedSchedule } from '../../api/types';

export interface MareyChartProps {
  scenario: Scenario | null;
  scheduledJobs?: ScheduledJob[];
  schedule?: OptimizedSchedule | null;
  onJobSelect?: (jobId: string) => void;
  onSelectJob?: (jobId: string) => void;
  selectedJobId?: string | null;
  onShiftBlock?: (jobId: string, shiftMinutes: number) => void;
  lang?: 'en' | 'hi';
}

interface StationChainage {
  code: string;
  nameEn: string;
  nameHi: string;
  km: number;
}

const STATIONS: StationChainage[] = [
  { code: 'SFG', nameEn: 'Subedarganj', nameHi: 'सूबेदारगंज', km: 0.0 },
  { code: 'PRYJ', nameEn: 'Prayagraj Jn', nameHi: 'प्रयागराज जं.', km: 4.2 },
  { code: 'NYN', nameEn: 'Naini Jn', nameHi: 'नैनी जं.', km: 11.5 },
  { code: 'KCN', nameEn: 'Karchana', nameHi: 'करछना', km: 23.0 },
  { code: 'BEP', nameEn: 'Bheerpur', nameHi: 'भीरपुर', km: 38.6 },
  { code: 'MJA', nameEn: 'Meja Road', nameHi: 'मेजा रोड', km: 50.8 },
  { code: 'MNF', nameEn: 'Manda Road', nameHi: 'मांडा रोड', km: 63.2 },
  { code: 'JIA', nameEn: 'Jigna', nameHi: 'जिगना', km: 71.4 },
  { code: 'MZP', nameEn: 'Mirzapur', nameHi: 'मिर्जापुर', km: 80.0 },
];

const HOURS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24];

export const MareyChart: React.FC<MareyChartProps> = ({
  scenario,
  scheduledJobs,
  schedule,
  onJobSelect,
  onSelectJob,
  selectedJobId,
  onShiftBlock,
  lang = 'en'
}) => {
  const jobs = useMemo(() => {
    if (scheduledJobs && scheduledJobs.length > 0) return scheduledJobs;
    if (schedule?.scheduled_jobs) return schedule.scheduled_jobs;
    return [];
  }, [scheduledJobs, schedule]);

  // Chart Coordinate Dimensions
  const SVG_WIDTH = 1200;
  const SVG_HEIGHT = 650;
  const MARGIN = { top: 40, right: 40, bottom: 50, left: 140 };

  const chartWidth = SVG_WIDTH - MARGIN.left - MARGIN.right;
  const chartHeight = SVG_HEIGHT - MARGIN.top - MARGIN.bottom;

  const [hoveredTrain, setHoveredTrain] = useState<Train | null>(null);
  const [hoveredJob, setHoveredJob] = useState<ScheduledJob | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);
  const [activeShiftJobId, setActiveShiftJobId] = useState<string | null>(null);
  const [isEvaluatingShift, setIsEvaluatingShift] = useState<boolean>(false);

  // Time to X conversion (0 to 24 hours)
  const timeToX = useCallback((hours: number): number => {
    return MARGIN.left + (Math.max(0, Math.min(24, hours)) / 24) * chartWidth;
  }, [chartWidth, MARGIN.left]);

  // Km to Y conversion (0 to 80 km)
  const kmToY = useCallback((km: number): number => {
    return MARGIN.top + (Math.max(0, Math.min(80, km)) / 80) * chartHeight;
  }, [chartHeight, MARGIN.top]);

  // Block Section Km mapping helper
  const getBlockKmRange = (blockId: string): [number, number] => {
    const b = scenario?.blocks.find((blk) => blk.id === blockId);
    if (b) {
      return [b.chainage_start, b.chainage_end];
    }
    // Fallback block index mapping (10km chunks)
    const match = blockId.match(/\d+/);
    const idx = match ? parseInt(match[0], 10) - 1 : 0;
    return [idx * 10.0, (idx + 1) * 10.0];
  };

  // Department colors
  const getDeptColor = (dept: Department | string): { fill: string; stroke: string; label: string } => {
    const d = String(dept).toUpperCase();
    if (d.includes('ENG') || d.includes('CIVIL')) {
      return { fill: 'rgba(249, 115, 22, 0.35)', stroke: '#f97316', label: 'Civil / Track' };
    }
    if (d.includes('OHE') || d.includes('TRD') || d.includes('ELEC')) {
      return { fill: 'rgba(2, 132, 199, 0.35)', stroke: '#0284c7', label: '25kV TRD/OHE' };
    }
    if (d.includes('S&T') || d.includes('SIG') || d.includes('TEL')) {
      return { fill: 'rgba(16, 185, 129, 0.35)', stroke: '#10b981', label: 'S&T Interlocking' };
    }
    return { fill: 'rgba(168, 85, 247, 0.35)', stroke: '#a855f7', label: 'General Poss.' };
  };

  // Train line style
  const getTrainStyle = (train: Train): { stroke: string; strokeWidth: number; dash?: string; label: string } => {
    const cat = train.category.toLowerCase();
    const isLoaded = Boolean(train.is_loaded_freight || (train.gross_tonnage_tonnes && train.gross_tonnage_tonnes >= 4000));
    if (cat === 'premium') {
      return { stroke: '#06b6d4', strokeWidth: 3.5, label: 'Premium Vande Bharat / Rajdhani' };
    }
    if (cat === 'express') {
      return { stroke: '#3b82f6', strokeWidth: 2.5, label: 'Mail / Express' };
    }
    if (isLoaded) {
      return { stroke: '#a855f7', strokeWidth: 3.0, label: 'Heavy Bulk Mineral/Coal (5000t)' };
    }
    return { stroke: '#94a3b8', strokeWidth: 1.8, dash: '4,3', label: 'Empty Freight / Parcel' };
  };

  // Calculate train path coordinates
  const trainPaths = useMemo(() => {
    if (!scenario?.trains) return [];

    return scenario.trains.map((train, idx) => {
      const isUpDirection = idx % 2 === 0;
      const startKm = isUpDirection ? 0.0 : 80.0;
      const endKm = isUpDirection ? 80.0 : 0.0;

      const tStart = train.scheduled_start;
      const tEnd = train.scheduled_end;

      const x1 = timeToX(tStart);
      const y1 = kmToY(startKm);
      const x2 = timeToX(tEnd);
      const y2 = kmToY(endKm);

      return {
        train,
        x1,
        y1,
        x2,
        y2,
        isUp: isUpDirection
      };
    });
  }, [scenario, kmToY, timeToX]);

  const handleBlockShiftConfirm = (shiftMins: number) => {
    if (!activeShiftJobId || !onShiftBlock) return;
    setIsEvaluatingShift(true);
    onShiftBlock(activeShiftJobId, shiftMins);
    setTimeout(() => {
      setIsEvaluatingShift(false);
      setActiveShiftJobId(null);
    }, 400);
  };

  return (
    <div className="relative w-full overflow-hidden rounded-xl border border-slate-700/60 bg-slate-950/90 p-4 shadow-2xl backdrop-blur-md">
      {/* Header bar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/30">
            <Layers className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold tracking-wide text-slate-100">
                {lang === 'hi' ? 'डिजिटल मारे चार्ट (समय-दूरी ग्राफ)' : 'Digital Marey Chart (Time-Distance Graph)'}
              </h2>
              <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-xs font-semibold text-emerald-300 ring-1 ring-emerald-500/40">
                24-Hour Corridor
              </span>
            </div>
            <p className="text-xs text-slate-400">
              {lang === 'hi'
                ? 'प्रयागराज डिवीजन: सूबेदारगंज (किमी 0) से मिर्जापुर (किमी 80) — ट्रेनों के पथ और ब्लॉक ऑक्यूपेंसी'
                : 'Prayagraj Division: Subedarganj (Km 0) to Mirzapur (Km 80) — Train Paths & Block Occupations'}
            </p>
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5 text-cyan-400">
            <span className="h-1 w-5 rounded-full bg-cyan-400" />
            <span>Vande Bharat / Rajdhani</span>
          </div>
          <div className="flex items-center gap-1.5 text-purple-400">
            <span className="h-1 w-5 rounded-full bg-purple-400" />
            <span>Loaded Coal/Mineral (5000t)</span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-400">
            <span className="h-0.5 w-5 rounded-full bg-slate-400" />
            <span>Empty Rake</span>
          </div>
          <div className="flex items-center gap-1.5 text-orange-400">
            <span className="h-3 w-3 rounded border border-orange-500 bg-orange-500/30" />
            <span>Civil Block</span>
          </div>
          <div className="flex items-center gap-1.5 text-sky-400">
            <span className="h-3 w-3 rounded border border-sky-500 bg-sky-500/30" />
            <span>25kV OHE Block</span>
          </div>
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="relative overflow-x-auto">
        <svg
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
          className="h-auto w-full min-w-[900px] select-none text-slate-200"
          style={{ fontVariantNumeric: 'tabular-nums' }}
        >
          <defs>
            {/* Diagonal hatch pattern for Shadow Blocks */}
            <pattern id="shadowHatch" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
              <line x1="0" y1="0" x2="0" y2="8" stroke="#38bdf8" strokeWidth="1.5" strokeOpacity="0.6" />
            </pattern>
            {/* Linear gradients for shaded possession blocks */}
            <linearGradient id="gradCivil" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#f97316" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#ea580c" stopOpacity="0.30" />
            </linearGradient>
            <linearGradient id="gradOHE" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#0284c7" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#0369a1" stopOpacity="0.30" />
            </linearGradient>
            <linearGradient id="gradSig" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#047857" stopOpacity="0.30" />
            </linearGradient>
          </defs>

          {/* Chart Background Grid */}
          <rect
            x={MARGIN.left}
            y={MARGIN.top}
            width={chartWidth}
            height={chartHeight}
            fill="#090d16"
            stroke="#1e293b"
            strokeWidth="1.5"
          />

          {/* Vertical Hourly Gridlines (00:00 to 24:00) */}
          {HOURS.map((hour) => {
            const x = timeToX(hour);
            const isMajor = hour % 4 === 0;
            return (
              <g key={`hour-${hour}`}>
                <line
                  x1={x}
                  y1={MARGIN.top}
                  x2={x}
                  y2={MARGIN.top + chartHeight}
                  stroke={isMajor ? '#334155' : '#1e293b'}
                  strokeWidth={isMajor ? 1.2 : 0.8}
                  strokeDasharray={isMajor ? undefined : '2,2'}
                />
                {/* 15-minute intermediate tick */}
                {hour < 24 ? (
                  <line
                    x1={timeToX(hour + 0.5)}
                    y1={MARGIN.top}
                    x2={timeToX(hour + 0.5)}
                    y2={MARGIN.top + chartHeight}
                    stroke="#141c2b"
                    strokeWidth="0.5"
                  />
                ) : null}
                {/* Hour text on top and bottom */}
                <text
                  x={x}
                  y={MARGIN.top - 12}
                  textAnchor="middle"
                  className="fill-slate-400 text-[10px] font-mono font-medium"
                >
                  {`${String(hour).padStart(2, '0')}:00`}
                </text>
                <text
                  x={x}
                  y={MARGIN.top + chartHeight + 20}
                  textAnchor="middle"
                  className="fill-slate-400 text-[10px] font-mono font-medium"
                >
                  {`${String(hour).padStart(2, '0')}:00`}
                </text>
              </g>
            );
          })}

          {/* Horizontal Station Lines & Chainage Labels */}
          {STATIONS.map((stn) => {
            const y = kmToY(stn.km);
            const isJunction = stn.code === 'PRYJ' || stn.code === 'NYN' || stn.code === 'MZP';
            return (
              <g key={`station-${stn.code}`}>
                <line
                  x1={MARGIN.left}
                  y1={y}
                  x2={MARGIN.left + chartWidth}
                  y2={y}
                  stroke={isJunction ? '#334155' : '#1e293b'}
                  strokeWidth={isJunction ? 1.5 : 0.8}
                />
                {/* Station Label on Left Y-Axis */}
                <text
                  x={MARGIN.left - 12}
                  y={y - 2}
                  textAnchor="end"
                  className={`text-[11px] font-bold ${isJunction ? 'fill-emerald-400' : 'fill-slate-300'}`}
                >
                  {lang === 'hi' ? stn.nameHi : stn.nameEn}
                </text>
                <text
                  x={MARGIN.left - 12}
                  y={y + 11}
                  textAnchor="end"
                  className="fill-slate-500 text-[9px] font-mono"
                >
                  {`[${stn.code}] Km ${stn.km.toFixed(1)}`}
                </text>
              </g>
            );
          })}

          {/* Midday Peak Summer Thermal Hazard Zone (12:00 to 16:00) */}
          {Boolean(scenario?.weather?.is_summer_buckling_risk) && (
            <g opacity="0.15">
              <rect
                x={timeToX(12)}
                y={MARGIN.top}
                width={timeToX(16) - timeToX(12)}
                height={chartHeight}
                fill="#ef4444"
              />
              <text
                x={timeToX(14)}
                y={MARGIN.top + 30}
                textAnchor="middle"
                className="fill-red-400 text-[11px] font-bold uppercase tracking-wider"
              >
                ⚠️ IRPWM Para 509 Summer Buckling Zone (Tr &ge; 60°C)
              </text>
            </g>
          )}

          {/* 1. Maintenance Possession Blocks (Shaded Rectangular Bands) */}
          {jobs.map((job) => {
            const [startKm, endKm] = getBlockKmRange(job.block_id);
            const x = timeToX(job.start_time);
            const w = Math.max(12, timeToX(job.end_time) - x);
            const y = kmToY(startKm);
            const h = Math.max(14, kmToY(endKm) - y);

            const isSelected = selectedJobId === job.job_id;
            const colors = getDeptColor(job.department);
            const isFixed = job.job_id.startsWith('J_FIXED') || job.job_id === 'FB1' || job.job_id === 'FB2';

            return (
              <g
                key={`block-${job.job_id}`}
                className="cursor-pointer transition-all duration-150"
                onClick={() => {
                  onJobSelect?.(job.job_id);
                  onSelectJob?.(job.job_id);
                }}
                onMouseEnter={(e) => {
                  setHoveredJob(job);
                  setTooltipPos({ x: e.clientX, y: e.clientY });
                }}
                onMouseLeave={() => {
                  setHoveredJob(null);
                  setTooltipPos(null);
                }}
              >
                {/* Main block rect */}
                <rect
                  x={x}
                  y={y}
                  width={w}
                  height={h}
                  rx="4"
                  fill={colors.fill}
                  stroke={isSelected ? '#38bdf8' : colors.stroke}
                  strokeWidth={isSelected ? 2.5 : 1.5}
                />

                {/* Shadow possession overlay */}
                {job.is_shadow_block && (
                  <rect
                    x={x}
                    y={y}
                    width={w}
                    height={h}
                    rx="4"
                    fill="url(#shadowHatch)"
                    pointerEvents="none"
                  />
                )}

                {/* Block label inside rect */}
                <text
                  x={x + 6}
                  y={y + 14}
                  className="fill-slate-100 text-[10px] font-mono font-bold tracking-tight"
                >
                  {job.job_id}
                </text>
                <text
                  x={x + 6}
                  y={y + 26}
                  className="fill-slate-300 text-[8px] font-medium"
                >
                  {job.department}
                </text>

                {/* Immutable Active Lock badge for safety */}
                {isFixed && (
                  <g transform={`translate(${x + w - 16}, ${y + 4})`}>
                    <rect width="12" height="12" rx="2" fill="#0f172a" stroke="#e2e8f0" strokeWidth="0.8" />
                    <text x="6" y="9" textAnchor="middle" className="fill-amber-400 text-[8px] font-bold">
                      🔒
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* 2. Train Path Slanted Lines */}
          {trainPaths.map(({ train, x1, y1, x2, y2, isUp }) => {
            const style = getTrainStyle(train);
            const isHovered = hoveredTrain?.id === train.id;

            return (
              <g
                key={`train-${train.id}`}
                className="cursor-pointer transition-opacity duration-150"
                onMouseEnter={(e) => {
                  setHoveredTrain(train);
                  setTooltipPos({ x: e.clientX, y: e.clientY });
                }}
                onMouseLeave={() => {
                  setHoveredTrain(null);
                  setTooltipPos(null);
                }}
              >
                {/* Hover glow line */}
                {isHovered && (
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke="#ffffff"
                    strokeWidth={style.strokeWidth + 4}
                    strokeOpacity="0.4"
                  />
                )}

                {/* Main train line */}
                <line
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke={style.stroke}
                  strokeWidth={isHovered ? style.strokeWidth + 1.5 : style.strokeWidth}
                  strokeDasharray={style.dash}
                  strokeLinecap="round"
                />

                {/* Train number text marker along trajectory */}
                <text
                  x={x1 + (x2 - x1) * 0.25}
                  y={y1 + (y2 - y1) * 0.25 - 4}
                  className="fill-slate-200 text-[9px] font-mono font-bold"
                  transform={`rotate(${isUp ? 22 : -22}, ${x1 + (x2 - x1) * 0.25}, ${y1 + (y2 - y1) * 0.25 - 4})`}
                >
                  {train.id}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Interactive Tooltip Card */}
      {hoveredTrain && tooltipPos && (
        <div
          className="pointer-events-none fixed z-50 w-72 rounded-lg border border-slate-700 bg-slate-900/95 p-3 text-xs shadow-2xl backdrop-blur-md"
          style={{
            left: `${Math.min(window.innerWidth - 300, tooltipPos.x + 15)}px`,
            top: `${Math.min(window.innerHeight - 200, tooltipPos.y - 40)}px`
          }}
        >
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center gap-1.5 font-bold text-slate-100">
              <TrainIcon className="h-4 w-4 text-cyan-400" />
              <span>{hoveredTrain.name || hoveredTrain.id}</span>
            </div>
            <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-semibold text-slate-300 uppercase">
              {hoveredTrain.category}
            </span>
          </div>

          <div className="mt-2 space-y-1.5 text-slate-300">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Scheduled:</span>
              <span className="font-mono">{`T+${hoveredTrain.scheduled_start.toFixed(1)}h -> T+${hoveredTrain.scheduled_end.toFixed(1)}h`}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Gross Tonnage (FOIS):</span>
              <span className="font-mono font-semibold text-purple-300">
                {hoveredTrain.gross_tonnage_tonnes ? `${hoveredTrain.gross_tonnage_tonnes.toLocaleString()} t` : '1,500 t'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Max Speed:</span>
              <span className="font-mono">{`${hoveredTrain.max_speed_kmh || 100} km/h`}</span>
            </div>
            {hoveredTrain.crew_duty_remaining_hours && (
              <div className="flex items-center justify-between border-t border-slate-800/80 pt-1 text-emerald-300">
                <span className="flex items-center gap-1">
                  <UserCheck className="h-3 w-3" />
                  <span>HOER Crew Duty:</span>
                </span>
                <span className="font-mono font-bold">{`${hoveredTrain.crew_duty_remaining_hours.toFixed(1)}h remaining`}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {hoveredJob && tooltipPos && (
        <div
          className="pointer-events-none fixed z-50 w-80 rounded-lg border border-slate-700 bg-slate-900/95 p-3 text-xs shadow-2xl backdrop-blur-md"
          style={{
            left: `${Math.min(window.innerWidth - 320, tooltipPos.x + 15)}px`,
            top: `${Math.min(window.innerHeight - 200, tooltipPos.y - 40)}px`
          }}
        >
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center gap-1.5 font-bold text-orange-400">
              <Layers className="h-4 w-4" />
              <span>{`Possession Block ${hoveredJob.job_id}`}</span>
            </div>
            <span className="rounded bg-orange-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-orange-300">
              {hoveredJob.department}
            </span>
          </div>

          <div className="mt-2 space-y-1.5 text-slate-300">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Section:</span>
              <span className="font-mono font-semibold text-slate-200">{hoveredJob.block_id}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Time Window:</span>
              <span className="font-mono">{`T+${hoveredJob.start_time.toFixed(1)}h -> T+${hoveredJob.end_time.toFixed(1)}h (${(hoveredJob.end_time - hoveredJob.start_time).toFixed(1)} hrs)`}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">TCI Score:</span>
              <span className="font-mono font-bold text-amber-400">{`${hoveredJob.tci.toFixed(1)} / 100`}</span>
            </div>
            {hoveredJob.is_shadow_block && (
              <div className="flex items-center gap-1 rounded bg-sky-500/15 px-2 py-1 text-[11px] text-sky-300 ring-1 ring-sky-500/30">
                <Zap className="h-3.5 w-3.5 shrink-0" />
                <span>Shadow Bundled with: {hoveredJob.shadow_with_jobs?.join(', ') || 'Multi-Dept'}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Re-planning Shift Control Bar */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900/70 p-3 text-xs">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-emerald-400" />
          <span className="font-semibold text-slate-200">
            {lang === 'hi' ? 'इंटरैक्टिव री-प्लानिंग (विंडो शिफ्ट):' : 'Interactive Re-Planning (Window Shift):'}
          </span>
          <select
            value={activeShiftJobId || ''}
            onChange={(e) => setActiveShiftJobId(e.target.value || null)}
            className="rounded border border-slate-700 bg-slate-800 px-2 py-1 font-mono text-slate-200 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          >
            <option value="">{lang === 'hi' ? '-- ब्लॉक चुनें --' : '-- Select Block --'}</option>
            {jobs.map((j) => (
              <option key={j.job_id} value={j.job_id}>
                {`${j.job_id} (${j.department} on ${j.block_id})`}
              </option>
            ))}
          </select>
        </div>

        {activeShiftJobId && (
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Shift Window:</span>
            <button
              onClick={() => handleBlockShiftConfirm(-30)}
              disabled={isEvaluatingShift}
              className="rounded bg-slate-800 px-2.5 py-1 font-mono text-slate-200 hover:bg-slate-700 disabled:opacity-50"
            >
              -30 min
            </button>
            <button
              onClick={() => handleBlockShiftConfirm(-15)}
              disabled={isEvaluatingShift}
              className="rounded bg-slate-800 px-2.5 py-1 font-mono text-slate-200 hover:bg-slate-700 disabled:opacity-50"
            >
              -15 min
            </button>
            <button
              onClick={() => handleBlockShiftConfirm(+15)}
              disabled={isEvaluatingShift}
              className="rounded bg-slate-800 px-2.5 py-1 font-mono text-slate-200 hover:bg-slate-700 disabled:opacity-50"
            >
              +15 min
            </button>
            <button
              onClick={() => handleBlockShiftConfirm(+30)}
              disabled={isEvaluatingShift}
              className="rounded bg-slate-800 px-2.5 py-1 font-mono text-slate-200 hover:bg-slate-700 disabled:opacity-50"
            >
              +30 min
            </button>
            {isEvaluatingShift && <RefreshCw className="h-4 w-4 animate-spin text-emerald-400" />}
          </div>
        )}
      </div>
    </div>
  );
};
