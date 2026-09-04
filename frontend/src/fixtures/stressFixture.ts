import type {
  NetworkGeometryResponse,
  Scenario,
  TrackBlock,
  Train,
  MaintenanceJob,
  Resource,
  TrackGeometry,
  StationNode,
  SignalMarker,
  OHEMast,
  ConflictItem,
  AssetHealthRecord,
  Coordinate3D
} from '../api/types';

/**
 * Generates a deterministic, large-scale railway corridor stress fixture:
 * - 1,000 track blocks
 * - 500 stations/junctions
 * - 2,000 trains
 * - 5,000 track and electrical assets
 * - 2,000 operational conflict markers
 * - 10,000 OHE masts
 */
export function generateStressNetworkFixture(): {
  geometry: NetworkGeometryResponse;
  scenario: Scenario;
  assets: AssetHealthRecord[];
} {
  const NUM_BLOCKS = 1000;
  const NUM_STATIONS = 500;
  const NUM_TRAINS = 2000;
  const NUM_ASSETS = 5000;
  const NUM_CONFLICTS = 2000;
  const NUM_OHE_MASTS = 10000;

  const totalLengthKm = NUM_BLOCKS * 5.0; // 5,000 km network

  // 1. Blocks
  const blocks: TrackBlock[] = [];
  const tracks: TrackGeometry[] = [];

  for (let i = 0; i < NUM_BLOCKS; i++) {
    const bId = `B${i + 1}`;
    const startKm = i * 5.0;
    const endKm = (i + 1) * 5.0;

    // Longitudinal X scaled from -400 to +400
    const startX = -400.0 + (startKm / totalLengthKm) * 800.0;
    const endX = -400.0 + (endKm / totalLengthKm) * 800.0;
    const startZ = Math.sin((i / NUM_BLOCKS) * Math.PI * 8) * 12.0;
    const endZ = Math.sin(((i + 1) / NUM_BLOCKS) * Math.PI * 8) * 12.0;

    const startCoord: Coordinate3D = { x: Math.round(startX * 10) / 10, y: 0.0, z: Math.round(startZ * 10) / 10 };
    const endCoord: Coordinate3D = { x: Math.round(endX * 10) / 10, y: 0.0, z: Math.round(endZ * 10) / 10 };

    blocks.push({
      id: bId,
      chainage_start: startKm,
      chainage_end: endKm,
      description: `Corridor Sector ${i + 1}`,
      speed_restriction_kmh: 110.0,
      track_type: 'Mainline',
      electrification_status: '25kV AC',
      signaling_type: 'Automatic'
    });

    tracks.push({
      id: `TRACK_${bId}`,
      block_id: bId,
      entity_type: 'track',
      name: `Block ${bId} Section`,
      start_coord: startCoord,
      end_coord: endCoord,
      path_points: [
        startCoord,
        {
          x: Math.round(((startX + endX) / 2) * 10) / 10,
          y: 0.2,
          z: Math.round(((startZ + endZ) / 2) * 10) / 10
        },
        endCoord
      ],
      length_km: 5.0,
      chainage_start: startKm,
      chainage_end: endKm,
      elevation_profile: [0.0, 0.2, 0.0],
      track_type: 'Mainline',
      electrification: '25kV AC',
      gauge: 'Broad Gauge 1676mm',
      speed_limit_kmh: 130.0,
      geometry_source: 'synthetic',
      geometry_schema_version: '1.0.0',
      schema_version: '1.0.0'
    });
  }

  // 2. Stations & Junctions
  const nodes: StationNode[] = [];
  for (let i = 0; i < NUM_STATIONS; i++) {
    const km = (i / NUM_STATIONS) * totalLengthKm;
    const x = -400.0 + (km / totalLengthKm) * 800.0;
    const z = Math.sin((i / NUM_STATIONS) * Math.PI * 8) * 12.0;
    const isJunction = i % 5 === 0;

    nodes.push({
      id: `STN_${i + 1}`,
      name: `Station ${i + 1}${isJunction ? ' Jn' : ''}`,
      code: `S${i + 1}`,
      entity_type: isJunction ? 'junction' : 'station',
      position: { x: Math.round(x * 10) / 10, y: 0.0, z: Math.round(z * 10) / 10 },
      chainage_km: Math.round(km * 10) / 10,
      node_type: isJunction ? 'junction' : 'station',
      platforms: isJunction ? 4 : 2,
      connected_blocks: [`B${Math.min(NUM_BLOCKS, Math.floor((km / totalLengthKm) * NUM_BLOCKS) + 1)}`],
      geometry_source: 'synthetic',
      geometry_schema_version: '1.0.0',
      schema_version: '1.0.0'
    });
  }

  // 3. Trains
  const trains: Train[] = [];
  for (let i = 0; i < NUM_TRAINS; i++) {
    const isPremium = i % 8 === 0;
    const startHour = (i % 24) * 0.9;
    const dur = isPremium ? 2.5 : 5.0;
    const routeStart = (i * 3) % (NUM_BLOCKS - 10);
    const route = [`B${routeStart + 1}`, `B${routeStart + 2}`, `B${routeStart + 3}`, `B${routeStart + 4}`];

    trains.push({
      id: `TR_${i + 1}`,
      name: isPremium ? `Vande Bharat Exp ${22000 + i}` : `Goods Freight ${54000 + i}`,
      category: isPremium ? 'premium' : 'freight',
      scheduled_start: startHour,
      scheduled_end: startHour + dur,
      route,
      min_travel_times: { [route[0]]: 0.5, [route[1]]: 0.5, [route[2]]: 0.5, [route[3]]: 0.5 },
      max_speed_kmh: isPremium ? 130.0 : 75.0
    });
  }

  // 4. Assets
  const assets: AssetHealthRecord[] = [];
  for (let i = 0; i < NUM_ASSETS; i++) {
    const km = (i / NUM_ASSETS) * totalLengthKm;
    const bIdx = Math.min(NUM_BLOCKS, Math.floor((km / totalLengthKm) * NUM_BLOCKS) + 1);
    const isCrit = i % 20 === 0;

    const x = -400.0 + (km / totalLengthKm) * 800.0;
    const z = (i % 2 === 0 ? 2.5 : 0.0) + Math.sin((km / totalLengthKm) * Math.PI * 8) * 12.0;
    const pos = { x: Math.round(x * 10) / 10, y: 1.2, z: Math.round(z * 10) / 10 };

    assets.push({
      asset_id: `AST_${i + 1}`,
      block_id: `B${bIdx}`,
      name: `Track Circuit & Point ${i + 1}`,
      asset_type: i % 2 === 0 ? 'Point Machine' : 'OHE Mast',
      chainage_start_km: Math.round(km * 10) / 10,
      chainage_end_km: Math.round((km + 0.1) * 10) / 10,
      health_score: isCrit ? 42.0 : 88.0,
      defect_severity: isCrit ? 'Critical' : 'Minor',
      degradation_velocity: 0.15,
      observed_defect_type: isCrit ? 'Insulator Flashover' : 'Normal Wear',
      model_predicted_risk: isCrit ? 0.85 : 0.12,
      last_ultrasonic_test: '2026-08-15',
      days_overdue: isCrit ? 14 : 0,
      position: pos,
      coordinates: pos,
      geometry_source: 'synthetic',
      geometry_schema_version: '1.0.0'
    });
  }

  // 5. Conflicts
  const conflicts: ConflictItem[] = [];
  for (let i = 0; i < NUM_CONFLICTS; i++) {
    const km = (i / NUM_CONFLICTS) * totalLengthKm;
    const x = -400.0 + (km / totalLengthKm) * 800.0;
    const z = Math.sin((i / NUM_CONFLICTS) * Math.PI * 8) * 12.0;
    const bIdx = Math.min(NUM_BLOCKS, Math.floor((km / totalLengthKm) * NUM_BLOCKS) + 1);

    conflicts.push({
      id: `CONF_${i + 1}`,
      entity_type: 'conflict',
      conflict_type: i % 3 === 0 ? 'premium_train_risk' : 'train_vs_block',
      severity: i % 5 === 0 ? 'CRITICAL' : 'MAJOR',
      block_id: `B${bIdx}`,
      title: `Operational Risk ${i + 1}`,
      description: `High traffic density contention on Sector ${bIdx}.`,
      affected_jobs: [],
      affected_trains: [`TR_${(i % NUM_TRAINS) + 1}`],
      time_window: { start: 2.0, end: 6.0 },
      suggested_resolution: 'Apply speed caution order and signal lock.',
      position: { x: Math.round(x * 10) / 10, y: 1.2, z: Math.round(z * 10) / 10 },
      geometry_source: 'synthetic',
      geometry_schema_version: '1.0.0',
      schema_version: '1.0.0'
    });
  }

  // 6. OHE Masts
  const oheMasts: OHEMast[] = [];
  for (let i = 0; i < NUM_OHE_MASTS; i++) {
    const km = (i / NUM_OHE_MASTS) * totalLengthKm;
    const x = -400.0 + (km / totalLengthKm) * 800.0;
    const z = Math.sin((i / NUM_OHE_MASTS) * Math.PI * 8) * 12.0 + 2.2;
    const bIdx = Math.min(NUM_BLOCKS, Math.floor((km / totalLengthKm) * NUM_BLOCKS) + 1);

    oheMasts.push({
      id: `MAST_${i + 1}`,
      entity_type: 'ohe_mast',
      block_id: `B${bIdx}`,
      position: { x: Math.round(x * 10) / 10, y: 0.0, z: Math.round(z * 10) / 10 },
      chainage_km: Math.round(km * 10) / 10,
      catenary_height_m: 5.5,
      is_isolated: i % 100 === 0,
      geometry_source: 'synthetic',
      geometry_schema_version: '1.0.0',
      schema_version: '1.0.0'
    });
  }

  // 7. Signals
  const signals: SignalMarker[] = [];
  for (let i = 0; i < NUM_BLOCKS; i++) {
    const km = i * 5.0;
    const x = -400.0 + (km / totalLengthKm) * 800.0;
    const z = Math.sin((i / NUM_BLOCKS) * Math.PI * 8) * 12.0 + 1.5;

    signals.push({
      id: `SIG_${i + 1}_UP`,
      entity_type: 'signal',
      block_id: `B${i + 1}`,
      chainage_km: km + 0.5,
      position: { x: Math.round(x * 10) / 10, y: 0.0, z: Math.round(z * 10) / 10 },
      aspect: i % 4 === 0 ? 'caution' : 'clear',
      direction: 'UP',
      geometry_source: 'synthetic',
      geometry_schema_version: '1.0.0',
      schema_version: '1.0.0'
    });
  }

  // Resources & Jobs
  const resources: Resource[] = [
    { id: 'R_BCM', name: 'Ballast Cleaning Machine', capacity: 10, department: 'Engineering' },
    { id: 'R_TIE', name: 'Tie Tamper', capacity: 8, department: 'Engineering' },
    { id: 'R_CREW_OHE', name: 'OHE Maintenance Crew', capacity: 15, department: 'OHE' },
    { id: 'R_CREW_SIG', name: 'Signal Testing Crew', capacity: 12, department: 'S&T' }
  ];

  const jobs: MaintenanceJob[] = [];
  for (let i = 0; i < 50; i++) {
    jobs.push({
      id: `JOB_STRESS_${i + 1}`,
      department: i % 3 === 0 ? 'Engineering' : i % 3 === 1 ? 'OHE' : 'S&T',
      block_id: `B${(i * 15) + 1}`,
      duration: 2.0,
      required_resources: { 'R_BCM': 1 },
      tci_inputs: { safety_severity: 0.8, traffic_impact: 0.6, degradation_indicator: 0.7, overdue_days: 10 },
      is_fixed: false
    });
  }

  const scenario: Scenario = {
    blocks,
    trains,
    jobs,
    resources,
    fixed_blocks: []
  };

  const geometry: NetworkGeometryResponse = {
    geometry_schema_version: '1.0.0',
    coordinate_system: {
      name: 'LOCAL_CORRIDOR',
      crs: 'LOCAL_CORRIDOR',
      units: 'meters',
      axis_order: ['x', 'y', 'z'],
      handedness: 'right-handed',
      origin_description: 'Synthetic local origin for the bounded railway division',
      geometry_source: 'synthetic'
    },
    division: 'Prayagraj Stress Division (PRYJ-1000)',
    line_name: 'Super-Dense 1,000-Block Stress Corridor',
    total_length_km: totalLengthKm,
    is_synthetic: true,
    geometry_source: 'synthetic',
    coordinate_convention: 'X: corridor longitudinal (m), Y: elevation (m), Z: lateral offset (m)',
    schema_version: '1.0.0',
    nodes,
    tracks,
    signals,
    ohe_masts: oheMasts,
    blocks,
    conflicts,
    junctions: [],
    assets,
    disconnected_components: []
  };

  return { geometry, scenario, assets };
}
