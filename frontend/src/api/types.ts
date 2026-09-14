export type Department = "Engineering" | "OHE" | "S&T";

export type TrainCategory = "premium" | "express" | "freight";

export type JobStatus = "scheduled" | "unscheduled" | "in_progress" | "completed" | "conflict";

export interface Resource {
  id: string;
  name: string;
  capacity: number;
  department?: Department;
  available_units?: number;
}

export interface TrackBlock {
  id: string;
  chainage_start: number;
  chainage_end: number;
  description: string;
  track_id?: string;
  start_station?: string;
  end_station?: string;
  length_km?: number;
  speed_limit_kmh?: number;
  track_type?: "Mainline" | "Loop" | "Siding";
  speed_restriction_kmh?: number;
  electrification_status?: "25kV AC" | "Non-Electrified";
  signaling_type?: "Automatic" | "Absolute Block";
}

export interface Train {
  id: string;
  name?: string;
  category: TrainCategory;
  priority?: number;
  origin?: string;
  destination?: string;
  scheduled_start: number;
  scheduled_end: number;
  route: string[];
  min_travel_times?: Record<string, number>;
  max_speed_kmh?: number;
  current_block?: string;
  current_delay_min?: number;
  gross_tonnage_tonnes?: number;
  is_loaded_freight?: boolean;
  train_type?: string;
  crew_duty_remaining_hours?: number;
  crew_duty_expiry_timestamp?: string;
  designated_crew_stations?: string[];
}

export interface TCIInputs {
  safety_severity: number;
  traffic_impact: number;
  degradation_indicator: number;
  overdue_days: number;
}

export interface TCIExplanation {
  safety_component: number;
  delay_component: number;
  degradation_component: number;
  overdue_component: number;
  raw_inputs: TCIInputs;
  formula_breakdown?: string;
}

export interface MaintenanceJob {
  id: string;
  department: Department;
  block_id: string;
  duration: number;
  required_resources: Record<string, number>;
  tci_inputs: TCIInputs;
  is_fixed?: boolean;
  fixed_start?: number | null;
  job_type?: string;
  due_date?: string;
  safety_clearance_required?: string;
  chainage_km?: string;
  status?: JobStatus;
  preferred_start_window?: [number, number];
  urgency_score?: number;
}

export interface FixedMaintenanceBlock {
  id: string;
  block_id: string;
  start_time: number;
  end_time: number;
  reason?: string;
  department?: Department;
}

export interface ScheduleWindow {
  block_id: string;
  start_time: number;
  end_time: number;
  window_type: "maintenance" | "traffic" | "shadow";
}

export interface ScheduledJob {
  job_id: string;
  block_id: string;
  start_time: number;
  end_time: number;
  tci: number;
  department: Department;
  track_id?: string;
  is_shadow_block?: boolean;
  shadow_with_jobs?: string[];
  assigned_resources?: string[];
}

export interface UnscheduledJob {
  job_id: string;
  reason: string;
  conflict_with?: string;
  potential_window?: string;
}

export interface Scenario {
  id?: string;
  name?: string;
  blocks: TrackBlock[];
  trains: Train[];
  jobs: MaintenanceJob[];
  resources: Resource[];
  fixed_blocks: FixedMaintenanceBlock[];
  weather?: Record<string, unknown>;
  asset_telemetry?: Record<string, unknown>;
}

export interface KPIReport {
  bue_percent: number;
  bue_baseline_percent: number;
  sbr_percent: number;
  pii_delays: number;
  pii_baseline_delays: number;
  tci_coverage_percent: number;
  total_closure_hours: number;
  baseline_closure_hours: number;
  consolidated_blocks: number;
  mttg_minutes?: number;
  high_crit_completion_percent?: number;
  asset_downtime_reduction_percent?: number;
  solver_runtime_seconds?: number;
}

export interface OptimizedSchedule {
  scenario_id?: string;
  status: string;
  solver: string;
  scheduled_jobs: ScheduledJob[];
  unscheduled_jobs: UnscheduledJob[];
  train_delays: Record<string, number>;
  total_closure_time: number;
  objective_value: number;
  runtime_seconds?: number;
  kpi_metrics?: KPIReport;
  kpis?: Record<string, unknown>;
  conflicts?: ConflictItem[];
  shadow_block_groups?: ShadowBlockGroup[];
  is_fallback?: boolean;
  explainability?: Record<string, JobExplanation>;
}

export interface ScoredJob {
  job_id: string;
  tci: number;
  explanation: TCIExplanation;
}

export interface Coordinate3D {
  x: number;
  y: number;
  z: number;
}

export type Vector3D = Coordinate3D;

