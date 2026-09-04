import type {
  Scenario,
  OptimizedSchedule,
  ScoredJob,
  KPIReport,
  SystemEvent,
  AssetHealthRecord,
  DivisionInfo,
  NetworkGeometryResponse,
  PlanningCapabilitiesResponse,
  ConflictItem
} from './types';

export const mockDivisions: DivisionInfo[] = [
  { id: "DIV-PRYJ", code: "PRYJ", name: "Prayagraj Division", zone: "North Central Railway", headquarters: "Prayagraj", route_km: 1340, active_blocks_count: 4 },
  { id: "DIV-DLI", code: "DLI", name: "Delhi Division", zone: "Northern Railway", headquarters: "New Delhi", route_km: 1412, active_blocks_count: 6 },
  { id: "DIV-SC", code: "SC", name: "Secunderabad Division", zone: "South Central Railway", headquarters: "Secunderabad", route_km: 1520, active_blocks_count: 3 },
  { id: "DIV-HWH", code: "HWH", name: "Howrah Division", zone: "Eastern Railway", headquarters: "Kolkata", route_km: 1285, active_blocks_count: 5 },
];

export const mockScenario: Scenario = {
  blocks: [
    { id: "B1", chainage_start: 0.0, chainage_end: 10.0, description: "Station A to B (Ghaziabad - Aligarh)", track_type: "Mainline", speed_restriction_kmh: 110, electrification_status: "25kV AC", signaling_type: "Automatic" },
    { id: "B2", chainage_start: 10.0, chainage_end: 20.0, description: "Station B to C (Aligarh - Hathras)", track_type: "Mainline", speed_restriction_kmh: 80, electrification_status: "25kV AC", signaling_type: "Automatic" },
    { id: "B3", chainage_start: 20.0, chainage_end: 30.0, description: "Station C to D (Hathras - Tundla)", track_type: "Mainline", speed_restriction_kmh: 120, electrification_status: "25kV AC", signaling_type: "Automatic" },
    { id: "B4", chainage_start: 30.0, chainage_end: 40.0, description: "Station D to E (Tundla - Firozabad)", track_type: "Mainline", speed_restriction_kmh: 75, electrification_status: "25kV AC", signaling_type: "Automatic" },
    { id: "B5", chainage_start: 40.0, chainage_end: 50.0, description: "Station E to F (Firozabad - Shikohabad)", track_type: "Mainline", speed_restriction_kmh: 130, electrification_status: "25kV AC", signaling_type: "Automatic" },
    { id: "B6", chainage_start: 50.0, chainage_end: 60.0, description: "Station F to G (Shikohabad - Etawah)", track_type: "Mainline", speed_restriction_kmh: 90, electrification_status: "25kV AC", signaling_type: "Automatic" },
    { id: "B7", chainage_start: 60.0, chainage_end: 70.0, description: "Station G to H (Etawah - Bharthana)", track_type: "Mainline", speed_restriction_kmh: 120, electrification_status: "25kV AC", signaling_type: "Absolute Block" },
    { id: "B8", chainage_start: 70.0, chainage_end: 80.0, description: "Station H to I (Bharthana - Phaphund)", track_type: "Mainline", speed_restriction_kmh: 130, electrification_status: "25kV AC", signaling_type: "Absolute Block" },
  ],
  resources: [
    { id: "R_BCM", name: "Ballast Cleaning Machine (BCM-04)", capacity: 2, department: "Engineering", available_units: 2 },
    { id: "R_CREW_OHE", name: "OHE Maintenance Tower Wagon Crew", capacity: 4, department: "OHE", available_units: 3 },
    { id: "R_CREW_SIG", name: "Signal & Interlocking Testing Crew", capacity: 3, department: "S&T", available_units: 2 },
    { id: "R_TIE", name: "Heavy Tie Tamper (CSM-9X)", capacity: 1, department: "Engineering", available_units: 1 },
  ],
  fixed_blocks: [
    { id: "FB1", block_id: "B1", start_time: 2.0, end_time: 6.0, reason: "Emergency Bridge Girder Repair", department: "Engineering" },
    { id: "FB2", block_id: "B4", start_time: 10.0, end_time: 12.0, reason: "High Voltage Substation Feeder Shutdown", department: "OHE" },
  ],
  trains: [
    { id: "T1", name: "12301 Rajdhani Express", category: "premium", scheduled_start: 0.0, scheduled_end: 3.0, route: ["B5", "B6", "B7"], min_travel_times: { B5: 0.5, B6: 0.5, B7: 0.5 }, max_speed_kmh: 130, current_block: "B6", current_delay_min: 0 },
    { id: "T2", name: "12002 Shatabdi Express", category: "premium", scheduled_start: 1.0, scheduled_end: 4.0, route: ["B5", "B6", "B7", "B8"], min_travel_times: { B5: 0.5, B6: 0.5, B7: 0.5, B8: 0.5 }, max_speed_kmh: 130, current_block: "B7", current_delay_min: 0 },
    { id: "T3", name: "22436 Vande Bharat Express", category: "premium", scheduled_start: 2.0, scheduled_end: 5.0, route: ["B5", "B6", "B7", "B8"], min_travel_times: { B5: 0.5, B6: 0.5, B7: 0.5, B8: 0.5 }, max_speed_kmh: 130, current_block: "B5", current_delay_min: 0 },
    { id: "T4", name: "BOXN Coal Freight Spl", category: "freight", scheduled_start: 3.0, scheduled_end: 9.0, route: ["B6", "B7", "B8"], min_travel_times: { B6: 1.0, B7: 1.0, B8: 1.0 }, max_speed_kmh: 75, current_block: "B7", current_delay_min: 15 },
    { id: "T5", name: "BCN Grain Container Express", category: "freight", scheduled_start: 4.0, scheduled_end: 10.0, route: ["B5", "B6", "B7"], min_travel_times: { B5: 1.0, B6: 1.0, B7: 1.0 }, max_speed_kmh: 75, current_block: "B5", current_delay_min: 5 },
    { id: "T6", name: "RO-RO Auto Freight Carrier", category: "freight", scheduled_start: 5.0, scheduled_end: 11.0, route: ["B1", "B2", "B3", "B4", "B5", "B6"], min_travel_times: { B1: 1.0, B2: 1.0, B3: 1.0, B4: 1.0, B5: 1.0, B6: 1.0 }, max_speed_kmh: 70, current_block: "B2", current_delay_min: 180 },
    { id: "T7", name: "12801 Purushottam Express", category: "express", scheduled_start: 6.0, scheduled_end: 12.0, route: ["B4", "B5", "B6", "B7"], min_travel_times: { B4: 0.8, B5: 0.8, B6: 0.8, B7: 0.8 }, max_speed_kmh: 110, current_block: "B4", current_delay_min: 0 },
    { id: "T8", name: "12454 Ranchi Rajdhani", category: "premium", scheduled_start: 7.0, scheduled_end: 13.0, route: ["B1", "B2", "B3", "B4"], min_travel_times: { B1: 0.6, B2: 0.6, B3: 0.6, B4: 0.6 }, max_speed_kmh: 130, current_block: "B1", current_delay_min: 120 },
    { id: "T9", name: "14217 Unchahar Express", category: "express", scheduled_start: 8.0, scheduled_end: 14.0, route: ["B5", "B6", "B7"], min_travel_times: { B5: 0.8, B6: 0.8, B7: 0.8 }, max_speed_kmh: 100, current_block: "B5", current_delay_min: 0 },
    { id: "T10", name: "CONCOR DFC Feeder Rake", category: "freight", scheduled_start: 9.0, scheduled_end: 15.0, route: ["B5", "B6", "B7", "B8"], min_travel_times: { B5: 1.0, B6: 1.0, B7: 1.0, B8: 1.0 }, max_speed_kmh: 75, current_block: "B6", current_delay_min: 0 },
  ],
  jobs: [
    {
      id: "J1",
      department: "OHE",
      block_id: "B4",
      duration: 2.0,
      required_resources: { R_CREW_OHE: 1 },
      tci_inputs: { safety_severity: 0.63, traffic_impact: 0.83, degradation_indicator: 0.11, overdue_days: 10 },
      is_fixed: false,
      job_type: "Catenary Wire Tension Adjustment",
      chainage_km: "34.2 to 36.8",
      safety_clearance_required: "Power Disconnection & Discharge Rod Erection",
      due_date: "2026-09-08"
    },
    {
      id: "J2",
      department: "S&T",
      block_id: "B7",
      duration: 2.0,
      required_resources: { R_CREW_SIG: 1 },
      tci_inputs: { safety_severity: 0.35, traffic_impact: 0.29, degradation_indicator: 0.79, overdue_days: 6 },
      is_fixed: false,
      job_type: "Digital Axle Counter Calibration",
      chainage_km: "62.1 to 64.5",
      safety_clearance_required: "Signal Disconnection Notice Issued",
      due_date: "2026-09-12"
    },
    {
      id: "J3",
      department: "Engineering",
      block_id: "B7",
      duration: 1.0,
      required_resources: { R_TIE: 1 },
      tci_inputs: { safety_severity: 0.38, traffic_impact: 0.24, degradation_indicator: 0.55, overdue_days: 4 },
      is_fixed: false,
      job_type: "Turnout Point Tamping & Lining",
      chainage_km: "61.0 to 62.0",
      safety_clearance_required: "Caution Order 30 km/h Post Maintenance",
      due_date: "2026-09-15"
    },
    {
      id: "J4",
      department: "S&T",
      block_id: "B2",
      duration: 2.0,
      required_resources: { R_CREW_SIG: 1 },
      tci_inputs: { safety_severity: 0.40, traffic_impact: 0.45, degradation_indicator: 0.32, overdue_days: 8 },
      is_fixed: false,
      job_type: "Point Machine Overhaul & Friction Clutch Test",
      chainage_km: "12.4 to 14.1",
      safety_clearance_required: "Line Block & S&T Disconnection Form B",
      due_date: "2026-09-10"
    },
    {
      id: "J5",
      department: "S&T",
      block_id: "B4",
      duration: 3.0,
      required_resources: { R_CREW_SIG: 1 },
      tci_inputs: { safety_severity: 0.48, traffic_impact: 0.52, degradation_indicator: 0.42, overdue_days: 9 },
      is_fixed: false,
      job_type: "Track Circuit Glued Joint Renewal",
      chainage_km: "31.5 to 33.2",
      safety_clearance_required: "Automatic Signaling Territory Line Block",
      due_date: "2026-09-09"
    },
    {
      id: "J6",
      department: "Engineering",
      block_id: "B2",
      duration: 2.0,
      required_resources: { R_BCM: 1 },
      tci_inputs: { safety_severity: 0.56, traffic_impact: 0.60, degradation_indicator: 0.50, overdue_days: 12 },
      is_fixed: false,
      job_type: "Shoulder Ballast Deep Screening",
      chainage_km: "15.0 to 18.0",
      safety_clearance_required: "Line Closure & Machine Protection Kit",
      due_date: "2026-09-07"
    },
    {
      id: "J7",
      department: "S&T",
      block_id: "B5",
      duration: 3.0,
      required_resources: { R_CREW_SIG: 1 },
      tci_inputs: { safety_severity: 0.82, traffic_impact: 0.78, degradation_indicator: 0.74, overdue_days: 18 },
      is_fixed: false,
      job_type: "Electronic Interlocking Optical Link Replacement",
      chainage_km: "42.0 to 45.0",
      safety_clearance_required: "Critical Safety Interlocking Bypass Approval",
      due_date: "2026-09-05"
    },
    {
      id: "J8",
      department: "S&T",
      block_id: "B4",
      duration: 1.0,
      required_resources: { R_CREW_SIG: 1 },
      tci_inputs: { safety_severity: 0.60, traffic_impact: 0.62, degradation_indicator: 0.55, overdue_days: 14 },
      is_fixed: false,
      job_type: "Multi-aspect Color Light Signal LED Cluster Replacement",
      chainage_km: "38.1 to 39.0",
      safety_clearance_required: "Standard S&T Clearance",
      due_date: "2026-09-06"
    },
    {
      id: "J9",
      department: "Engineering",
      block_id: "B6",
      duration: 1.0,
      required_resources: { R_TIE: 1 },
      tci_inputs: { safety_severity: 0.28, traffic_impact: 0.35, degradation_indicator: 0.31, overdue_days: 3 },
      is_fixed: false,
      job_type: "Plain Track Joint Tamping",
      chainage_km: "52.0 to 53.5",
      safety_clearance_required: "Machine Block 1h",
      due_date: "2026-09-18"
    },
    {
      id: "J10",
      department: "S&T",
      block_id: "B6",
      duration: 1.0,
      required_resources: { R_CREW_SIG: 1 },
      tci_inputs: { safety_severity: 0.72, traffic_impact: 0.68, degradation_indicator: 0.66, overdue_days: 15 },
      is_fixed: false,
      job_type: "Signal Relays Quarterly Overhaul",
      chainage_km: "55.2 to 56.4",
      safety_clearance_required: "Relay Room Access Protocol",
      due_date: "2026-09-06"
    },
    {
      id: "J11",
      department: "Engineering",
      block_id: "B5",
      duration: 1.0,
      required_resources: { R_TIE: 1 },
      tci_inputs: { safety_severity: 0.58, traffic_impact: 0.55, degradation_indicator: 0.56, overdue_days: 11 },
      is_fixed: false,
      job_type: "Curve Alignment & Superelevation Correction",
      chainage_km: "46.2 to 47.8",
      safety_clearance_required: "Engineering Speed Restriction 45 km/h",
      due_date: "2026-09-09"
    },
    {
      id: "J12",
      department: "OHE",
      block_id: "B6",
      duration: 1.0,
      required_resources: { R_CREW_OHE: 1 },
      tci_inputs: { safety_severity: 0.62, traffic_impact: 0.64, degradation_indicator: 0.58, overdue_days: 13 },
      is_fixed: false,
      job_type: "Dropper & Section Insulator Inspection",
      chainage_km: "51.0 to 54.0",
      safety_clearance_required: "OHE Power Block 1h",
      due_date: "2026-09-08"
    },
    {
      id: "J13",
      department: "Engineering",
      block_id: "B3",
      duration: 3.0,
      required_resources: { R_BCM: 1 },
      tci_inputs: { safety_severity: 0.68, traffic_impact: 0.66, degradation_indicator: 0.64, overdue_days: 16 },
      is_fixed: false,
      job_type: "Ballast Cleaning & Track Lifting",
      chainage_km: "22.0 to 25.5",
      safety_clearance_required: "Heavy Machine Line Block",
      due_date: "2026-09-06"
    },
    {
      id: "J14",
      department: "OHE",
      block_id: "B5",
      duration: 3.0,
      required_resources: { R_CREW_OHE: 1 },
      tci_inputs: { safety_severity: 0.64, traffic_impact: 0.65, degradation_indicator: 0.60, overdue_days: 14 },
      is_fixed: false,
      job_type: "Contact Wire Stagger Rectification",
      chainage_km: "41.5 to 44.5",
      safety_clearance_required: "Traction Power Block 3h",
      due_date: "2026-09-07"
    },
    {
      id: "J15",
      department: "OHE",
      block_id: "B6",
      duration: 1.0,
      required_resources: { R_CREW_OHE: 1 },
      tci_inputs: { safety_severity: 0.30, traffic_impact: 0.32, degradation_indicator: 0.34, overdue_days: 4 },
      is_fixed: false,
      job_type: "Neutral Section Phase Break Inspection",
      chainage_km: "58.0 to 59.0",
      safety_clearance_required: "Coast Notice for Locomotives",
      due_date: "2026-09-17"
    },
    {
      id: "J16",
      department: "S&T",
      block_id: "B3",
      duration: 3.0,
      required_resources: { R_CREW_SIG: 1 },
      tci_inputs: { safety_severity: 0.85, traffic_impact: 0.80, degradation_indicator: 0.76, overdue_days: 20 },
      is_fixed: false,
      job_type: "Audio Frequency Track Circuit (AFTC) Replacement",
      chainage_km: "23.1 to 26.0",
      safety_clearance_required: "S&T Safety Block & Disconnection Notice",
      due_date: "2026-09-04"
    },
    {
      id: "J17",
      department: "S&T",
      block_id: "B4",
      duration: 1.0,
      required_resources: { R_CREW_SIG: 1 },
      tci_inputs: { safety_severity: 0.54, traffic_impact: 0.55, degradation_indicator: 0.52, overdue_days: 10 },
      is_fixed: false,
      job_type: "Block Instrument Surge Protection Maintenance",
      chainage_km: "35.0 to 36.5",
      safety_clearance_required: "Short Window S&T Block",
      due_date: "2026-09-10"
    },
    {
      id: "J18",
      department: "Engineering",
      block_id: "B6",
      duration: 2.0,
      required_resources: { R_BCM: 1 },
      tci_inputs: { safety_severity: 0.92, traffic_impact: 0.90, degradation_indicator: 0.86, overdue_days: 24 },
      is_fixed: false,
      job_type: "Thermit Weld Fracture Replacement",
      chainage_km: "54.1 to 55.0",
      safety_clearance_required: "Immediate Emergency Speed Restriction 20 km/h",
      due_date: "2026-09-04"
    },
    {
      id: "J_FIXED_1",
      department: "Engineering",
      block_id: "B1",
      duration: 4.0,
      required_resources: { R_BCM: 1 },
      tci_inputs: { safety_severity: 1.0, traffic_impact: 1.0, degradation_indicator: 1.0, overdue_days: 0 },
      is_fixed: true,
      fixed_start: 2.0,
      job_type: "Major Girder Bridge Regirdering (Scheduled RBP Block)",
      chainage_km: "4.5 to 6.2",
      safety_clearance_required: "Chief Bridge Engineer Direct Supervision",
      due_date: "2026-09-04"
    },
    {
      id: "J_FIXED_2",
      department: "OHE",
      block_id: "B4",
      duration: 2.0,
      required_resources: { R_CREW_OHE: 1 },
      tci_inputs: { safety_severity: 1.0, traffic_impact: 1.0, degradation_indicator: 1.0, overdue_days: 0 },
      is_fixed: true,
      fixed_start: 10.0,
      job_type: "Grid Substation Feeder 132/25kV Transformer Isolator Maintenance",
      chainage_km: "33.0 to 35.0",
      safety_clearance_required: "State Electricity Board Load Dispatch Approval",
      due_date: "2026-09-04"
    },
  ]
};

