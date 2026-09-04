import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiClient, setDemoModeEnabled } from '../api/client';
import {
  validateNetworkGeometryContract,
  GeometryContractError,
  CANONICAL_GEOMETRY_SCHEMA_VERSION,
  CANONICAL_COORDINATE_SYSTEM
} from '../api/geometryValidator';
import { mockNetworkGeometry, mockAssetHealth } from '../api/mockData';
import { generateStressNetworkFixture } from '../fixtures/stressFixture';
import type { NetworkGeometryResponse } from '../api/types';

describe('Geometry Schema Contract (Frontend)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('validateNetworkGeometryContract', () => {
    it('validates canonical mock network geometry without error', () => {
      expect(() => {
        validateNetworkGeometryContract(mockNetworkGeometry, false);
      }).not.toThrow();
    });

    it('validates stress test fixture network geometry without error', () => {
      const stressGeometry = generateStressNetworkFixture().geometry;
      expect(() => {
        validateNetworkGeometryContract(stressGeometry, false);
      }).not.toThrow();
    });

    it('enforces geometry_schema_version 1.0.0 and rejects missing or incompatible version', () => {
      const invalidVersionGeo = {
        ...mockNetworkGeometry,
        geometry_schema_version: '2.0.0'
      } as unknown as NetworkGeometryResponse;

      expect(() => {
        validateNetworkGeometryContract(invalidVersionGeo, false);
      }).toThrowError(GeometryContractError);

      try {
        validateNetworkGeometryContract(invalidVersionGeo, false);
      } catch (e) {
        expect(e).toBeInstanceOf(GeometryContractError);
        const err = e as GeometryContractError;
        expect(err.schemaVersion).toBe('2.0.0');
        expect(err.message).toContain('1.0.0');
        expect(err.message).toContain('2.0.0');
      }

      const missingVersionGeo = {
        ...mockNetworkGeometry,
        geometry_schema_version: undefined
      } as unknown as NetworkGeometryResponse;

      expect(() => {
        validateNetworkGeometryContract(missingVersionGeo, false);
      }).toThrowError(GeometryContractError);
    });

    it('enforces coordinate_system contract properties', () => {
      const invalidCrsGeo = {
        ...mockNetworkGeometry,
        coordinate_system: {
          ...CANONICAL_COORDINATE_SYSTEM,
          crs: 'EPSG:4326' // GPS coordinates rejected! Must be LOCAL_CORRIDOR
        }
      } as unknown as NetworkGeometryResponse;

      expect(() => {
        validateNetworkGeometryContract(invalidCrsGeo, false);
      }).toThrowError(/LOCAL_CORRIDOR/);

      const invalidUnitsGeo = {
        ...mockNetworkGeometry,
        coordinate_system: {
          ...CANONICAL_COORDINATE_SYSTEM,
          units: 'feet'
        }
      } as unknown as NetworkGeometryResponse;

      expect(() => {
        validateNetworkGeometryContract(invalidUnitsGeo, false);
      }).toThrowError(/meters/);

      const invalidHandednessGeo = {
        ...mockNetworkGeometry,
        coordinate_system: {
          ...CANONICAL_COORDINATE_SYSTEM,
          handedness: 'left-handed'
        }
      } as unknown as NetworkGeometryResponse;

      expect(() => {
        validateNetworkGeometryContract(invalidHandednessGeo, false);
      }).toThrowError(/right-handed/);
    });

    it('enforces zero-invention rule in non-demo mode (isDemo = false)', () => {
      const missingCoordNodeGeo: NetworkGeometryResponse = {
        ...mockNetworkGeometry,
        nodes: [
          {
            id: 'NODE_INV',
            name: 'Invented Station',
            code: 'INV',
            chainage_km: 10,
            node_type: 'station',
            platforms: 2,
            connected_blocks: ['B1']
            // position and coordinates intentionally omitted
          } as unknown as NetworkGeometryResponse['nodes'][0]
        ]
      };

      expect(() => {
        validateNetworkGeometryContract(missingCoordNodeGeo, false);
      }).toThrowError(/Node 'NODE_INV' has non-finite or missing coordinates/);

      const missingCoordTrackGeo: NetworkGeometryResponse = {
        ...mockNetworkGeometry,
        tracks: [
          {
            block_id: 'TRK_INV',
            line_id: 'L1',
            chainage_start: 0,
            chainage_end: 10,
            speed_limit_kmh: 110,
            gradient_permille: 0,
            path_points: []
            // start_coord and end_coord intentionally omitted
          } as unknown as NetworkGeometryResponse['tracks'][0]
        ]
      };

      expect(() => {
        validateNetworkGeometryContract(missingCoordTrackGeo, false);
      }).toThrowError(/Track 'TRK_INV' has non-finite or missing 'start_coord'/);
    });

    it('allows graceful operation in demo mode when coordinates are missing', () => {
      const demoMissingCoordGeo: NetworkGeometryResponse = {
        ...mockNetworkGeometry,
        nodes: [
          {
            id: 'NODE_DEMO',
            name: 'Demo Station',
            code: 'DEM',
            chainage_km: 10,
            node_type: 'station',
            platforms: 2,
            connected_blocks: ['B1']
          } as unknown as NetworkGeometryResponse['nodes'][0]
        ]
      };

      // In demo mode, zero-invention strict check is bypassed with warning
      expect(() => {
        validateNetworkGeometryContract(demoMissingCoordGeo, true);
      }).not.toThrow();
    });
  });

  describe('ApiClient Contract Verification', () => {
    it('getNetworkGeometry returns valid geometry with schema version 1.0.0 and canonical assets in demo mode', async () => {
      setDemoModeEnabled(true);
      const geo = await ApiClient.getNetworkGeometry();

      expect(geo.geometry_schema_version).toBe(CANONICAL_GEOMETRY_SCHEMA_VERSION);
      expect(geo.coordinate_system).toBeDefined();
      expect(geo.coordinate_system.crs).toBe('LOCAL_CORRIDOR');
      expect(geo.coordinate_system.units).toBe('meters');
      expect(geo.coordinate_system.handedness).toBe('right-handed');
      expect(geo.assets).toBeDefined();
      expect(geo.assets?.length).toBeGreaterThan(0);

      // Verify every asset has canonical 3D coordinates
      for (const asset of geo.assets || []) {
        const pos = asset.position || asset.coordinates;
        expect(pos).toBeDefined();
        expect(typeof pos?.x).toBe('number');
        expect(typeof pos?.y).toBe('number');
        expect(typeof pos?.z).toBe('number');
      }
    });

    it('getHealth exposes geometry_schema_version 1.0.0', async () => {
      setDemoModeEnabled(true);
      const health = await ApiClient.getHealth();
      expect(health.geometry_schema_version).toBe(CANONICAL_GEOMETRY_SCHEMA_VERSION);
    });

    it('getPlanningCapabilities exposes geometry_schema_version 1.0.0 and coordinate_system', async () => {
      setDemoModeEnabled(true);
      const caps = await ApiClient.getPlanningCapabilities();
      expect(caps.geometry_schema_version).toBe(CANONICAL_GEOMETRY_SCHEMA_VERSION);
      expect(caps.coordinate_system).toBeDefined();
      expect(caps.coordinate_system?.crs).toBe('LOCAL_CORRIDOR');
    });

    it('mockAssetHealth contains canonical coordinates and schema version 1.0.0', () => {
      for (const asset of mockAssetHealth) {
        expect(asset.geometry_schema_version).toBe(CANONICAL_GEOMETRY_SCHEMA_VERSION);
        expect(asset.position).toBeDefined();
        expect(typeof asset.position?.x).toBe('number');
        expect(typeof asset.position?.y).toBe('number');
        expect(typeof asset.position?.z).toBe('number');
      }
    });

    it('throws ApiError wrapping GeometryContractError in non-demo mode when backend response violates schema contract', async () => {
      setDemoModeEnabled(false);

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          ...mockNetworkGeometry,
          geometry_schema_version: '2.0.0'
        })
      } as unknown as Response);

      await expect(ApiClient.getNetworkGeometry()).rejects.toThrow(
        /Incompatible geometry_schema_version '2.0.0'/
      );

      setDemoModeEnabled(true);
    });
  });
});