export type ValidationStatus =
  | "VALIDATED"
  | "SYNTHETIC"
  | "STALE"
  | "LOW_CONFIDENCE"
  | "INVALID"
  | "CONTRADICTORY"
  | "UNAVAILABLE";

export interface BaseEntityProvenance {
  source_system?: string;
  source_record_id?: string;
  geometry_source?: string;
  schema_version?: string;
  coordinate_reference_system?: string;
  source_timestamp?: string;
  ingestion_timestamp?: string;
  data_freshness_seconds?: number;
  confidence?: number;
  validation_status?: ValidationStatus;
  referenced_block_id?: string;
  referenced_track_section_id?: string;
}

export interface CoordinateSystemContract {
  name: "LOCAL_CORRIDOR" | string;
  crs: "LOCAL_CORRIDOR" | string;
  units: "meters";
  axis_order: string[];
  handedness: "right-handed";
  origin_description: string;
  geometry_source: "synthetic" | "surveyed";
  transform_version?: string;
  is_synthetic?: boolean;
}

export interface GeometryNode extends BaseEntityProvenance {
  id: string;
  entity_type?: string;
  coordinates?: Coordinate3D;
  position: Coordinate3D;
  chainage_km: number;
  referenced_block_id?: string;
  referenced_asset_id?: string;
  geometry_source?: string;
  geometry_schema_version?: string;
  schema_version?: string;
}

export interface StationNode extends GeometryNode {
  name: string;
  code: string;
  node_type: "station" | "junction" | "terminal";
  platforms: number;
  connected_blocks: string[];
}

export interface JunctionNode extends GeometryNode {
  name: string;
  code: string;
  diverging_blocks?: string[];
  switch_type?: string;
  interlocking_status?: string;
}

export interface TrackGeometry extends BaseEntityProvenance {
  id?: string;
  block_id: string;
  entity_type?: string;
  name: string;
  start_coord: Coordinate3D;
  end_coord: Coordinate3D;
  path_points: Coordinate3D[];
  length_km: number;
  chainage_start: number;
  chainage_end: number;
  elevation_profile: number[];
  track_type: string;
  electrification: string;
  gauge?: string;
  speed_limit_kmh: number;
  referenced_block_id?: string;
  geometry_source?: string;
  geometry_schema_version?: string;
  schema_version?: string;
}

export type GeometryTrack = TrackGeometry;

export interface TrackSection extends BaseEntityProvenance {
  id: string;
  block_id: string;
  line_name: string;
  track_direction: "UP" | "DOWN" | "BIDIRECTIONAL";
  chainage_start_km: number;
  chainage_end_km: number;
  length_km: number;
  start_coord: Coordinate3D;
  end_coord: Coordinate3D;
  path_points?: Coordinate3D[];
  speed_limit_kmh: number;
  electrification_status: string;
  gauge: string;
}

export interface TrackCenterline extends BaseEntityProvenance {
  id: string;
  corridor_name: string;
  chainage_start_km: number;
  chainage_end_km: number;
  centerline_points: Coordinate3D[];
  station_anchors: string[];
}

export interface Crossover extends BaseEntityProvenance {
  id: string;
  name: string;
  station_code: string;
  from_track_id: string;
  to_track_id: string;
  turnout_ratio: string;
  points_number: string;
  speed_limit_kmh: number;
  switch_position: "NORMAL" | "REVERSE";
  chainage_km: number;
  start_coord: Coordinate3D;
  end_coord: Coordinate3D;
}

export interface InterlockingZone extends BaseEntityProvenance {
  id: string;
  station_code: string;
  name: string;
  interlocking_type: string;
  controlled_signals: string[];
  controlled_points: string[];
  controlled_circuits: string[];
  status: string;
  chainage_start_km: number;
  chainage_end_km: number;
  boundary_coords: Coordinate3D[];
}

export interface TrackCircuit extends BaseEntityProvenance {
  id: string;
  track_id: string;
  block_id: string;
  chainage_start_km: number;
  chainage_end_km: number;
  is_occupied: boolean;
  circuit_type: string;
  coordinates: Coordinate3D;
}

export interface ElementarySection extends BaseEntityProvenance {
  id: string;
  section_code: string;
  name: string;
  feeding_post_id: string;
  associated_tracks: string[];
  associated_masts: string[];
  isolator_switch_ids: string[];
  is_energized: boolean;
  nominal_voltage_kv: number;
  chainage_start_km: number;
  chainage_end_km: number;
}

export interface FeedingPost extends BaseEntityProvenance {
  id: string;
  name: string;
  location_chainage_km: number;
  incoming_grid_voltage_kv: number;
  catenary_voltage_kv: number;
  is_operational: boolean;
  coordinates: Coordinate3D;
}