// Compute deterministic TCI score matching TaskCriticalityScorer formula
export const mockScoredJobs: { scored_jobs: ScoredJob[] } = {
  scored_jobs: mockScenario.jobs.map((job) => {
    const s_safety = Math.max(0, Math.min(1, job.tci_inputs.safety_severity));
    const s_delay = Math.max(0, Math.min(1, job.tci_inputs.traffic_impact));
    const s_degrad = Math.max(0, Math.min(1, job.tci_inputs.degradation_indicator));
    const s_overdue = job.tci_inputs.overdue_days <= 0
      ? 0
      : Math.min(1, Math.log1p(job.tci_inputs.overdue_days) / Math.log1p(30));

    const w_safety = 0.4;
    const w_delay = 0.3;
    const w_degrad = 0.2;
    const w_overdue = 0.1;

    const raw_score = w_safety * s_safety + w_delay * s_delay + w_degrad * s_degrad + w_overdue * s_overdue;
    const final_tci = raw_score * 100.0;

    return {
      job_id: job.id,
      tci: Number(final_tci.toFixed(1)),
      explanation: {
        safety_component: Number((w_safety * s_safety * 100).toFixed(1)),
        delay_component: Number((w_delay * s_delay * 100).toFixed(1)),
        degradation_component: Number((w_degrad * s_degrad * 100).toFixed(1)),
        overdue_component: Number((w_overdue * s_overdue * 100).toFixed(1)),
        raw_inputs: job.tci_inputs,
        formula_breakdown: `TCI = 40%*Safety (${(s_safety*100).toFixed(0)}) + 30%*Delay (${(s_delay*100).toFixed(0)}) + 20%*Degradation (${(s_degrad*100).toFixed(0)}) + 10%*Overdue (${job.tci_inputs.overdue_days}d)`
      }
    };
  })
};

