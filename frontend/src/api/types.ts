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
  track_type?: "Mainline" | "Loop" | "Siding";
  speed_restriction_kmh?: number;
  electrification_status?: "25kV AC" | "Non-Electrified";
  signaling_type?: "Automatic" | "Absolute Block";
}

export interface Train {
  id: string;
  name?: string;
  category: TrainCategory;
  scheduled_start: number;
  scheduled_end: number;
  route: string[];
  min_travel_times: Record<string, number>;
  max_speed_kmh?: number;
  current_block?: string;
  current_delay_min?: number;
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
  is_fixed: boolean;
  fixed_start?: number | null;
  job_type?: string;
  due_date?: string;
  safety_clearance_required?: string;
  chainage_km?: string;
  status?: JobStatus;
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
  blocks: TrackBlock[];
  trains: Train[];
  jobs: MaintenanceJob[];
  resources: Resource[];
  fixed_blocks: FixedMaintenanceBlock[];
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
  status: string;
  solver: string;
  scheduled_jobs: ScheduledJob[];
  unscheduled_jobs: UnscheduledJob[];
  train_delays: Record<string, number>;
  total_closure_time: number;
  objective_value: number;
  runtime_seconds?: number;
  kpi_metrics?: KPIReport;
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

export interface CoordinateSystemContract {
  name: "LOCAL_CORRIDOR" | string;
  crs: "LOCAL_CORRIDOR" | string;
  units: "meters";
  axis_order: string[];
  handedness: "right-handed";
  origin_description: string;
  geometry_source: "synthetic" | "surveyed";
}

export interface GeometryNode {
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

export interface TrackGeometry {
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

export interface SignalMarker {
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

export interface OHEMast {
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
  | "premium_train_risk"
  | "incompatible_department"
  | "resource_overallocation"
  | "fixed_block_collision"
  | "insufficient_safety_clearance"
  | "overdue_critical_maintenance";

export interface ConflictItem {
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
  approval_status: "PENDING_CTPC_REVIEW" | "SANCTIONED" | "GRANTED" | "REJECTED" | "OVERRIDDEN";
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