export interface IsolatorSwitch extends BaseEntityProvenance {
  id: string;
  switch_code: string;
  elementary_section_id: string;
  state: "OPEN" | "CLOSED";
  switch_type: string;
  chainage_km: number;
  coordinates: Coordinate3D;
}

export interface PossessionEntity extends BaseEntityProvenance {
  id: string;
  job_id: string;
  block_id: string;
  department: string;
  status: "PLANNED" | "SANCTIONED" | "GRANTED" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED" | "REJECTED";
  start_time_hours: number;
  end_time_hours: number;
  chainage_start_km: number;
  chainage_end_km: number;
  affected_tracks: string[];
  affected_ohe_sections: string[];
  affected_signals: string[];
  is_locked: boolean;
  is_shadow: boolean;
  shadow_bundle_id?: string;
  required_machines: string[];
  crew_count: number;
  safety_certified: boolean;
  approval_status: string;
}

export interface ShadowPossessionBundle extends BaseEntityProvenance {
  bundle_id: string;
  id?: string;
  primary_demand_id?: string;
  primary_possession_id?: string;
  secondary_demand_ids?: string[];
  shadow_possession_ids?: string[];
  corridor_closure_saving_hours?: number;
  block_id: string;
  window_start?: number;
  window_end?: number;
  time_window_start?: number;
  time_window_end?: number;
}

export interface SpeedRestrictionZone extends BaseEntityProvenance {
  id: string;
  track_id: string;
  block_id: string;
  chainage_start_km: number;
  chainage_end_km: number;
  restricted_speed_kmh: number;
  normal_speed_kmh: number;
  reason: string;
  is_permanent: boolean;
  start_coord: Coordinate3D;
  end_coord: Coordinate3D;
}

export interface SignalMarker extends BaseEntityProvenance {
  id: string;
  entity_type?: string;
  block_id: string;
  referenced_block_id?: string;
  chainage_km: number;
  coordinates?: Coordinate3D;
  position: Coordinate3D;
  aspect: "clear" | "caution" | "danger" | "stop";
  direction: "UP" | "DOWN";
  geometry_source?: string;
  geometry_schema_version?: string;
  schema_version?: string;
}

export interface OHEMast extends BaseEntityProvenance {
  id: string;
  entity_type?: string;
  block_id: string;
  referenced_block_id?: string;
  coordinates?: Coordinate3D;
  position: Coordinate3D;
  chainage_km?: number;
  catenary_height_m: number;
  is_isolated: boolean;
  geometry_source?: string;
  geometry_schema_version?: string;
  schema_version?: string;
}

export type ConflictType = 
  | "train_vs_block"
  | "train_versus_possession"
  | "premium_train_risk"
  | "incompatible_department"
  | "resource_overallocation"
  | "fixed_block_collision"
  | "insufficient_safety_clearance"
  | "overdue_critical_maintenance"
  | "headway_violation"
  | "ohe_isolation_conflict"
  | "signalling_disconnection_conflict"
  | "machine_collision"
  | "crew_rest_violation"
  | "tsl_conflict"
  | "stale_data"
  | "contradictory_source_data"
  | "disconnected_topology"
  | "invalid_geometry";

export interface ConflictItem extends BaseEntityProvenance {
  id: string;
  entity_type?: string;
  conflict_type: ConflictType;
  severity: "CRITICAL" | "MAJOR" | "WARNING" | "INFO";
  block_id: string;
  referenced_block_id?: string;
  title: string;
  description: string;
  affected_jobs: string[];
  affected_trains: string[];
  time_window?: { start: number; end: number };
  suggested_resolution: string;
  blocks_approval?: boolean;
  explanation?: string;
  location?: string;
  coordinates?: Coordinate3D;
  position?: Coordinate3D;
  geometry_source?: string;
  geometry_schema_version?: string;
  schema_version?: string;
}

export type NetworkConflict = ConflictItem;

export interface NetworkGeometryResponse {
  geometry_schema_version: string;
  coordinate_system: CoordinateSystemContract;
  division: string;
  line_name: string;
  total_length_km: number;
  is_synthetic: boolean;
  geometry_source?: string;
  coordinate_convention?: string;
  schema_version?: string;
  nodes: StationNode[];
  tracks: TrackGeometry[];
  signals: SignalMarker[];
  ohe_masts: OHEMast[];
  blocks: TrackBlock[];
  conflicts: ConflictItem[];
  junctions?: JunctionNode[];
  assets?: AssetHealthRecord[];
  disconnected_components?: string[][];
  track_sections?: TrackSection[];
  track_centerlines?: TrackCenterline[];
  crossovers?: Crossover[];
  interlockings?: InterlockingZone[];
  track_circuits?: TrackCircuit[];
  elementary_sections?: ElementarySection[];
  feeding_posts?: FeedingPost[];
  isolator_switches?: IsolatorSwitch[];
  possessions?: PossessionEntity[];
  shadow_bundles?: ShadowPossessionBundle[];
  speed_restrictions?: SpeedRestrictionZone[];
}