export const mockKPIReport: KPIReport = {
  bue_percent: 134.48,
  bue_baseline_percent: 100.0,
  sbr_percent: 17.65,
  pii_delays: 4.0,
  pii_baseline_delays: 42.0,
  tci_coverage_percent: 100.0,
  total_closure_hours: 29.0,
  baseline_closure_hours: 39.0,
  consolidated_blocks: 3,
  mttg_minutes: 22.5,
  high_crit_completion_percent: 100.0
};

export const mockSchedule: OptimizedSchedule = {
  status: "optimal",
  solver: "PySCIPOpt (SCIP MILP)",
  total_closure_time: 29.0,
  objective_value: -121050.53,
  runtime_seconds: 0.253,
  scheduled_jobs: [
    { job_id: "J_FIXED_1", block_id: "B1", start_time: 2.0, end_time: 6.0, tci: 90.0, department: "Engineering", is_shadow_block: false, assigned_resources: ["R_BCM"] },
    { job_id: "J8", block_id: "B4", start_time: 4.0, end_time: 5.0, tci: 59.6, department: "S&T", is_shadow_block: false, assigned_resources: ["R_CREW_SIG"] },
    { job_id: "J_FIXED_2", block_id: "B4", start_time: 10.0, end_time: 12.0, tci: 90.0, department: "OHE", is_shadow_block: false, assigned_resources: ["R_CREW_OHE"] },
    { job_id: "J1", block_id: "B4", start_time: 14.0, end_time: 16.0, tci: 59.2, department: "OHE", is_shadow_block: false, assigned_resources: ["R_CREW_OHE"] },
    { job_id: "J11", block_id: "B5", start_time: 16.0, end_time: 17.0, tci: 56.8, department: "Engineering", is_shadow_block: true, shadow_with_jobs: ["J14"], assigned_resources: ["R_TIE"] },
    { job_id: "J14", block_id: "B5", start_time: 16.0, end_time: 19.0, tci: 63.3, department: "OHE", is_shadow_block: true, shadow_with_jobs: ["J11"], assigned_resources: ["R_CREW_OHE"] },
    { job_id: "J2", block_id: "B7", start_time: 17.0, end_time: 19.0, tci: 44.2, department: "S&T", is_shadow_block: true, shadow_with_jobs: ["J3"], assigned_resources: ["R_CREW_SIG"] },
    { job_id: "J3", block_id: "B7", start_time: 17.0, end_time: 18.0, tci: 39.2, department: "Engineering", is_shadow_block: true, shadow_with_jobs: ["J2"], assigned_resources: ["R_TIE"] },
    { job_id: "J4", block_id: "B2", start_time: 18.0, end_time: 20.0, tci: 40.3, department: "S&T", is_shadow_block: true, shadow_with_jobs: ["J6"], assigned_resources: ["R_CREW_SIG"] },
    { job_id: "J6", block_id: "B2", start_time: 18.0, end_time: 20.0, tci: 56.1, department: "Engineering", is_shadow_block: true, shadow_with_jobs: ["J4"], assigned_resources: ["R_BCM"] },
    { job_id: "J17", block_id: "B4", start_time: 19.0, end_time: 20.0, tci: 54.0, department: "S&T", is_shadow_block: false, assigned_resources: ["R_CREW_SIG"] },
    { job_id: "J12", block_id: "B6", start_time: 20.0, end_time: 21.0, tci: 61.6, department: "OHE", is_shadow_block: true, shadow_with_jobs: ["J18"], assigned_resources: ["R_CREW_OHE"] },
    { job_id: "J18", block_id: "B6", start_time: 20.0, end_time: 22.0, tci: 89.9, department: "Engineering", is_shadow_block: true, shadow_with_jobs: ["J12"], assigned_resources: ["R_BCM"] },
    { job_id: "J10", block_id: "B6", start_time: 21.0, end_time: 22.0, tci: 69.6, department: "S&T", is_shadow_block: true, shadow_with_jobs: ["J18"], assigned_resources: ["R_CREW_SIG"] },
    { job_id: "J9", block_id: "B6", start_time: 22.0, end_time: 23.0, tci: 31.2, department: "Engineering", is_shadow_block: true, shadow_with_jobs: ["J15"], assigned_resources: ["R_TIE"] },
    { job_id: "J15", block_id: "B6", start_time: 22.0, end_time: 23.0, tci: 32.1, department: "OHE", is_shadow_block: true, shadow_with_jobs: ["J9"], assigned_resources: ["R_CREW_OHE"] },
    { job_id: "J5", block_id: "B4", start_time: 23.0, end_time: 26.0, tci: 48.5, department: "S&T", is_shadow_block: false, assigned_resources: ["R_CREW_SIG"] },
    { job_id: "J7", block_id: "B5", start_time: 23.0, end_time: 26.0, tci: 78.2, department: "S&T", is_shadow_block: false, assigned_resources: ["R_CREW_SIG"] },
    { job_id: "J13", block_id: "B3", start_time: 23.0, end_time: 26.0, tci: 66.5, department: "Engineering", is_shadow_block: true, shadow_with_jobs: ["J16"], assigned_resources: ["R_BCM"] },
    { job_id: "J16", block_id: "B3", start_time: 23.0, end_time: 26.0, tci: 80.7, department: "S&T", is_shadow_block: true, shadow_with_jobs: ["J13"], assigned_resources: ["R_CREW_SIG"] },
  ],
  unscheduled_jobs: [
    {
      job_id: "J_UNSCHED_1",
      reason: "Track occupancy bottleneck on B2 during peak traffic corridor; deferred to Week 2 RBP maintenance cycle to protect 12301 Rajdhani priority window.",
      conflict_with: "12301 Rajdhani Express (T1)",
      potential_window: "Week 2, Tuesday 02:00 to 05:00"
    }
  ],
  train_delays: {
    "T1": 0.0,
    "T2": 0.0,
    "T3": 0.0,
    "T4": 0.0,
    "T5": 0.0,
    "T6": 3.0,
    "T7": 0.0,
    "T8": 2.0,
    "T9": 0.0,
    "T10": 0.0
  },
  kpi_metrics: mockKPIReport
};

