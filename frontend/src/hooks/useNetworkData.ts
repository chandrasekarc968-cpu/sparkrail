import { useState, useEffect, useCallback } from 'react';
import { ApiClient } from '../api/client';
import type {
  NetworkGeometryResponse,
  Scenario,
  AssetHealthRecord,
  PlanningCapabilitiesResponse
} from '../api/types';

export function useNetworkData() {
  const [geometry, setGeometry] = useState<NetworkGeometryResponse | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [assets, setAssets] = useState<AssetHealthRecord[]>([]);
  const [capabilities, setCapabilities] = useState<PlanningCapabilitiesResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [geomRes, scnRes, astRes, capRes] = await Promise.all([
        ApiClient.getNetworkGeometry(),
        ApiClient.getScenario(),
        ApiClient.getAssetHealth(),
        ApiClient.getPlanningCapabilities()
      ]);
      setGeometry(geomRes);
      setScenario(scnRes);
      setAssets(astRes);
      setCapabilities(capRes);
      setLastRefreshed(new Date());
    } catch (err: unknown) {
      console.error("Failed to load 3D network data:", err);
      setError(err instanceof Error ? err.message : "Failed to load railway network data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    geometry,
    scenario,
    assets,
    capabilities,
    loading,
    error,
    lastRefreshed,
    refresh: fetchData,
    isDemo: ApiClient.isDemoMode()
  };
}
