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

export interface Vector3D {
  x: number;
  y: number;
  z: number;
}

export interface TrackGeometry {
  block_id: string;
  name: string;
  start_coord: Vector3D;
  end_coord: Vector3D;
  path_points: Vector3D[];
  length_km: number;
  chainage_start: number;
  chainage_end: number;
  elevation_profile: number[];
  track_type: string;
  electrification: string;
  gauge?: string;
  speed_limit_kmh: number;
}

export interface StationNode {
  id: string;
  name: string;
  code: string;
  position: Vector3D;
  chainage_km: number;
  node_type: "station" | "junction" | "terminal";
  platforms: number;
  connected_blocks: string[];
}

export interface SignalMarker {
  id: string;
  block_id: string;
  chainage_km: number;
  position: Vector3D;
  aspect: "clear" | "caution" | "danger" | "stop";
  direction: "UP" | "DOWN";
}

export interface OHEMast {
  id: string;
  block_id: string;
  position: Vector3D;
  catenary_height_m: number;
  is_isolated: boolean;
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
  conflict_type: ConflictType;
  severity: "CRITICAL" | "MAJOR" | "WARNING" | "INFO";
  block_id: string;
  title: string;
  description: string;
  affected_jobs: string[];
  affected_trains: string[];
  time_window?: { start: number; end: number };
  suggested_resolution: string;
  position?: Vector3D;
}

export interface NetworkGeometryResponse {
  division: string;
  line_name: string;
  total_length_km: number;
  is_synthetic: boolean;
  nodes: StationNode[];
  tracks: TrackGeometry[];
  signals: SignalMarker[];
  ohe_masts: OHEMast[];
  blocks: TrackBlock[];
  conflicts: ConflictItem[];
}

export interface PlanningCapabilitiesResponse {
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