export const mockEvents: SystemEvent[] = [
  { id: "EVT-101", timestamp: "2026-09-04T08:52:10Z", level: "info", message: "PySCIPOpt MILP Solver converged to optimal solution in 253ms with 0.0% duality gap.", source: "Optimization Engine", division: "PRYJ" },
  { id: "EVT-102", timestamp: "2026-09-04T08:45:30Z", level: "warning", message: "Track fracture warning detected by TRC-09 on Block B6 chainage 54.1 km. TCI score escalated to 89.9.", source: "Track Management System", division: "PRYJ", action_required: true },
  { id: "EVT-103", timestamp: "2026-09-04T08:30:00Z", level: "info", message: "Shadow Block synchronization generated for B2 (Engineering J6 + S&T J4, duration 2h).", source: "Shadow Block Engine", division: "PRYJ" },
  { id: "EVT-104", timestamp: "2026-09-04T08:15:22Z", level: "critical", message: "Fixed block FB1 confirmed: Emergency bridge regirdering on B1 between 02:00 and 06:00.", source: "Chief Bridge Engineer", division: "PRYJ" },
  { id: "EVT-105", timestamp: "2026-09-04T07:45:11Z", level: "info", message: "Control Office Application (COA) CDC stream synced 8,420 train telemetry records via Apache Kafka.", source: "COA Ingestion", division: "PRYJ" },
  { id: "EVT-106", timestamp: "2026-09-04T07:10:00Z", level: "warning", message: "T6 RO-RO freight delayed by 3.0 hours due to loop holding at Hathras Junction.", source: "Traffic Controller", division: "PRYJ" },
];

