import React, { useState } from 'react';
import {
  Sparkles,
  Play,
  X,
  AlertTriangle,
  Flame,
  Zap,
  Clock,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  CheckCircle2
} from 'lucide-react';
import { ApiClient } from '../../api/client';
import type { Scenario, WhatIfScenarioResponse, WhatIfModification } from '../../api/types';

export interface WhatIfSimulatorModalProps {
  isOpen: boolean;
  onClose: () => void;
  scenario?: Scenario | null;
  onApplyAdvisory?: (whatIfSchedule: any) => void;
  onScenarioCommitted?: (whatIfSchedule: any) => void;
}

export const WhatIfSimulatorModal: React.FC<WhatIfSimulatorModalProps> = ({
  isOpen,
  onClose,
  scenario,
  onApplyAdvisory,
  onScenarioCommitted
}) => {
  if (!isOpen) return null;

  const [simType, setSimType] = useState<'machine_extension' | 'train_delay' | 'speed_restriction'>('machine_extension');
  const [selectedJobId, setSelectedJobId] = useState<string>('J1');
  const [extensionHours, setExtensionHours] = useState<number>(1.0);
  const [selectedTrainId, setSelectedTrainId] = useState<string>('T4');
  const [trainDelayMinutes, setTrainDelayMinutes] = useState<number>(30.0);
  const [speedRestrictionKmh, setSpeedRestrictionKmh] = useState<number>(30.0);
  const [selectedBlockId, setSelectedBlockId] = useState<string>('B2');

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [result, setResult] = useState<WhatIfScenarioResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lang, setLang] = useState<'en' | 'hi'>('en');

  const handleRunSimulation = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const modifications: WhatIfModification[] = [];

      if (simType === 'machine_extension') {
        modifications.push({
          job_id: selectedJobId,
          extend_duration_hours: extensionHours
        });
      } else if (simType === 'train_delay') {
        modifications.push({
          train_id: selectedTrainId,
          added_delay_min: trainDelayMinutes
        });
      } else if (simType === 'speed_restriction') {
        modifications.push({
          speed_restriction_kmh: speedRestrictionKmh,
          affected_block_id: selectedBlockId
        });
      }

      const res = await ApiClient.simulateWhatIf({
        scenario_id: 'latest',
        modifications,
        fast_solve: true
      });

      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Simulation failed.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md">
      <div className="relative flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 bg-slate-950/70 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 text-purple-400 ring-1 ring-purple-500/30">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-slate-100">
                  {lang === 'hi' ? 'वॉट-इफ सैंडबॉक्स और परिदृश्य सिम्युलेटर' : '"What-If" Sandbox & Scenario Simulator'}
                </h3>
                <span className="rounded bg-purple-500/20 px-2 py-0.5 text-xs font-semibold text-purple-300 ring-1 ring-purple-500/40">
                  Sr. DOM Staging Mode
                </span>
              </div>
              <p className="text-xs text-slate-400">
                {lang === 'hi'
                  ? 'लाइव बीडीएमएस प्रणाली को प्रभावित किए बिना हाइपोथेटिकल घटनाओं और देरी का विश्लेषण करें।'
                  : 'Isolated staging environment to evaluate disruptions without committing to live BDMS.'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Language Toggle */}
            <div className="flex rounded-lg border border-slate-700 bg-slate-800 p-0.5 text-xs">
              <button
                onClick={() => setLang('en')}
                className={`rounded px-2 py-1 font-semibold ${lang === 'en' ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}
              >
                EN
              </button>
              <button
                onClick={() => setLang('hi')}
                className={`rounded px-2 py-1 font-semibold ${lang === 'hi' ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}
              >
                हिंदी
              </button>
            </div>

            <button
              onClick={onClose}
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Simulation Injector Form */}
          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-5">
            <h4 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-400">
              {lang === 'hi' ? '1. हाइपोथेटिकल घटना चुनें' : '1. Select Hypothetical Disruption'}
            </h4>

            {/* Type selector pills */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <button
                onClick={() => setSimType('machine_extension')}
                className={`flex flex-col items-start rounded-lg border p-3 text-left transition-all ${
                  simType === 'machine_extension'
                    ? 'border-purple-500 bg-purple-500/10 text-slate-100 ring-1 ring-purple-500/30'
                    : 'border-slate-800 bg-slate-900/60 text-slate-400 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center gap-2 font-semibold text-xs">
                  <Clock className="h-4 w-4 text-purple-400" />
                  <span>{lang === 'hi' ? 'मशीन अवधि विस्तार' : 'Extend Machine Duration'}</span>
                </div>
                <span className="mt-1 text-[11px] text-slate-500">
                  {lang === 'hi' ? 'BCM / टैम्पर कार्य समय बढ़ाएं (+60 min)' : 'Grant extra hours to BCM/Tie Tamper'}
                </span>
              </button>

              <button
                onClick={() => setSimType('train_delay')}
                className={`flex flex-col items-start rounded-lg border p-3 text-left transition-all ${
                  simType === 'train_delay'
                    ? 'border-purple-500 bg-purple-500/10 text-slate-100 ring-1 ring-purple-500/30'
                    : 'border-slate-800 bg-slate-900/60 text-slate-400 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center gap-2 font-semibold text-xs">
                  <Flame className="h-4 w-4 text-amber-400" />
                  <span>{lang === 'hi' ? 'लोको विफलता / ट्रेन विलंब' : 'Loco Failure / Train Delay'}</span>
                </div>
                <span className="mt-1 text-[11px] text-slate-500">
                  {lang === 'hi' ? 'अचानक ट्रेन रुकने पर प्रभाव देखें' : 'Inject sudden breakdown or line delay'}
                </span>
              </button>

              <button
                onClick={() => setSimType('speed_restriction')}
                className={`flex flex-col items-start rounded-lg border p-3 text-left transition-all ${
                  simType === 'speed_restriction'
                    ? 'border-purple-500 bg-purple-500/10 text-slate-100 ring-1 ring-purple-500/30'
                    : 'border-slate-800 bg-slate-900/60 text-slate-400 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center gap-2 font-semibold text-xs">
                  <AlertTriangle className="h-4 w-4 text-red-400" />
                  <span>{lang === 'hi' ? 'अस्थायी गति प्रतिबंध (TSR)' : 'Speed Restriction (TSR)'}</span>
                </div>
                <span className="mt-1 text-[11px] text-slate-500">
                  {lang === 'hi' ? 'रेल फ्रैक्चर पर 30 किमी/घंटा प्रतिबंध' : 'Track fracture 30 km/h restriction'}
                </span>
              </button>
            </div>

            {/* Inputs based on type */}
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              {simType === 'machine_extension' && (
                <>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      {lang === 'hi' ? 'रखरखाव ब्लॉक' : 'Target Maintenance Block:'}
                    </label>
                    <select
                      value={selectedJobId}
                      onChange={(e) => setSelectedJobId(e.target.value)}
                      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:ring-1 focus:ring-purple-500"
                    >
                      {scenario?.jobs.map((j) => (
                        <option key={j.id} value={j.id}>
                          {`${j.id} - ${j.department} on ${j.block_id} (${j.job_type || 'Maintenance'})`}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      {lang === 'hi' ? 'अतिरिक्त समय' : 'Added Extra Hours:'}
                    </label>
                    <select
                      value={extensionHours}
                      onChange={(e) => setExtensionHours(parseFloat(e.target.value))}
                      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:ring-1 focus:ring-purple-500"
                    >
                      <option value="0.5">+30 minutes (0.5h)</option>
                      <option value="1.0">+60 minutes (1.0h)</option>
                      <option value="1.5">+90 minutes (1.5h)</option>
                      <option value="2.0">+120 minutes (2.0h)</option>
                    </select>
                  </div>
                </>
              )}

              {simType === 'train_delay' && (
                <>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      {lang === 'hi' ? 'प्रभावित ट्रेन' : 'Affected Train:'}
                    </label>
                    <select
                      value={selectedTrainId}
                      onChange={(e) => setSelectedTrainId(e.target.value)}
                      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:ring-1 focus:ring-purple-500"
                    >
                      {scenario?.trains.map((t) => (
                        <option key={t.id} value={t.id}>
                          {`${t.id} - ${t.name || t.id} (${t.category})`}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      {lang === 'hi' ? 'विलंब मिनट' : 'Delay Added (Minutes):'}
                    </label>
                    <select
                      value={trainDelayMinutes}
                      onChange={(e) => setTrainDelayMinutes(parseFloat(e.target.value))}
                      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:ring-1 focus:ring-purple-500"
                    >
                      <option value="15">15 Minutes</option>
                      <option value="30">30 Minutes</option>
                      <option value="45">45 Minutes</option>
                      <option value="60">60 Minutes</option>
                    </select>
                  </div>
                </>
              )}

              {simType === 'speed_restriction' && (
                <>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      {lang === 'hi' ? 'ब्लॉक सेक्शन' : 'Block Section:'}
                    </label>
                    <select
                      value={selectedBlockId}
                      onChange={(e) => setSelectedBlockId(e.target.value)}
                      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:ring-1 focus:ring-purple-500"
                    >
                      {scenario?.blocks.map((b) => (
                        <option key={b.id} value={b.id}>
                          {`${b.id} - ${b.description}`}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      {lang === 'hi' ? 'गति सीमा (TSR)' : 'Caution Speed (km/h):'}
                    </label>
                    <select
                      value={speedRestrictionKmh}
                      onChange={(e) => setSpeedRestrictionKmh(parseFloat(e.target.value))}
                      className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:ring-1 focus:ring-purple-500"
                    >
                      <option value="20">20 km/h (Severe Defect)</option>
                      <option value="30">30 km/h (Standard Rail Flaw)</option>
                      <option value="50">50 km/h (Track Packing)</option>
                    </select>
                  </div>
                </>
              )}
            </div>

            <div className="mt-4 flex justify-end">
              <button
                onClick={handleRunSimulation}
                disabled={isLoading}
                className="flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 font-semibold text-xs text-white shadow-lg shadow-purple-600/30 hover:bg-purple-500 disabled:opacity-50"
              >
                {isLoading ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>{lang === 'hi' ? 'सिमुलेशन जारी है...' : 'Solving Scenario...'}</span>
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 fill-white" />
                    <span>{lang === 'hi' ? 'सिमुलेशन चलाएं' : 'Run What-If Simulation'}</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Simulation Results Report */}
          {result && (
            <div className="space-y-4 rounded-xl border border-purple-500/30 bg-purple-950/10 p-5 ring-1 ring-purple-500/20">
              <div className="flex items-center justify-between border-b border-purple-800/40 pb-3">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                  <span className="font-bold text-sm text-slate-100">
                    {lang === 'hi' ? 'तुलनात्मक डेल्टा रिपोर्ट' : 'Comparative Delta Report'}
                  </span>
                  <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-300">
                    {result.run_id}
                  </span>
                </div>
              </div>

              {/* Top Delta Metrics Cards */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-3">
                  <span className="text-[11px] text-slate-400">
                    {lang === 'hi' ? 'कुल विलंब डेल्टा' : 'Total Delay Delta'}
                  </span>
                  <div className="mt-1 flex items-center gap-2">
                    {result.delta_report.delta_cumulative_delay_min > 0 ? (
                      <TrendingUp className="h-4 w-4 text-amber-400" />
                    ) : (
                      <TrendingDown className="h-4 w-4 text-emerald-400" />
                    )}
                    <span className="text-lg font-bold font-mono text-slate-100">
                      {`${result.delta_report.delta_cumulative_delay_min > 0 ? '+' : ''}${result.delta_report.delta_cumulative_delay_min} min`}
                    </span>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-3">
                  <span className="text-[11px] text-slate-400">
                    {lang === 'hi' ? 'प्रभावित मालगाड़ियां' : 'Regulated Freight'}
                  </span>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-lg font-bold font-mono text-purple-400">
                      {result.delta_report.freight_rakes_regulated_count} rakes
                    </span>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-3">
                  <span className="text-[11px] text-slate-400">
                    {lang === 'hi' ? 'ऊर्जा हानि (Kinetic Loss)' : 'Kinetic Energy Loss'}
                  </span>
                  <div className="mt-1 flex items-center gap-2">
                    <Zap className="h-4 w-4 text-amber-400" />
                    <span className="text-lg font-bold font-mono text-amber-300">
                      {`${result.delta_report.total_energy_loss_kwh.toLocaleString()} kWh`}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-500">
                    {`~₹${result.delta_report.total_fuel_cost_impact_inr.toLocaleString()} traction cost`}
                  </span>
                </div>

                <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-3">
                  <span className="text-[11px] text-slate-400">
                    {lang === 'hi' ? 'मशीन उत्पादकता' : 'Machine Productivity'}
                  </span>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-lg font-bold font-mono text-emerald-400">
                      {`${result.delta_report.heavy_machine_productivity_delta_hours > 0 ? '+' : ''}${result.delta_report.heavy_machine_productivity_delta_hours} hrs`}
                    </span>
                  </div>
                </div>
              </div>

              {/* Natural Language XAI Narrative */}
              <div className="rounded-lg border border-slate-800 bg-slate-900/90 p-4">
                <span className="text-[11px] font-bold uppercase tracking-wider text-purple-400">
                  {lang === 'hi' ? 'वरिष्ठ नियंत्रक सारांश (Explainable AI Briefing)' : 'Chief Controller Briefing (Explainable AI)'}
                </span>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-200">
                  {lang === 'hi'
                    ? result.delta_report.narrative_summary_hi
                    : result.delta_report.narrative_summary_en}
                </p>
              </div>

              {/* Train Impact Details */}
              {result.delta_report.train_deltas.length > 0 && (
                <div className="overflow-x-auto rounded-lg border border-slate-800">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950/80 font-semibold text-slate-400">
                      <tr>
                        <th className="p-2.5">Train</th>
                        <th className="p-2.5">Category</th>
                        <th className="p-2.5 font-mono">Baseline Delay</th>
                        <th className="p-2.5 font-mono">What-If Delay</th>
                        <th className="p-2.5 font-mono">Delta</th>
                        <th className="p-2.5 font-mono">Energy Impact</th>
                        <th className="p-2.5">HOER Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
                      {result.delta_report.train_deltas.map((td) => (
                        <tr key={td.train_id} className="hover:bg-slate-800/40">
                          <td className="p-2.5 font-bold text-slate-200">{td.train_name || td.train_id}</td>
                          <td className="p-2.5 capitalize">{td.category}</td>
                          <td className="p-2.5">{`${td.baseline_delay_min.toFixed(0)} min`}</td>
                          <td className="p-2.5">{`${td.what_if_delay_min.toFixed(0)} min`}</td>
                          <td className={`p-2.5 font-bold ${td.delta_delay_min > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                            {`${td.delta_delay_min > 0 ? '+' : ''}${td.delta_delay_min.toFixed(0)} min`}
                          </td>
                          <td className="p-2.5 text-amber-300">
                            {td.energy_loss_kwh > 0 ? `${td.energy_loss_kwh.toFixed(0)} kWh` : '0 kWh'}
                          </td>
                          <td className="p-2.5">
                            {td.crew_duty_exceeded ? (
                              <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-[10px] font-bold text-red-400">
                                ⚠️ HOURS EXPIRED
                              </span>
                            ) : (
                              <span className="text-emerald-400 text-[11px]">✓ Normal</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {error && (
                <div className="p-3 rounded-lg bg-red-500/20 text-red-300 text-xs border border-red-500/40">
                  {error}
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={onClose}
                  className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700"
                >
                  {lang === 'hi' ? 'बंद करें (रद्द करें)' : 'Discard What-If'}
                </button>
                {(onApplyAdvisory || onScenarioCommitted) && (
                  <button
                    onClick={() => {
                      onApplyAdvisory?.(result.what_if_schedule);
                      onScenarioCommitted?.(result.what_if_schedule);
                      onClose();
                    }}
                    className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-500"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    <span>{lang === 'hi' ? 'एडवाइजरी ड्राफ्ट में लागू करें' : 'Apply to Advisory Draft'}</span>
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
