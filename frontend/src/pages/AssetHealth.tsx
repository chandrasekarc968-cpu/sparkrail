import { useEffect, useState } from 'react';
import { ApiClient } from '../api/client';
import type { AssetHealthRecord } from '../api/types';
import { useAppContext } from '../context/useAppContext';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { ErrorBanner } from '../components/ui/ErrorBanner';
import { Skeleton } from '../components/ui/Skeleton';
import {
  Cpu,
  Eye,
  ArrowRight
} from 'lucide-react';
import { Link } from 'react-router-dom';

export function AssetHealth() {
  const { lastRefresh, isDemoMode } = useAppContext();
  const [assets, setAssets] = useState<AssetHealthRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>("AST-TRK-B6-12");

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await ApiClient.getAssetHealth();
      setAssets(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load asset health records.");
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
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-bold">Asset Health</h1>
        <ErrorBanner
          title="Asset Condition Pipeline Error"
          message={error}
          onRetry={() => void loadData()}
        />
      </div>
    );
  }

  const criticalCount = assets.filter((a) => a.defect_severity === "Critical").length;
  const majorCount = assets.filter((a) => a.defect_severity === "Major").length;
  const selectedAsset = assets.find((a) => a.asset_id === selectedAssetId) || assets[0];

  // Highest degradation section
  const highestDegradation = [...assets].sort((a, b) => b.degradation_velocity - a.degradation_velocity)[0];

  return (
    <div className="space-y-6">
      {/* Header & Legend */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <h1 className="text-2xl font-extrabold tracking-tight text-neutral-950">
              Track & Traction Asset Health
            </h1>
            <Badge variant="outline" size="sm" className="font-mono">
              TMS / TRC INTEGRATED
            </Badge>
            {isDemoMode && (
              <Badge variant="warning" size="sm">
                SYNTHETIC SENSOR FEEDS
              </Badge>
            )}
          </div>
          <p className="text-xs text-neutral-500 mt-0.5">
            Surveillance of ultrasonic flaw detection (USFD), track geometry indices, and degradation velocity.
          </p>
        </div>

        {/* Legend: Observed vs Predicted */}
        <div className="flex items-center space-x-3 bg-white p-2 rounded border border-neutral-200 text-xs">
          <span className="flex items-center gap-1.5 font-medium text-neutral-700">
            <Eye className="w-3.5 h-3.5 text-op-blue" />
            <span>Observed (TMS Sensor)</span>
          </span>
          <span className="text-neutral-300">|</span>
          <span className="flex items-center gap-1.5 font-medium text-neutral-700">
            <Cpu className="w-3.5 h-3.5 text-accent-600" />
            <span>Predicted (AI Degradation)</span>
          </span>
        </div>
      </div>

      {/* Top 4 KPI Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-xs text-neutral-500 uppercase font-bold">Critical Defects</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0">
            <div className="text-2xl font-bold font-mono text-op-red tabular-nums">{criticalCount} Critical</div>
            <p className="text-[11px] text-op-red-dark mt-1">+{majorCount} major defects tracked</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-xs text-neutral-500 uppercase font-bold">Highest Degradation</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0">
            <div className="text-2xl font-bold font-mono text-neutral-900 tabular-nums">
              {highestDegradation ? `${highestDegradation.degradation_velocity.toFixed(2)} mm/MGT` : "--"}
            </div>
            <p className="text-[11px] text-neutral-500 mt-1 font-mono">
              Section {highestDegradation?.block_id} ({highestDegradation?.name})
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-xs text-neutral-500 uppercase font-bold">Overdue Maintenance</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0">
            <div className="text-2xl font-bold font-mono text-amber-700 tabular-nums">
              {assets.filter((a) => a.days_overdue > 0).length} Assets
            </div>
            <p className="text-[11px] text-neutral-500 mt-1">Escalating TCI overdue penalty</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-xs text-neutral-500 uppercase font-bold">Health Index Mean</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0">
            <div className="text-2xl font-bold font-mono text-op-green font-extrabold tabular-nums">
              {(assets.reduce((acc, a) => acc + a.health_score, 0) / assets.length).toFixed(1)} / 100
            </div>
            <p className="text-[11px] text-neutral-500 mt-1">Corridor average condition</p>
          </CardContent>
        </Card>
      </div>

      {/* Schematic Heatmap Across Sections B1-B8 */}
      <Card>
        <CardHeader className="py-3 px-5 border-b border-neutral-100 flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-sm">Linear Asset Risk Heatmap (Chainage 0.0 - 80.0 km)</CardTitle>
            <p className="text-[11px] text-neutral-500">
              Color intensity depicts combined physical flaw severity and AI-predicted structural failure probability
            </p>
          </div>
          <span className="text-xs font-mono text-neutral-500">8 Track Sections</span>
        </CardHeader>
        <CardContent className="p-4 bg-neutral-50">
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5">
            {Array.from({ length: 8 }).map((_, i) => {
              const blockId = `B${i + 1}`;
              const blockAssets = assets.filter((a) => a.block_id === blockId);
              const hasCritical = blockAssets.some((a) => a.defect_severity === "Critical");
              const hasMajor = blockAssets.some((a) => a.defect_severity === "Major");

              let bg = "bg-op-green-light/40 border-op-green/30 text-op-green-dark";
              let statusText = "NORMAL";
              if (hasCritical) {
                bg = "bg-op-red-light/50 border-op-red/40 text-op-red-dark";
                statusText = "CRITICAL";
              } else if (hasMajor) {
                bg = "bg-op-amber-light/50 border-op-amber/40 text-op-amber-dark";
                statusText = "WARNING";
              }

              return (
                <div
                  key={blockId}
                  className={`p-3 rounded border flex flex-col justify-between h-28 ${bg} transition-all`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-extrabold text-sm">{blockId}</span>
                    <span className="text-[9px] font-bold uppercase tracking-wider">{statusText}</span>
                  </div>
                  <div className="text-[10px] space-y-0.5 mt-2">
                    <p className="font-mono">{i * 10}-{(i + 1) * 10} km</p>
                    <p className="font-semibold">{blockAssets.length} Defect Point{blockAssets.length > 1 ? 's' : ''}</p>
                  </div>
                  <div className="w-full bg-black/10 h-1.5 rounded-full overflow-hidden mt-1">
                    <div
                      className={`h-full ${hasCritical ? "bg-op-red" : hasMajor ? "bg-amber-600" : "bg-op-green"}`}
                      style={{ width: `${hasCritical ? 90 : hasMajor ? 60 : 25}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Main Asset Table & Evidence Drilldown Split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Table of Assets (8 Columns) */}
        <Card className="lg:col-span-8 flex flex-col overflow-hidden">
          <CardHeader className="py-3 px-5 border-b border-neutral-100 flex flex-row items-center justify-between">
            <CardTitle className="text-sm">Monitored Infrastructure Register</CardTitle>
            <span className="text-xs text-neutral-500 font-mono">{assets.length} Monitored Assets</span>
          </CardHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs whitespace-nowrap">
              <thead className="bg-neutral-50 border-b border-neutral-200 text-neutral-600 uppercase font-semibold text-[10px] tracking-wide">
                <tr>
                  <th className="px-4 py-3">Asset ID / Name</th>
                  <th className="px-4 py-3">Section</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Health Score</th>
                  <th className="px-4 py-3">Defect Severity</th>
                  <th className="px-4 py-3">Degradation</th>
                  <th className="px-4 py-3">Predicted Risk</th>
                  <th className="px-4 py-3 text-right">Drilldown</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {assets.map((asset) => {
                  const isSelected = selectedAssetId === asset.asset_id;
                  return (
                    <tr
                      key={asset.asset_id}
                      onClick={() => setSelectedAssetId(asset.asset_id)}
                      className={`hover:bg-neutral-50 transition-colors cursor-pointer ${
                        isSelected ? "bg-accent-50/20 font-semibold" : ""
                      }`}
                    >
                      <td className="px-4 py-3">
                        <div className="font-mono font-bold text-neutral-900">{asset.asset_id}</div>
                        <div className="text-[11px] text-neutral-500 font-normal">{asset.name}</div>
                      </td>
                      <td className="px-4 py-3 font-mono text-neutral-700">
                        {asset.block_id} ({asset.chainage_start_km}-{asset.chainage_end_km} km)
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" size="sm">
                          {asset.asset_type}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 font-mono font-bold tabular-nums">
                        <span
                          className={
                            asset.health_score < 40
                              ? "text-op-red"
                              : asset.health_score < 70
                              ? "text-amber-600"
                              : "text-op-green"
                          }
                        >
                          {asset.health_score} / 100
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <Badge
                          variant={
                            asset.defect_severity === "Critical"
                              ? "danger"
                              : asset.defect_severity === "Major"
                              ? "warning"
                              : "neutral"
                          }
                          size="sm"
                        >
                          {asset.defect_severity}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 font-mono tabular-nums text-neutral-600">
                        {asset.degradation_velocity.toFixed(2)} mm/MGT
                      </td>
                      <td className="px-4 py-3 font-mono tabular-nums">
                        <span className="font-bold text-accent-600">
                          {(asset.model_predicted_risk * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedAssetId(asset.asset_id);
                          }}
                          className="text-accent-600 hover:text-accent-700 min-h-[32px] px-2 text-xs"
                        >
                          Inspect →
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Selected Asset Evidence & AI Prediction Panel (4 Columns) */}
        <Card className="lg:col-span-4">
          <CardHeader className="py-3 px-5 border-b border-neutral-100">
            <CardTitle className="text-xs uppercase tracking-wider text-neutral-700 font-bold flex items-center justify-between">
              <span>Sensor & AI Evidence</span>
              <span className="font-mono text-accent-600">{selectedAsset.asset_id}</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-4 text-xs">
            {/* Header info */}
            <div className="p-3 bg-neutral-50 rounded border border-neutral-200">
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-bold text-neutral-900">{selectedAsset.name}</p>
                  <p className="text-[11px] text-neutral-500 font-mono">
                    Track Section {selectedAsset.block_id} | Chainage {selectedAsset.chainage_start_km} to {selectedAsset.chainage_end_km} km
                  </p>
                </div>
                <Badge
                  variant={selectedAsset.defect_severity === "Critical" ? "danger" : "warning"}
                  size="sm"
                >
                  {selectedAsset.defect_severity}
                </Badge>
              </div>
            </div>

            {/* Observed Sensor Evidence */}
            <div className="space-y-1.5">
              <div className="flex items-center space-x-1.5 font-bold text-neutral-800 uppercase text-[10px] tracking-wider">
                <Eye className="w-3.5 h-3.5 text-op-blue" />
                <span>Observed Physical Evidence (TMS / TRC)</span>
              </div>
              <div className="p-3 bg-blue-50/40 border border-blue-200 rounded text-blue-950 space-y-1">
                <p className="font-semibold text-xs">{selectedAsset.observed_defect_type}</p>
                <div className="flex justify-between text-[11px] text-blue-800 font-mono pt-1 border-t border-blue-200/50">
                  <span>Last Inspection: {selectedAsset.last_ultrasonic_test}</span>
                  <span>Overdue: {selectedAsset.days_overdue} days</span>
                </div>
              </div>
            </div>

            {/* AI Model Prediction */}
            <div className="space-y-1.5">
              <div className="flex items-center space-x-1.5 font-bold text-neutral-800 uppercase text-[10px] tracking-wider">
                <Cpu className="w-3.5 h-3.5 text-accent-600" />
                <span>AI Degradation Model Prediction</span>
              </div>
              <div className="p-3 bg-accent-50/40 border border-accent-600/30 rounded text-neutral-900 space-y-2">
                <div className="flex justify-between items-center">
                  <span>Predicted Failure Probability</span>
                  <span className="font-mono font-extrabold text-accent-600 text-sm">
                    {(selectedAsset.model_predicted_risk * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="w-full bg-neutral-200 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-accent-600 h-full rounded-full"
                    style={{ width: `${selectedAsset.model_predicted_risk * 100}%` }}
                  />
                </div>
                <p className="text-[11px] text-neutral-600 leading-snug">
                  Degradation velocity is {selectedAsset.degradation_velocity} mm/MGT. Model projects threshold exceedance within 14 days without block possession.
                </p>
              </div>
            </div>

            {/* Associated Maintenance Task Drilldown */}
            {selectedAsset.associated_job_id && (
              <div className="pt-2 border-t border-neutral-100">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-[10px] uppercase font-bold text-neutral-500">Mitigating Action</span>
                  <Badge variant="outline" size="sm" className="font-mono">
                    {selectedAsset.associated_job_id}
                  </Badge>
                </div>
                <Link
                  to={`/jobs`}
                  className="w-full inline-flex items-center justify-center py-2 px-3 bg-neutral-900 text-white rounded text-xs font-semibold hover:bg-neutral-800 transition-colors min-h-[36px]"
                >
                  Inspect Mitigating Maintenance Job <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                </Link>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}