export const mockAssetHealth: AssetHealthRecord[] = [
  {
    asset_id: "AST-TRK-B1-04",
    block_id: "B1",
    name: "Girder Bridge 42 Pier Bearing",
    asset_type: "Rail",
    chainage_start_km: 4.5,
    chainage_end_km: 6.2,
    health_score: 34,
    defect_severity: "Critical",
    degradation_velocity: 1.85,
    observed_defect_type: "Bridge Girder Bedplate Deflection > 8mm",
    model_predicted_risk: 0.94,
    last_ultrasonic_test: "2026-08-28",
    days_overdue: 0,
    associated_job_id: "J_FIXED_1"
  },
  {
    asset_id: "AST-TRK-B6-12",
    block_id: "B6",
    name: "Thermit Weld Joint W-144",
    asset_type: "Rail",
    chainage_start_km: 54.1,
    chainage_end_km: 55.0,
    health_score: 28,
    defect_severity: "Critical",
    degradation_velocity: 2.10,
    observed_defect_type: "Ultrasonic Flaw USFD IMR Crack (Immediate Rail Replacement)",
    model_predicted_risk: 0.96,
    last_ultrasonic_test: "2026-09-02",
    days_overdue: 24,
    associated_job_id: "J18"
  },
  {
    asset_id: "AST-SIG-B3-08",
    block_id: "B3",
    name: "AFTC Track Circuit Receiver 3R",
    asset_type: "Track Circuit",
    chainage_start_km: 23.1,
    chainage_end_km: 26.0,
    health_score: 41,
    defect_severity: "Major",
    degradation_velocity: 1.40,
    observed_defect_type: "Signal Attenuation Drop below 1.2V threshold",
    model_predicted_risk: 0.82,
    last_ultrasonic_test: "2026-08-15",
    days_overdue: 20,
    associated_job_id: "J16"
  },
  {
    asset_id: "AST-SIG-B5-02",
    block_id: "B5",
    name: "Electronic Interlocking Rack 02",
    asset_type: "Point Machine",
    chainage_start_km: 42.0,
    chainage_end_km: 45.0,
    health_score: 46,
    defect_severity: "Major",
    degradation_velocity: 1.25,
    observed_defect_type: "Optical Card Bit Error Rate intermittent spike",
    model_predicted_risk: 0.76,
    last_ultrasonic_test: "2026-08-18",
    days_overdue: 18,
    associated_job_id: "J7"
  },
  {
    asset_id: "AST-OHE-B5-18",
    block_id: "B5",
    name: "Traction Catenary Mast 44/12",
    asset_type: "OHE Mast",
    chainage_start_km: 41.5,
    chainage_end_km: 44.5,
    health_score: 55,
    defect_severity: "Major",
    degradation_velocity: 0.95,
    observed_defect_type: "Contact Wire Wear thickness 9.2mm (limit 8.5mm)",
    model_predicted_risk: 0.65,
    last_ultrasonic_test: "2026-08-20",
    days_overdue: 14,
    associated_job_id: "J14"
  },
  {
    asset_id: "AST-TRK-B2-07",
    block_id: "B2",
    name: "PSC Sleeper Track Section Hathras",
    asset_type: "Sleeper",
    chainage_start_km: 15.0,
    chainage_end_km: 18.0,
    health_score: 58,
    defect_severity: "Minor",
    degradation_velocity: 0.88,
    observed_defect_type: "Ballast Cushion Deficiency & Fouling Index 32%",
    model_predicted_risk: 0.58,
    last_ultrasonic_test: "2026-08-25",
    days_overdue: 12,
    associated_job_id: "J6"
  },
  {
    asset_id: "AST-OHE-B4-09",
    block_id: "B4",
    name: "Section Insulator Mast 36/04",
    asset_type: "OHE Mast",
    chainage_start_km: 34.2,
    chainage_end_km: 36.8,
    health_score: 62,
    defect_severity: "Minor",
    degradation_velocity: 0.72,
    observed_defect_type: "Catenary Sag Deviation +15mm",
    model_predicted_risk: 0.52,
    last_ultrasonic_test: "2026-08-22",
    days_overdue: 10,
    associated_job_id: "J1"
  },
  {
    asset_id: "AST-TRK-B7-11",
    block_id: "B7",
    name: "Turnout 1:12 Curved Switch 62B",
    asset_type: "Point Machine",
    chainage_start_km: 61.0,
    chainage_end_km: 62.0,
    health_score: 72,
    defect_severity: "Normal",
    degradation_velocity: 0.45,
    observed_defect_type: "Routine Point Wear within tolerances",
    model_predicted_risk: 0.35,
    last_ultrasonic_test: "2026-08-30",
    days_overdue: 4,
    associated_job_id: "J3"
  },
];