export interface PlanningCapabilitiesResponse {
  geometry_schema_version: string;
  coordinate_system?: CoordinateSystemContract;
  solver_available: boolean;
  solver_name: string;
  fallback_active: boolean;
  model_mode: string;
  model_version: string;
  supports_3d_geometry: boolean;
  demo_mode: boolean;
  supported_horizons_days: number[];
  routes_available: string[];
  max_blocks_capacity: number;
  max_trains_capacity: number;
}

export interface ShadowBlockGroup {
  group_id: string;
  block_id: string;
  start_time: number;
  end_time: number;
  jobs: string[];
  departments?: Department[];
}

export interface JobExplanation {
  job_id: string;
  tci: number;
  tci_components: Record<string, unknown>;
  priority_rationale: string;
  window_rationale: string;
  consolidation_rationale?: string;
  protected_trains: string[];
  active_constraints: string[];
}

export interface SystemEvent {
  id: string;
  timestamp: string;
  level: "info" | "warning" | "critical";
  message: string;
  source?: string;
  division?: string;
  action_required?: boolean;
}

export interface AssetHealthRecord {
  asset_id: string;
  block_id: string;
  name: string;
  asset_type: "Rail" | "Sleeper" | "OHE Mast" | "Point Machine" | "Track Circuit";
  chainage_start_km: number;
  chainage_end_km: number;
  health_score: number; // 0-100
  defect_severity: "Normal" | "Minor" | "Major" | "Critical";
  degradation_velocity: number; // mm/MGT or mm/month
  observed_defect_type: string;
  model_predicted_risk: number; // 0-1
  last_ultrasonic_test: string;
  days_overdue: number;
  associated_job_id?: string;
  coordinates?: Coordinate3D;
  position?: Coordinate3D;
  geometry_source?: string;
  geometry_schema_version?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  geometry_schema_version: string;
  solver_available: boolean;
  solver_name: string;
  data_mode: string;
  commit_sha?: string;
}

export interface DivisionInfo {
  id: string;
  code: string;
  name: string;
  zone: string;
  headquarters: string;
  route_km: number;
  active_blocks_count: number;
}

export type PossessionLifecycle =
  | "REQUESTED"
  | "SANCTIONED"
  | "GRANTED"
  | "IN_PROGRESS"
  | "CLEARANCE_PENDING"
  | "COMPLETED"
  | "CANCELLED"
  | "REJECTED";

export type ApprovalRole =
  | "CTPC"
  | "SR_DOM"
  | "SECTION_CONTROLLER"
  | "STATION_MASTER"
  | "SSE_PWAY"
  | "SSE_TRD"
  | "SSE_SIGNAL";

export interface CandidateBundleItem {
  bundle_id: string;
  primary_job_id: string;
  secondary_job_ids: string[];
  block_id: string;
  departments: string[];
  spatial_extent_km: [number, number];
  time_envelope_hours: [number, number];
  required_duration_hours: number;
  total_tci_benefit: number;
  compatibility_rationale: string;
}

export interface RecommendedBlockItem {
  job_id: string;
  block_id: string;
  start_time: number;
  end_time: number;
  tci: number;
  is_shadow: boolean;
  shadow_parent?: string;
  department: string;
  lifecycle_state: PossessionLifecycle;
}

export interface ApprovalChainRecord {
  status: "PENDING" | "APPROVED" | "REJECTED" | "OVERRIDDEN";
  approver_id?: string | null;
  approver_name?: string | null;
  comments?: string | null;
  timestamp?: string | null;
}

