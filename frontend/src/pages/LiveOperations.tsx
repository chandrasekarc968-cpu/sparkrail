import { useState, useEffect, useRef } from 'react';
import { ApiClient } from '../api/client';
import type { Scenario, OptimizedSchedule, SystemEvent } from '../api/types';
import { useAppContext } from '../context/useAppContext';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { ErrorBanner } from '../components/ui/ErrorBanner';
import { Skeleton } from '../components/ui/Skeleton';
import {
  Play,
  Pause,
  RotateCcw,
  Train as TrainIcon,
  Wrench,
  Radio
} from 'lucide-react';

export function LiveOperations() {
  const { isDemoMode, lastRefresh } = useAppContext();
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [schedule, setSchedule] = useState<OptimizedSchedule | null>(null);
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Simulation Playback State
  const [isPlaying, setIsPlaying] = useState(false);
  const [simTime, setSimTime] = useState<number>(3.5); // 0.0 to 24.0 hours (e.g. 03:30 AM)
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const timerRef = useRef<number | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [scen, sched, evts] = await Promise.all([
        ApiClient.getScenario(),
        ApiClient.getSchedule("latest"),
        ApiClient.getEvents()
      ]);
      setScenario(scen);
      setSchedule(sched);
      setEvents(evts);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load live telemetry.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [lastRefresh]);

  // Simulation timer loop
  useEffect(() => {
    if (isPlaying) {
      timerRef.current = window.setInterval(() => {
        setSimTime((prev) => {
          const next = prev + 0.05 * playbackSpeed;
          return next >= 24 ? 0 : Number(next.toFixed(2));
        });
      }, 200);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, playbackSpeed]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-64 w-full" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Skeleton className="h-80 lg:col-span-2" />
          <Skeleton className="h-80" />
        </div>
      </div>
    );
  }

  if (error || !scenario || !schedule) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-bold">Live Operations</h1>
        <ErrorBanner
          title="Telemetry Stream Disconnected"
          message={error || "Could not retrieve live railway telemetry."}
          onRetry={() => void loadData()}
        />
      </div>
    );
  }

  // Active blocks at current simTime
  const activeBlocksAtNow = schedule.scheduled_jobs.filter(
    (j) => simTime >= j.start_time && simTime <= j.end_time
  );
  const activeBlockIds = new Set(activeBlocksAtNow.map((j) => j.block_id));

  // Compute live positions for trains at current simTime
  const liveTrains = scenario.trains.map((train) => {
    const isEnRoute = simTime >= train.scheduled_start && simTime <= train.scheduled_end;
    const progress = isEnRoute
      ? (simTime - train.scheduled_start) / (train.scheduled_end - train.scheduled_start)
      : simTime < train.scheduled_start
      ? 0
      : 1;

    // Approximate km location between 0 and 80 km
    const estimatedKm = isEnRoute ? progress * 80 : simTime < train.scheduled_start ? 0 : 80;

    return {
      ...train,
      isEnRoute,
      progress,
      estimatedKm: Number(estimatedKm.toFixed(1)),
    };
  });

  const formatSimTime = (hours: number) => {
    const h = Math.floor(hours);
    const m = Math.floor((hours - h) * 60);
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')} IST`;
  };

  return (
    <div className="space-y-6">
      {/* Header & Playback Control Strip */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <h1 className="text-2xl font-extrabold tracking-tight text-neutral-950">
              Live Operations & Telemetry
            </h1>
            <Badge
              variant={isDemoMode ? "warning" : "success"}
              size="sm"
            >
              {isDemoMode ? "Demo Mode: Deterministic Replay" : "Live COA Stream Connected"}
            </Badge>
          </div>
          <p className="text-xs text-neutral-500 mt-0.5">
            Real-time train positioning, active possession boundaries, and delay cascade warnings.
          </p>
        </div>

        {/* Replay Controls */}
        <div className="flex items-center space-x-3 bg-white p-2 rounded-md border border-neutral-200 shadow-xs">
          <div className="text-xs font-mono font-bold text-neutral-800 tabular-nums px-2">
            Sim Clock: <span className="text-accent-600 font-extrabold">{formatSimTime(simTime)}</span>
          </div>

          <div className="flex items-center space-x-1 border-l border-neutral-200 pl-2">
            <Button
              variant="outline"
              size="icon"
              onClick={() => setSimTime(0)}
              aria-label="Reset replay clock to 00:00"
              className="w-8 h-8 min-h-[32px] min-w-[32px] p-0"
              title="Reset to 00:00"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </Button>

            <Button
              variant={isPlaying ? "outline" : "default"}
              size="icon"
              onClick={() => setIsPlaying(!isPlaying)}
              aria-label={isPlaying ? "Pause simulation replay" : "Play simulation replay"}
              className="w-8 h-8 min-h-[32px] min-w-[32px] p-0"
            >
              {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-current" />}
            </Button>
          </div>

          {/* Speed multiplier */}
          <div className="flex items-center space-x-1 text-[11px] font-mono border-l border-neutral-200 pl-2">
            {[1, 2, 5].map((spd) => (
              <button
                key={spd}
                type="button"
                onClick={() => setPlaybackSpeed(spd)}
                className={`px-1.5 py-0.5 rounded cursor-pointer ${
                  playbackSpeed === spd
                    ? "bg-neutral-800 text-white font-bold"
                    : "text-neutral-500 hover:text-neutral-900"
                }`}
              >
                {spd}x
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Interactive Schematic Track Map */}
      <Card>
        <CardHeader className="py-3 px-5 flex flex-row items-center justify-between border-b border-neutral-100">
          <div>
            <CardTitle className="text-sm">Corridor Schematic Track Diagram (Chainage 0.0 - 80.0 km)</CardTitle>
            <p className="text-[11px] text-neutral-500">
              Active block boundaries (red), clear track (green), and dynamic train positions at {formatSimTime(simTime)}
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono text-neutral-600">
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full bg-op-green" /> Clear
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full bg-op-red animate-pulse" /> Maintenance Block
            </span>
          </div>
        </CardHeader>

        <CardContent className="p-6 bg-neutral-900 text-neutral-100 overflow-x-auto select-none min-h-[220px] flex flex-col justify-center">
          <div className="min-w-[800px] space-y-6">
            {/* Schematic Linear Track Representation */}
            <div className="relative pt-6 pb-6">
              {/* Main Rail Line */}
              <div className="h-2 bg-neutral-700 rounded-full relative flex">
                {scenario.blocks.map((block) => {
                  const isBlocked = activeBlockIds.has(block.id);
                  return (
                    <div
                      key={block.id}
                      className={`h-full relative flex-1 transition-colors ${
                        isBlocked
                          ? "bg-op-red pattern-diagonal-stripes"
                          : "bg-neutral-600 hover:bg-neutral-500"
                      }`}
                      title={`${block.id}: ${block.description} (${isBlocked ? 'BLOCKED' : 'CLEAR'})`}
                    >
                      {/* Section joint marker */}
                      <div className="absolute right-0 -top-2 -bottom-2 w-0.5 bg-neutral-400 z-10" />

                      {/* Block Section Label */}
                      <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] font-mono font-bold text-neutral-300 whitespace-nowrap">
                        {block.id}
                      </div>

                      {/* Closed Badge if currently occupied by maintenance */}
                      {isBlocked && (
                        <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-[9px] font-bold text-white bg-op-red px-1.5 py-0.5 rounded uppercase tracking-wider whitespace-nowrap shadow-xs animate-pulse">
                          CLOSED ({activeBlocksAtNow.find((j) => j.block_id === block.id)?.job_id})
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Station Indicators along chainage */}
              <div className="flex justify-between text-[10px] font-mono text-neutral-400 mt-8 px-1">
                <span>Stn A (Ghaziabad 0km)</span>
                <span>Stn C (Hathras 20km)</span>
                <span>Stn E (Tundla 40km)</span>
                <span>Stn G (Etawah 60km)</span>
                <span>Stn I (Phaphund 80km)</span>
              </div>

              {/* Real-Time Train Markers on the Track */}
              {liveTrains
                .filter((t) => t.isEnRoute)
                .map((train) => {
                  const leftPercent = (train.estimatedKm / 80) * 100;
                  const isPremium = train.category === "premium";

                  return (
                    <div
                      key={train.id}
                      className="absolute top-1/2 -translate-y-1/2 -mt-4 transition-all duration-300 z-30"
                      style={{ left: `${Math.min(96, Math.max(2, leftPercent))}%` }}
                    >
                      <div className="relative group cursor-pointer flex flex-col items-center">
                        <div
                          className={`w-5 h-5 rounded-full flex items-center justify-center shadow-lg border-2 border-neutral-900 ${
                            isPremium ? "bg-amber-400 text-neutral-950" : "bg-op-blue text-white"
                          }`}
                        >
                          <TrainIcon className="w-3 h-3" />
                        </div>
                        <span
                          className={`text-[9px] font-mono font-bold px-1 rounded absolute -top-5 whitespace-nowrap ${
                            isPremium ? "bg-amber-400 text-neutral-950" : "bg-neutral-800 text-neutral-200"
                          }`}
                        >
                          {train.id}
                        </span>

                        {/* Train Tooltip */}
                        <div className="hidden group-hover:block absolute bottom-6 bg-neutral-950 text-white text-[10px] p-2 rounded shadow-xl border border-neutral-700 whitespace-nowrap z-50">
                          <p className="font-bold">{train.name || train.id}</p>
                          <p className="text-neutral-400">Position: km {train.estimatedKm} | Speed: {train.max_speed_kmh} km/h</p>
                          <p className="text-op-green">Delay: {train.current_delay_min || 0} mins</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 3 Secondary Panels: Premium Train Alerts, Maintenance Crews, COA Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 1. Premium Train Surveillance */}
        <Card>
          <CardHeader className="py-3 px-5 flex flex-row items-center justify-between">
            <CardTitle className="text-sm">Premium Train Proximity</CardTitle>
            <TrainIcon className="w-4 h-4 text-amber-600" />
          </CardHeader>
          <CardContent className="p-4 space-y-3 text-xs">
            {scenario.trains
              .filter((t) => t.category === "premium")
              .map((train) => {
                const isDelayed = (schedule.train_delays[train.id] || 0) > 0;
                return (
                  <div
                    key={train.id}
                    className="p-2.5 rounded border border-neutral-200 bg-neutral-50 flex items-center justify-between"
                  >
                    <div>
                      <div className="flex items-center space-x-1.5 font-bold text-neutral-900">
                        <span>{train.id}</span>
                        <span className="text-[11px] font-normal text-neutral-600 truncate max-w-[140px]">
                          ({train.name})
                        </span>
                      </div>
                      <div className="text-[10px] text-neutral-500 font-mono mt-0.5">
                        Route: {train.route.join(" → ")}
                      </div>
                    </div>
                    <div>
                      {isDelayed ? (
                        <Badge variant="danger" size="sm">
                          +{schedule.train_delays[train.id]}h Delay
                        </Badge>
                      ) : (
                        <Badge variant="success" size="sm">
                          On Time
                        </Badge>
                      )}
                    </div>
                  </div>
                );
              })}
          </CardContent>
        </Card>

        {/* 2. Machine & Crew Telemetry */}
        <Card>
          <CardHeader className="py-3 px-5 flex flex-row items-center justify-between">
            <CardTitle className="text-sm">Maintenance Machine Status</CardTitle>
            <Wrench className="w-4 h-4 text-neutral-500" />
          </CardHeader>
          <CardContent className="p-4 space-y-3 text-xs">
            {scenario.resources.map((res) => {
              const isWorking = activeBlocksAtNow.length > 0;
              return (
                <div key={res.id} className="p-2.5 rounded border border-neutral-200 bg-neutral-50">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="font-bold text-neutral-900">{res.name}</p>
                      <p className="text-[10px] text-neutral-500 font-mono">
                        Dept: {res.department || "Engineering"} | Units: {res.capacity}
                      </p>
                    </div>
                    <Badge variant={isWorking ? "info" : "neutral"} size="sm">
                      {isWorking ? "In Possession" : "Standby"}
                    </Badge>
                  </div>
                  <div className="mt-2 w-full bg-neutral-200 h-1 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${isWorking ? "bg-accent-600 w-3/4" : "bg-neutral-400 w-1/4"}`}
                    />
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>

        {/* 3. Control Office Application (COA) Event Feed */}
        <Card>
          <CardHeader className="py-3 px-5 flex flex-row items-center justify-between">
            <CardTitle className="text-sm">COA Live Dispatch Stream</CardTitle>
            <Radio className="w-4 h-4 text-op-green animate-pulse" />
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-neutral-100 text-xs max-h-72 overflow-y-auto">
              {events.map((evt) => (
                <div key={evt.id} className="p-3 hover:bg-neutral-50 transition-colors">
                  <div className="flex items-center justify-between text-[10px] text-neutral-400 font-mono mb-0.5">
                    <span className="font-bold text-neutral-700">{evt.source}</span>
                    <span>{new Date(evt.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-neutral-800 leading-snug">{evt.message}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}