export const mockConflicts: ConflictItem[] = [
  {
    id: "CONF-FIXED-FB1",
    conflict_type: "fixed_block_collision",
    severity: "CRITICAL",
    block_id: "B1",
    title: "Mega Block Lock on B1",
    description: "Pre-scheduled immutable block FB1 occupies section B1 from T+2.0h to T+6.0h. All routine traffic and conflicting jobs barred.",
    affected_jobs: ["J15", "J17"],
    affected_trains: ["T6", "T8"],
    time_window: { start: 2.0, end: 6.0 },
    suggested_resolution: "Consolidate compatible routine jobs into shadow window or re-route express trains via loop line.",
    position: { x: -350.0, y: 1.0, z: 0.0 }
  },
  {
    id: "CONF-DEPT-J1-J7",
    conflict_type: "incompatible_department",
    severity: "MAJOR",
    block_id: "B4",
    title: "Cross-Department Safety Hazard on B4",
    description: "OHE 25kV power isolation on J1 conflicts with live circuit testing on J7 in section B4.",
    affected_jobs: ["J1", "J7"],
    affected_trains: [],
    time_window: { start: 10.0, end: 12.0 },
    suggested_resolution: "Sequence S&T point motor testing after 25kV traction re-energization or enforce joint permit-to-work.",
    position: { x: -50.0, y: 1.8, z: 2.0 }
  },
  {
    id: "CONF-OVERDUE-AST-TRK-B2-01",
    conflict_type: "overdue_critical_maintenance",
    severity: "CRITICAL",
    block_id: "B2",
    title: "Critical Defect: Switch Point Machine 104A (B2)",
    description: "Health score 42%, overdue by 14 days. Observed motor current surge during throw. High derailment probability.",
    affected_jobs: ["J2"],
    affected_trains: ["T6", "T8"],
    time_window: { start: 0.0, end: 24.0 },
    suggested_resolution: "Grant immediate emergency maintenance possession or impose 30 km/h caution order.",
    position: { x: -250.0, y: 1.2, z: 6.0 }
  },
  {
    id: "CONF-PREMIUM-T3",
    conflict_type: "premium_train_risk",
    severity: "WARNING",
    block_id: "B5",
    title: "Punctuality Risk: 22436 Vande Bharat Express (T3)",
    description: "Priority passenger service T3 scheduled window [2.0h - 5.0h] traverses corridor during heavy track possession. Risk of punctuality index degradation.",
    affected_jobs: [],
    affected_trains: ["T3"],
    time_window: { start: 2.0, end: 5.0 },
    suggested_resolution: "Lock green wave signal priority corridor; prohibit maintenance possession within 60 minutes of ETA.",
    position: { x: 50.0, y: 0.5, z: -2.0 }
  }
];