export interface AdvisoryProposal {
  optimization_run_id: string;
  idempotency_key: string;
  division_code: string;
  planning_window: string;
  schema_version: string;
  advisory_mode: string;
  solver_mode: string;
  safety_status: "SAFETY_CERTIFIED" | "SAFETY_REJECTED";
  approval_status:
    | "PENDING_CTPC_REVIEW"
    | "PENDING_SR_DOM_REVIEW"
    | "PENDING_SECTION_CONTROLLER_REVIEW"
    | "PENDING_STATION_MASTER_REVIEW"
    | "SANCTIONED"
    | "GRANTED"
    | "REJECTED"
    | "OVERRIDDEN"
    | string;
  statutory_compliance: string;
  created_at: string;
  created_by: string;
  recommended_blocks: RecommendedBlockItem[];
  candidate_bundles: CandidateBundleItem[];
  train_regulation_plan: Record<string, { accumulated_delay_hours: number; regulation_strategy: string }>;
  computed_metrics: {
    total_closure_hours: number;
    objective_tci_value: number;
    scheduled_count: number;
    runtime_seconds: number;
  };
  approval_chain: Record<string, ApprovalChainRecord>;
  diagnostics: string[];
}

export interface ApprovalActionPayload {
  role: ApprovalRole;
  approver_id: string;
  approver_name: string;
  decision: "APPROVED" | "REJECTED" | "OVERRIDDEN";
  comments: string;
  override_reason_code?: string;
  overridden_schedule?: Record<string, unknown>;
}

export interface OperationalOverridePayload {
  user_id: string;
  role: ApprovalRole;
  reason_code: string;
  justification: string;
  overridden_schedule: Record<string, unknown>;
}

export interface AuditEventRecord {
  id: string;
  event_id: string;
  event_type: string;
  user_id: string;
  role?: string | null;
  timestamp: string;
  resource_type: string;
  resource_id: string;
  action: string;
  details: Record<string, unknown>;
}

// ----------------- What-If & Scenario Simulator Types ----------------- //

export interface WhatIfModification {
  job_id?: string;
  extend_duration_hours?: number;
  shift_start_hours?: number;
  cancel_job?: boolean;
  train_id?: string;
  added_delay_min?: number;
  speed_restriction_kmh?: number;
  affected_block_id?: string;
}

export interface WhatIfScenarioRequest {
  scenario_id?: string;
  modifications?: WhatIfModification[];
  fast_solve?: boolean;
}

export interface TrainDelayDelta {
  train_id: string;
  train_name?: string;
  category: string;
  baseline_delay_min: number;
  what_if_delay_min: number;
  delta_delay_min: number;
  energy_loss_kwh: number;
  crew_duty_exceeded: boolean;
}

export interface WhatIfDeltaReport {
  baseline_cumulative_delay_min: number;
  what_if_cumulative_delay_min: number;
  delta_cumulative_delay_min: number;
  train_deltas: TrainDelayDelta[];
  heavy_machine_productivity_delta_hours: number;
  freight_rakes_regulated_count: number;
  total_energy_loss_kwh: number;
  total_fuel_cost_impact_inr: number;
  crew_hours_timeout_warnings: string[];
  narrative_summary_en: string;
  narrative_summary_hi: string;
}

export interface WhatIfScenarioResponse {
  status: string;
  run_id: string;
  delta_report: WhatIfDeltaReport;
  what_if_schedule: Record<string, unknown>;
  conflicts_count: number;
}

export interface BlockShiftRequest {
  job_id: string;
  shift_minutes?: number;
  shift_hours?: number;
  scenario_id?: string;
}

export interface BlockShiftResponse {
  job_id: string;
  block_id: string;
  original_start_hours: number;
  new_start_hours: number;
  new_end_hours: number;
  is_feasible: boolean;
  conflict_count: number;
  delta_delay_min: number;
  conflicts: Array<Record<string, unknown>>;
  bilingual_advisory: Record<string, string>;
  new_start_time?: number;
  new_end_time?: number;
  added_delay_minutes?: number;
  is_viable?: boolean;
  recommendation?: string;
}

export interface ScheduleJustification {
  job_id: string;
  block_id: string;
  headline_en: string;
  headline_hi: string;
  detailed_en: string;
  detailed_hi: string;
  tradeoff_en: string;
  tradeoff_hi: string;
  binding_constraints: string[];
  crew_impact_en?: string;
  crew_impact_hi?: string;
  energy_impact_en?: string;
  energy_impact_hi?: string;
}

export type RailwayDepartment = "OPERATING" | "CIVIL" | "TRD" | "SNT" | "ADMIN";

export type RailwayRole =
  | "SR_DOM"
  | "SECTION_CONTROLLER"
  | "CTPC"
  | "SSE_PWAY"
  | "SSE_TRD"
  | "SSE_SIGNAL"
  | "STATION_MASTER"
  | "SYSTEM_ADMIN";

export interface UserProfile {
  id: string;
  pf_number: string;
  email: string;
  full_name: string;
  department: RailwayDepartment;
  role: RailwayRole;
  division_code: string;
  zone_code: string;
  is_active: boolean;
  last_login?: string;
  capabilities: string[];
}

export interface AuthTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
}