export const mockNetworkGeometry: NetworkGeometryResponse = {
  division: "Prayagraj (PRYJ)",
  line_name: "Subedarganj - Mirzapur Mainline Corridor",
  total_length_km: 80.0,
  is_synthetic: true,
  nodes: [
    { id: "NODE_SFG", name: "Subedarganj", code: "SFG", position: { x: -400.0, y: 0.0, z: 0.0 }, chainage_km: 0.0, node_type: "terminal", platforms: 4, connected_blocks: ["B1"] },
    { id: "NODE_PRYJ", name: "Prayagraj Jn", code: "PRYJ", position: { x: -300.0, y: 0.0, z: 2.0 }, chainage_km: 10.0, node_type: "junction", platforms: 8, connected_blocks: ["B1", "B2"] },
    { id: "NODE_NYN", name: "Naini Jn", code: "NYN", position: { x: -200.0, y: 1.5, z: 8.0 }, chainage_km: 20.0, node_type: "junction", platforms: 4, connected_blocks: ["B2", "B3"] },
    { id: "NODE_KCN", name: "Karchana", code: "KCN", position: { x: -100.0, y: 2.0, z: 4.0 }, chainage_km: 30.0, node_type: "station", platforms: 2, connected_blocks: ["B3", "B4"] },
    { id: "NODE_BEP", name: "Bheepur", code: "BEP", position: { x: 0.0, y: 0.5, z: -2.0 }, chainage_km: 40.0, node_type: "station", platforms: 2, connected_blocks: ["B4", "B5"] },
    { id: "NODE_MJA", name: "Meja Road", code: "MJA", position: { x: 100.0, y: -1.0, z: 5.0 }, chainage_km: 50.0, node_type: "station", platforms: 2, connected_blocks: ["B5", "B6"] },
    { id: "NODE_UND", name: "Unchdih", code: "UND", position: { x: 200.0, y: 1.0, z: 12.0 }, chainage_km: 60.0, node_type: "station", platforms: 2, connected_blocks: ["B6", "B7"] },
    { id: "NODE_MNF", name: "Manda Road", code: "MNF", position: { x: 300.0, y: 2.5, z: 6.0 }, chainage_km: 70.0, node_type: "station", platforms: 2, connected_blocks: ["B7", "B8"] },
    { id: "NODE_MZP", name: "Mirzapur", code: "MZP", position: { x: 400.0, y: 0.0, z: 0.0 }, chainage_km: 80.0, node_type: "junction", platforms: 4, connected_blocks: ["B8"] }
  ],
  tracks: [
    {
      block_id: "B1",
      name: "Subedarganj to Prayagraj (B1)",
      start_coord: { x: -400.0, y: 0.0, z: 0.0 },
      end_coord: { x: -300.0, y: 0.0, z: 2.0 },
      path_points: [
        { x: -400.0, y: 0.0, z: 0.0 },
        { x: -380.0, y: 0.2, z: 0.5 },
        { x: -360.0, y: 0.4, z: 1.0 },
        { x: -340.0, y: 0.3, z: 1.5 },
        { x: -320.0, y: 0.1, z: 1.8 },
        { x: -300.0, y: 0.0, z: 2.0 }
      ],
      length_km: 10.0,
      chainage_start: 0.0,
      chainage_end: 10.0,
      elevation_profile: [0.0, 0.2, 0.4, 0.3, 0.1, 0.0],
      track_type: "Mainline",
      electrification: "25kV AC",
      speed_limit_kmh: 110.0
    },
    {
      block_id: "B2",
      name: "Prayagraj to Naini (B2)",
      start_coord: { x: -300.0, y: 0.0, z: 2.0 },
      end_coord: { x: -200.0, y: 1.5, z: 8.0 },
      path_points: [
        { x: -300.0, y: 0.0, z: 2.0 },
        { x: -280.0, y: 0.5, z: 3.5 },
        { x: -260.0, y: 1.0, z: 5.0 },
        { x: -240.0, y: 1.2, z: 6.5 },
        { x: -220.0, y: 1.4, z: 7.5 },
        { x: -200.0, y: 1.5, z: 8.0 }
      ],
      length_km: 10.0,
      chainage_start: 10.0,
      chainage_end: 20.0,
      elevation_profile: [0.0, 0.5, 1.0, 1.2, 1.4, 1.5],
      track_type: "Mainline",
      electrification: "25kV AC",
      speed_limit_kmh: 80.0
    },
    {
      block_id: "B3",
      name: "Naini to Karchana (B3)",
      start_coord: { x: -200.0, y: 1.5, z: 8.0 },
      end_coord: { x: -100.0, y: 2.0, z: 4.0 },
      path_points: [
        { x: -200.0, y: 1.5, z: 8.0 },
        { x: -180.0, y: 1.7, z: 7.2 },
        { x: -160.0, y: 1.9, z: 6.0 },
        { x: -140.0, y: 2.0, z: 5.0 },
        { x: -120.0, y: 2.0, z: 4.4 },
        { x: -100.0, y: 2.0, z: 4.0 }
      ],
      length_km: 10.0,
      chainage_start: 20.0,
      chainage_end: 30.0,
      elevation_profile: [1.5, 1.7, 1.9, 2.0, 2.0, 2.0],
      track_type: "Mainline",
      electrification: "25kV AC",
      speed_limit_kmh: 120.0
    },
    {
      block_id: "B4",
      name: "Karchana to Bheepur (B4)",
      start_coord: { x: -100.0, y: 2.0, z: 4.0 },
      end_coord: { x: 0.0, y: 0.5, z: -2.0 },
      path_points: [
        { x: -100.0, y: 2.0, z: 4.0 },
        { x: -80.0, y: 1.6, z: 2.5 },
        { x: -60.0, y: 1.2, z: 1.0 },
        { x: -40.0, y: 0.9, z: -0.2 },
        { x: -20.0, y: 0.7, z: -1.2 },
        { x: 0.0, y: 0.5, z: -2.0 }
      ],
      length_km: 10.0,
      chainage_start: 30.0,
      chainage_end: 40.0,
      elevation_profile: [2.0, 1.6, 1.2, 0.9, 0.7, 0.5],
      track_type: "Mainline",
      electrification: "25kV AC",
      speed_limit_kmh: 75.0
    },
    {
      block_id: "B5",
      name: "Bheepur to Meja Road (B5)",
      start_coord: { x: 0.0, y: 0.5, z: -2.0 },
      end_coord: { x: 100.0, y: -1.0, z: 5.0 },
      path_points: [
        { x: 0.0, y: 0.5, z: -2.0 },
        { x: 20.0, y: 0.1, z: -0.5 },
        { x: 40.0, y: -0.3, z: 1.0 },
        { x: 60.0, y: -0.7, z: 2.8 },
        { x: 80.0, y: -0.9, z: 4.1 },
        { x: 100.0, y: -1.0, z: 5.0 }
      ],
      length_km: 10.0,
      chainage_start: 40.0,
      chainage_end: 50.0,
      elevation_profile: [0.5, 0.1, -0.3, -0.7, -0.9, -1.0],
      track_type: "Mainline",
      electrification: "25kV AC",
      speed_limit_kmh: 130.0
    },
    {
      block_id: "B6",
      name: "Meja Road to Unchdih (B6)",
      start_coord: { x: 100.0, y: -1.0, z: 5.0 },
      end_coord: { x: 200.0, y: 1.0, z: 12.0 },
      path_points: [
        { x: 100.0, y: -1.0, z: 5.0 },
        { x: 120.0, y: -0.5, z: 6.8 },
        { x: 140.0, y: 0.0, z: 8.5 },
        { x: 160.0, y: 0.4, z: 10.0 },
        { x: 180.0, y: 0.7, z: 11.2 },
        { x: 200.0, y: 1.0, z: 12.0 }
      ],
      length_km: 10.0,
      chainage_start: 50.0,
      chainage_end: 60.0,
      elevation_profile: [-1.0, -0.5, 0.0, 0.4, 0.7, 1.0],
      track_type: "Mainline",
      electrification: "25kV AC",
      speed_limit_kmh: 90.0
    },
    {
      block_id: "B7",
      name: "Unchdih to Manda Road (B7)",
      start_coord: { x: 200.0, y: 1.0, z: 12.0 },
      end_coord: { x: 300.0, y: 2.5, z: 6.0 },
      path_points: [
        { x: 200.0, y: 1.0, z: 12.0 },
        { x: 220.0, y: 1.4, z: 10.8 },
        { x: 240.0, y: 1.8, z: 9.2 },
        { x: 260.0, y: 2.1, z: 8.0 },
        { x: 280.0, y: 2.3, z: 7.0 },
        { x: 300.0, y: 2.5, z: 6.0 }
      ],
      length_km: 10.0,
      chainage_start: 60.0,
      chainage_end: 70.0,
      elevation_profile: [1.0, 1.4, 1.8, 2.1, 2.3, 2.5],
      track_type: "Mainline",
      electrification: "25kV AC",
      speed_limit_kmh: 120.0
    },
    {
      block_id: "B8",
      name: "Manda Road to Mirzapur (B8)",
      start_coord: { x: 300.0, y: 2.5, z: 6.0 },
      end_coord: { x: 400.0, y: 0.0, z: 0.0 },
      path_points: [
        { x: 300.0, y: 2.5, z: 6.0 },
        { x: 320.0, y: 2.0, z: 4.8 },
        { x: 340.0, y: 1.5, z: 3.4 },
        { x: 360.0, y: 1.0, z: 2.0 },
        { x: 380.0, y: 0.5, z: 0.8 },
        { x: 400.0, y: 0.0, z: 0.0 }
      ],
      length_km: 10.0,
      chainage_start: 70.0,
      chainage_end: 80.0,
      elevation_profile: [2.5, 2.0, 1.5, 1.0, 0.5, 0.0],
      track_type: "Mainline",
      electrification: "25kV AC",
      speed_limit_kmh: 130.0
    }
  ],
  signals: [
    { id: "SIG_B1_UP", block_id: "B1", chainage_km: 0.5, position: { x: -396.0, y: 0.0, z: 1.5 }, aspect: "clear", direction: "UP" },
    { id: "SIG_B1_DN", block_id: "B1", chainage_km: 9.5, position: { x: -304.0, y: 0.0, z: -1.5 }, aspect: "clear", direction: "DOWN" },
    { id: "SIG_B2_UP", block_id: "B2", chainage_km: 10.5, position: { x: -296.0, y: 0.1, z: 3.5 }, aspect: "caution", direction: "UP" },
    { id: "SIG_B2_DN", block_id: "B2", chainage_km: 19.5, position: { x: -204.0, y: 1.4, z: 6.5 }, aspect: "clear", direction: "DOWN" },
    { id: "SIG_B3_UP", block_id: "B3", chainage_km: 20.5, position: { x: -196.0, y: 1.5, z: 9.5 }, aspect: "clear", direction: "UP" },
    { id: "SIG_B3_DN", block_id: "B3", chainage_km: 29.5, position: { x: -104.0, y: 2.0, z: 2.5 }, aspect: "clear", direction: "DOWN" },
    { id: "SIG_B4_UP", block_id: "B4", chainage_km: 30.5, position: { x: -96.0, y: 1.9, z: 5.5 }, aspect: "danger", direction: "UP" },
    { id: "SIG_B4_DN", block_id: "B4", chainage_km: 39.5, position: { x: -4.0, y: 0.5, z: -3.5 }, aspect: "danger", direction: "DOWN" },
    { id: "SIG_B5_UP", block_id: "B5", chainage_km: 40.5, position: { x: 4.0, y: 0.5, z: -0.5 }, aspect: "clear", direction: "UP" },
    { id: "SIG_B5_DN", block_id: "B5", chainage_km: 49.5, position: { x: 96.0, y: -0.9, z: 6.5 }, aspect: "clear", direction: "DOWN" },
    { id: "SIG_B6_UP", block_id: "B6", chainage_km: 50.5, position: { x: 104.0, y: -1.0, z: 6.5 }, aspect: "clear", direction: "UP" },
    { id: "SIG_B6_DN", block_id: "B6", chainage_km: 59.5, position: { x: 196.0, y: 0.9, z: 10.5 }, aspect: "clear", direction: "DOWN" },
    { id: "SIG_B7_UP", block_id: "B7", chainage_km: 60.5, position: { x: 204.0, y: 1.0, z: 13.5 }, aspect: "clear", direction: "UP" },
    { id: "SIG_B7_DN", block_id: "B7", chainage_km: 69.5, position: { x: 296.0, y: 2.4, z: 4.5 }, aspect: "clear", direction: "DOWN" },
    { id: "SIG_B8_UP", block_id: "B8", chainage_km: 70.5, position: { x: 304.0, y: 2.5, z: 7.5 }, aspect: "clear", direction: "UP" },
    { id: "SIG_B8_DN", block_id: "B8", chainage_km: 79.5, position: { x: 396.0, y: 0.0, z: -1.5 }, aspect: "clear", direction: "DOWN" }
  ],
  ohe_masts: [
    { id: "OHE_B1_M1", block_id: "B1", position: { x: -380.0, y: 0.2, z: 2.2 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B1_M2", block_id: "B1", position: { x: -350.0, y: 0.3, z: 3.2 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B1_M3", block_id: "B1", position: { x: -320.0, y: 0.1, z: 4.0 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B2_M1", block_id: "B2", position: { x: -280.0, y: 0.5, z: 5.7 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B2_M2", block_id: "B2", position: { x: -250.0, y: 1.1, z: 8.2 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B2_M3", block_id: "B2", position: { x: -220.0, y: 1.4, z: 9.7 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B3_M1", block_id: "B3", position: { x: -180.0, y: 1.7, z: 9.4 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B3_M2", block_id: "B3", position: { x: -150.0, y: 1.95, z: 7.7 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B3_M3", block_id: "B3", position: { x: -120.0, y: 2.0, z: 6.6 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B4_M1", block_id: "B4", position: { x: -80.0, y: 1.6, z: 4.7 }, catenary_height_m: 5.5, is_isolated: true },
    { id: "OHE_B4_M2", block_id: "B4", position: { x: -50.0, y: 1.05, z: 2.6 }, catenary_height_m: 5.5, is_isolated: true },
    { id: "OHE_B4_M3", block_id: "B4", position: { x: -20.0, y: 0.7, z: 1.0 }, catenary_height_m: 5.5, is_isolated: true },
    { id: "OHE_B5_M1", block_id: "B5", position: { x: 20.0, y: 0.1, z: 1.7 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B5_M2", block_id: "B5", position: { x: 50.0, y: -0.5, z: 4.1 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B5_M3", block_id: "B5", position: { x: 80.0, y: -0.9, z: 6.3 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B6_M1", block_id: "B6", position: { x: 120.0, y: -0.5, z: 9.0 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B6_M2", block_id: "B6", position: { x: 150.0, y: 0.2, z: 11.5 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B6_M3", block_id: "B6", position: { x: 180.0, y: 0.7, z: 13.4 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B7_M1", block_id: "B7", position: { x: 220.0, y: 1.4, z: 13.0 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B7_M2", block_id: "B7", position: { x: 250.0, y: 1.95, z: 10.8 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B7_M3", block_id: "B7", position: { x: 280.0, y: 2.3, z: 9.2 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B8_M1", block_id: "B8", position: { x: 320.0, y: 2.0, z: 7.0 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B8_M2", block_id: "B8", position: { x: 350.0, y: 1.25, z: 4.9 }, catenary_height_m: 5.5, is_isolated: false },
    { id: "OHE_B8_M3", block_id: "B8", position: { x: 380.0, y: 0.5, z: 3.0 }, catenary_height_m: 5.5, is_isolated: false }
  ],
  blocks: mockScenario.blocks,
  conflicts: mockConflicts
};

export const mockPlanningCapabilities: PlanningCapabilitiesResponse = {
  solver_available: true,
  solver_name: "PySCIPOpt (MIP Solver)",
  fallback_active: false,
  model_mode: "rule_based",
  model_version: "1.0.0",
  supports_3d_geometry: true,
  demo_mode: true,
  supported_horizons_days: [7, 14, 28],
  routes_available: ["Subedarganj - Mirzapur Mainline", "Naini Jn - Chheoki Bypass", "Prayagraj West Freight Loop"],
  max_blocks_capacity: 100,
  max_trains_capacity: 200
};
