import json
import os
import math
import random
from typing import List, Dict, Any, Optional
from src.data_pipeline.models import (
    TrackBlock,
    Train,
    MaintenanceJob,
    Resource,
    TCIInputs,
    Scenario,
    Department,
    FixedMaintenanceBlock,
    AssetHealthRecord,
    SystemEvent,
    Vector3D,
    Coordinate3D,
    TrackGeometry,
    GeometryTrack,
    StationNode,
    JunctionNode,
    SignalMarker,
    OHEMast,
    ConflictType,
    ConflictItem,
    NetworkConflict,
    CoordinateSystemContract,
    NetworkGeometryResponse,
    OptimizedSchedule
)

def generate_synthetic_data(
    seed: int = 42,
    num_blocks: int = 8,
    num_jobs: int = 20,
    num_trains: int = 10
) -> Scenario:
    """Generates deterministic synthetic data for one bounded railway division."""
    random.seed(seed)
    
    # 1. Block Sections
    blocks = []
    for i in range(num_blocks):
        blocks.append(TrackBlock(
            id=f"B{i+1}", 
            chainage_start=float(i * 10), 
            chainage_end=float((i + 1) * 10), 
            description=f"Station {chr(65+i)} to {chr(66+i)}",
            speed_restriction_kmh=100.0 if i != 1 else 75.0,
            track_type="Mainline",
            electrification_status="25kV AC",
            signaling_type="Automatic"
        ))
        
    # 2. Resources
    resources = [
        Resource(id="R_BCM", name="Ballast Cleaning Machine", capacity=2, department=Department.ENGINEERING),
        Resource(id="R_CREW_OHE", name="OHE Maintenance Crew", capacity=4, department=Department.OHE),
        Resource(id="R_CREW_SIG", name="Signal Testing Crew", capacity=3, department=Department.S_AND_T),
        Resource(id="R_TIE", name="Tie Tamper", capacity=1, department=Department.ENGINEERING)
    ]
    
    # 3. Trains
    trains = []
    for i in range(num_trains):
        is_premium = i < 3
        cat = "premium" if is_premium else "freight"
        start_t = float(i)
        end_t = start_t + (3.0 if is_premium else 6.0)
        
        # Stagger routes
        route_len = random.randint(3, min(6, num_blocks))
        if is_premium:
            start_idx = random.randint(max(0, num_blocks // 2), max(0, num_blocks - min(2, route_len)))
        else:
            start_idx = random.randint(0, max(0, num_blocks - route_len))
            
        route_blocks = [f"B{j+1}" for j in range(start_idx, min(num_blocks, start_idx + route_len))]
        if not route_blocks:
            route_blocks = [f"B{num_blocks}"]
            
        mtt = {b: 0.5 if is_premium else 1.0 for b in route_blocks}
        
        trains.append(Train(
            id=f"T{i+1}",
            name=f"Vande Bharat Exp {20000+i}" if is_premium else f"Container Freight {50000+i}",
            category=cat,
            scheduled_start=start_t,
            scheduled_end=end_t,
            route=route_blocks,
            min_travel_times=mtt,
            max_speed_kmh=130.0 if is_premium else 75.0
        ))
        
    # 4. Maintenance Jobs
    jobs = []
    departments = [Department.ENGINEERING, Department.OHE, Department.S_AND_T]
    flexible_count = max(0, num_jobs - 2)
    
    for i in range(flexible_count):
        dept = random.choice(departments)
        b_id = f"B{random.randint(1, num_blocks)}"
        dur = float(random.choice([1.0, 2.0, 3.0]))
        
        if dept == Department.ENGINEERING:
            req_res = {"R_BCM": 1} if random.random() > 0.5 else {"R_TIE": 1}
            job_type = "Track Tamping & Ballast Cleaning"
        elif dept == Department.OHE:
            req_res = {"R_CREW_OHE": 1}
            job_type = "OHE Cantilever & Contact Wire Inspection"
        else:
            req_res = {"R_CREW_SIG": 1}
            job_type = "Point Machine & Track Circuit Testing"
            
        tci_inputs = TCIInputs(
            safety_severity=round(random.uniform(0.1, 1.0), 2),
            traffic_impact=round(random.uniform(0.1, 1.0), 2),
            degradation_indicator=round(random.uniform(0.1, 1.0), 2),
            overdue_days=random.randint(0, 40)
        )
        
        jobs.append(MaintenanceJob(
            id=f"J{i+1}",
            department=dept,
            block_id=b_id,
            duration=dur,
            required_resources=req_res,
            tci_inputs=tci_inputs,
            is_fixed=False,
            job_type=job_type,
            safety_clearance_required="Power Isolation & Permit-to-Work" if dept == Department.OHE else "Standard Track Possession Clearance",
            chainage_km=f"KM {(random.randint(0, num_blocks-1))*10}.0"
        ))
        
    # 2 Fixed Jobs (if num_jobs >= 2)
    if num_jobs >= 2:
        jobs.append(MaintenanceJob(
            id="J_FIXED_1",
            department=Department.ENGINEERING,
            block_id="B1",
            duration=4.0,
            required_resources={"R_BCM": 1},
            tci_inputs=TCIInputs(safety_severity=1.0, traffic_impact=1.0, degradation_indicator=1.0, overdue_days=0),
            is_fixed=True,
            fixed_start=2.0,
            job_type="Deep Screening Turnout Renewal",
            safety_clearance_required="Full Line Block + Speed Restriction 30 km/h"
        ))
        jobs.append(MaintenanceJob(
            id="J_FIXED_2",
            department=Department.OHE,
            block_id="B4" if num_blocks >= 4 else "B2",
            duration=2.0,
            required_resources={"R_CREW_OHE": 1},
            tci_inputs=TCIInputs(safety_severity=1.0, traffic_impact=1.0, degradation_indicator=1.0, overdue_days=0),
            is_fixed=True,
            fixed_start=10.0,
            job_type="Overhead Mast Replacement & Power Block",
            safety_clearance_required="25kV Traction Power Isolation PTW"
        ))
        
        fixed_blocks = [
            FixedMaintenanceBlock(id="FB1", block_id="B1", start_time=2.0, end_time=6.0, reason="Weekly Track Deep Screening"),
            FixedMaintenanceBlock(id="FB2", block_id="B4" if num_blocks >= 4 else "B2", start_time=10.0, end_time=12.0, reason="OHE Mast Replacement")
        ]
    else:
        fixed_blocks = []
    
    return Scenario(blocks=blocks, trains=trains, jobs=jobs, resources=resources, fixed_blocks=fixed_blocks)

def save_synthetic_data(
    path: str = "data/synthetic",
    seed: int = 42,
    num_blocks: int = 8,
    num_jobs: int = 20,
    num_trains: int = 10
) -> str:
    """Saves the generated scenario to a JSON file."""
    os.makedirs(path, exist_ok=True)
    scenario = generate_synthetic_data(
        seed=seed,
        num_blocks=num_blocks,
        num_jobs=num_jobs,
        num_trains=num_trains
    )
    file_path = os.path.join(path, "scenario.json")
    with open(file_path, "w") as f:
        f.write(scenario.model_dump_json(indent=4))
    return file_path

def pos_at_corridor_km(km: float, total_km: float = 80.0, lateral_offset: float = 0.0) -> Vector3D:
    ratio = km / max(1.0, total_km)
    x = -400.0 + (ratio * 800.0)
    # Gentle realistic railway curve: maximum 16m lateral deviation
    z = math.sin(ratio * math.pi * 2.5) * 16.0 + lateral_offset
    # Gentle elevation: grade up to +3.5m over river bridges / flyovers
    y = math.sin(ratio * math.pi * 3.0) * 2.5 + (0.5 if 18.0 <= km <= 24.0 else 0.0)
    return Vector3D(x=round(x, 2), y=round(y, 2), z=round(z, 2))

def generate_synthetic_assets(scenario: Scenario) -> List[AssetHealthRecord]:
    """Generates asset health telemetry synchronized with current scenario blocks."""
    blocks = scenario.blocks
    total_km = blocks[-1].chainage_end if blocks else 80.0
    assets = [
        AssetHealthRecord(
            asset_id="AST-TRK-B2-01",
            block_id="B2",
            name="Point Machine 104A",
            asset_type="Point Machine",
            chainage_start_km=12.4,
            chainage_end_km=12.6,
            health_score=42.0,
            defect_severity="Critical",
            degradation_velocity=4.2,
            observed_defect_type="Motor current surge during throw",
            model_predicted_risk=0.88,
            last_ultrasonic_test="2026-08-20",
            days_overdue=14,
            associated_job_id="J2",
            position=pos_at_corridor_km(12.4, total_km, lateral_offset=2.5),
            geometry_source="synthetic",
            geometry_schema_version="1.0.0"
        ),
        AssetHealthRecord(
            asset_id="AST-OHE-B4-09",
            block_id="B4" if len(scenario.blocks) >= 4 else "B1",
            name="Catenary Wire Span 40-42",
            asset_type="OHE Mast",
            chainage_start_km=34.2,
            chainage_end_km=34.8,
            health_score=68.0,
            defect_severity="Major",
            degradation_velocity=2.1,
            observed_defect_type="Dropper wear exceeding 15%",
            model_predicted_risk=0.64,
            last_ultrasonic_test="2026-08-14",
            days_overdue=7,
            associated_job_id="J_FIXED_2",
            position=pos_at_corridor_km(34.2, total_km, lateral_offset=2.2),
            geometry_source="synthetic",
            geometry_schema_version="1.0.0"
        ),
        AssetHealthRecord(
            asset_id="AST-TRK-B1-04",
            block_id="B1",
            name="Weld Joint W-102",
            asset_type="Rail",
            chainage_start_km=4.8,
            chainage_end_km=5.0,
            health_score=85.0,
            defect_severity="Minor",
            degradation_velocity=1.0,
            observed_defect_type="Surface micro-spalling",
            model_predicted_risk=0.25,
            last_ultrasonic_test="2026-08-28",
            days_overdue=0,
            associated_job_id="J_FIXED_1",
            position=pos_at_corridor_km(4.8, total_km, lateral_offset=0.0),
            geometry_source="synthetic",
            geometry_schema_version="1.0.0"
        )
    ]
    return assets

def generate_synthetic_events() -> List[SystemEvent]:
    """Generates standard telemetry events for the control room stream."""
    import time
    now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return [
        SystemEvent(
            id="EVT-1001",
            timestamp=now_str,
            level="info",
            message="PySCIPOpt MILP solver optimized 24h horizon with 0.0% gap.",
            source="MILP Optimizer",
            division="PRYJ"
        ),
        SystemEvent(
            id="EVT-1002",
            timestamp=now_str,
            level="warning",
            message="Ghost train reservation enforced on Block B2 to preserve express train paths.",
            source="Conflict Engine",
            division="PRYJ"
        ),
        SystemEvent(
            id="EVT-1003",
            timestamp=now_str,
            level="info",
            message="Multi-department shadow block consolidated across Engineering and OHE on section B4.",
            source="Block Planner",
            division="PRYJ"
        )
    ]

def derive_conflicts(scenario: Scenario, schedule: Optional[OptimizedSchedule] = None) -> List[ConflictItem]:
    """
    Derives realistic operational conflicts from scenario and schedule states:
    1. Fixed block possession collisions (heavy machine or high speed path overlap)
    2. Incompatible department overlap (OHE 25kV power block vs S&T live testing)
    3. High-risk overdue critical asset requiring emergency speed restriction or immediate possession
    4. Train movement vs planned possession risk (train scheduled through possession window)
    5. Resource over-allocation (e.g. BCM machine requested simultaneously)
    """
    conflicts: List[ConflictItem] = []
    
    # 1. Fixed Block Collisions or Mega Block Possession
    for fb in scenario.fixed_blocks:
        conflicts.append(ConflictItem(
            id=f"CONF-FIXED-{fb.id}",
            conflict_type=ConflictType.FIXED_BLOCK_COLLISION,
            severity="CRITICAL",
            block_id=fb.block_id,
            title=f"Mega Block Lock on {fb.block_id}",
            description=f"Pre-scheduled immutable block {fb.id} occupies section {fb.block_id} from T+{fb.start_time:.1f}h to T+{fb.end_time:.1f}h. All routine traffic and conflicting jobs barred.",
            affected_jobs=[j.id for j in scenario.jobs if j.block_id == fb.block_id and not j.is_fixed],
            affected_trains=[t.id for t in scenario.trains if fb.block_id in t.route],
            time_window={"start": fb.start_time, "end": fb.end_time},
            suggested_resolution="Consolidate compatible routine jobs into shadow window or re-route express trains via loop line.",
            position=Vector3D(x=-300.0 if fb.block_id == "B1" else 0.0, y=1.0, z=0.0)
        ))

    # 2. Department Safety Incompatibility (OHE 25kV vs S&T)
    ohe_jobs = [j for j in scenario.jobs if j.department == Department.OHE]
    sig_jobs = [j for j in scenario.jobs if j.department == Department.S_AND_T]
    for oj in ohe_jobs:
        for sj in sig_jobs:
            if oj.block_id == sj.block_id:
                conflicts.append(ConflictItem(
                    id=f"CONF-DEPT-{oj.id}-{sj.id}",
                    conflict_type=ConflictType.DEPT_INCOMPATIBLE,
                    severity="MAJOR",
                    block_id=oj.block_id,
                    title=f"Cross-Department Safety Hazard on {oj.block_id}",
                    description=f"OHE power isolation on {oj.id} conflicts with live circuit testing on {sj.id} in section {oj.block_id}.",
                    affected_jobs=[oj.id, sj.id],
                    affected_trains=[],
                    time_window={"start": 4.0, "end": 6.0},
                    suggested_resolution="Sequence S&T point motor testing after 25kV traction re-energization or enforce joint permit-to-work.",
                    position=Vector3D(x=-100.0, y=2.0, z=4.0)
                ))
                break
        if len(conflicts) >= 4:
            break

    # 3. Overdue Critical Maintenance
    assets = generate_synthetic_assets(scenario)
    for ast in assets:
        if ast.health_score < 50.0 and ast.days_overdue > 7:
            conflicts.append(ConflictItem(
                id=f"CONF-OVERDUE-{ast.asset_id}",
                conflict_type=ConflictType.OVERDUE_CRITICAL,
                severity="CRITICAL",
                block_id=ast.block_id,
                title=f"Critical Defect: {ast.name} ({ast.block_id})",
                description=f"Health score {ast.health_score}%, overdue by {ast.days_overdue} days. Defect: {ast.observed_defect_type}. High derailment probability.",
                affected_jobs=[ast.associated_job_id] if ast.associated_job_id else [],
                affected_trains=[t.id for t in scenario.trains if ast.block_id in t.route and t.category == "premium"],
                time_window={"start": 0.0, "end": 24.0},
                suggested_resolution="Grant immediate emergency maintenance slot or impose 30 km/h caution order.",
                position=Vector3D(x=-200.0 if ast.block_id == "B2" else 0.0, y=1.5, z=8.0)
            ))

    # 4. Premium Train Headway / Risk
    premium_trains = [t for t in scenario.trains if t.category == "premium"]
    if premium_trains:
        pt = premium_trains[0]
        conflicts.append(ConflictItem(
            id=f"CONF-PREMIUM-{pt.id}",
            conflict_type=ConflictType.PREMIUM_TRAIN,
            severity="WARNING",
            block_id=pt.route[0] if pt.route else "B1",
            title=f"Punctuality Risk: {pt.name} ({pt.id})",
            description=f"Priority passenger service {pt.id} scheduled window [{pt.scheduled_start:.1f}h - {pt.scheduled_end:.1f}h] traverses congested work zone. Risk of punctuality index degradation.",
            affected_jobs=[],
            affected_trains=[pt.id],
            time_window={"start": pt.scheduled_start, "end": pt.scheduled_end},
            suggested_resolution="Lock green wave signal priority corridor; prohibit maintenance grant within 60 minutes of ETA.",
            position=Vector3D(x=-350.0, y=0.0, z=1.0)
        ))

    # 5. Scheduled conflicts if schedule is available
    if schedule:
        # Check train vs scheduled maintenance window
        for sj in schedule.scheduled_jobs:
            for train in scenario.trains:
                if sj.block_id in train.route:
                    # Train traverses this block
                    if not (train.scheduled_end <= sj.start_time or train.scheduled_start >= sj.end_time):
                        conflicts.append(ConflictItem(
                            id=f"CONF-SCHED-{train.id}-{sj.job_id}",
                            conflict_type=ConflictType.TRAIN_BLOCK,
                            severity="CRITICAL" if train.category == "premium" else "MAJOR",
                            block_id=sj.block_id,
                            title=f"Train Contention: {train.id} vs {sj.job_id}",
                            description=f"Train {train.id} ({train.category}) scheduled during maintenance closure T+{sj.start_time:.1f}h-T+{sj.end_time:.1f}h on {sj.block_id}.",
                            affected_jobs=[sj.job_id],
                            affected_trains=[train.id],
                            time_window={"start": max(train.scheduled_start, sj.start_time), "end": min(train.scheduled_end, sj.end_time)},
                            suggested_resolution="Apply MILP train retiming or loop diversion.",
                            position=Vector3D(x=-150.0, y=1.0, z=5.0)
                        ))

    return conflicts

def generate_network_geometry(scenario: Scenario) -> NetworkGeometryResponse:
    """
    Generates realistic 3D spatial geometry for the corridor network.
    Coordinates are scaled to a 3D visualization scene:
    X: Corridor longitudinal axis (meters / scaled units, from -400 to +400)
    Y: Elevation / Gradient (meters, realistic 1:1000 or slight curves)
    Z: Lateral offset / Curve track curvature
    """
    blocks = scenario.blocks
    total_km = blocks[-1].chainage_end if blocks else 80.0
    
    # Station definitions along the Prayagraj-Mirzapur corridor
    station_templates = [
        {"code": "SFG", "name": "Subedarganj", "type": "terminal", "km": 0.0},
        {"code": "PRYJ", "name": "Prayagraj Jn", "type": "junction", "km": 10.0},
        {"code": "NYN", "name": "Naini Jn", "type": "junction", "km": 20.0},
        {"code": "KCN", "name": "Karchana", "type": "station", "km": 30.0},
        {"code": "BEP", "name": "Bheepur", "type": "station", "km": 40.0},
        {"code": "MJA", "name": "Meja Road", "type": "station", "km": 50.0},
        {"code": "UND", "name": "Unchdih", "type": "station", "km": 60.0},
        {"code": "MNF", "name": "Manda Road", "type": "station", "km": 70.0},
        {"code": "MZP", "name": "Mirzapur", "type": "junction", "km": 80.0},
    ]
    
    def km_to_x(km: float) -> float:
        ratio = km / max(1.0, total_km)
        return -400.0 + (ratio * 800.0)
    
    def pos_at_km(km: float, lateral_offset: float = 0.0) -> Vector3D:
        return pos_at_corridor_km(km, total_km, lateral_offset)

    nodes: List[StationNode] = []
    for stn in station_templates:
        if stn["km"] <= total_km + 5.0:
            connected = [b.id for b in blocks if b.chainage_start <= stn["km"] <= b.chainage_end]
            nodes.append(StationNode(
                id=f"NODE_{stn['code']}",
                name=stn["name"],
                code=stn["code"],
                position=pos_at_km(stn["km"]),
                chainage_km=stn["km"],
                node_type=stn["type"],
                platforms=4 if stn["type"] == "junction" else 2,
                connected_blocks=connected
            ))

    tracks: List[TrackGeometry] = []
    signals: List[SignalMarker] = []
    ohe_masts: List[OHEMast] = []

    for block in blocks:
        start_pt = pos_at_km(block.chainage_start)
        end_pt = pos_at_km(block.chainage_end)
        
        steps = 5
        path_points: List[Vector3D] = []
        elevation_profile: List[float] = []
        for s in range(steps + 1):
            curr_km = block.chainage_start + (block.chainage_end - block.chainage_start) * (s / steps)
            pt = pos_at_km(curr_km)
            path_points.append(pt)
            elevation_profile.append(pt.y)

        tracks.append(TrackGeometry(
            block_id=block.id,
            name=f"{block.description} ({block.id})",
            start_coord=start_pt,
            end_coord=end_pt,
            path_points=path_points,
            length_km=round(block.chainage_end - block.chainage_start, 2),
            chainage_start=block.chainage_start,
            chainage_end=block.chainage_end,
            elevation_profile=elevation_profile,
            track_type=block.track_type or "Mainline",
            electrification=block.electrification_status or "25kV AC",
            speed_limit_kmh=block.speed_restriction_kmh or 110.0
        ))

        # Signals
        signals.append(SignalMarker(
            id=f"SIG_{block.id}_UP",
            block_id=block.id,
            chainage_km=round(block.chainage_start + 0.5, 2),
            position=pos_at_km(block.chainage_start + 0.5, lateral_offset=1.5),
            aspect="caution" if block.id == "B2" else "clear",
            direction="UP"
        ))
        signals.append(SignalMarker(
            id=f"SIG_{block.id}_DN",
            block_id=block.id,
            chainage_km=round(block.chainage_end - 0.5, 2),
            position=pos_at_km(block.chainage_end - 0.5, lateral_offset=-1.5),
            aspect="clear",
            direction="DOWN"
        ))

        # OHE masts
        for mast_idx in range(3):
            mast_km = block.chainage_start + (block.chainage_end - block.chainage_start) * ((mast_idx + 0.5) / 3.0)
            ohe_masts.append(OHEMast(
                id=f"OHE_{block.id}_M{mast_idx+1}",
                block_id=block.id,
                position=pos_at_km(mast_km, lateral_offset=2.2),
                catenary_height_m=5.5,
                is_isolated=(block.id == "B4")
            ))

    conflicts = derive_conflicts(scenario)

    junctions: List[JunctionNode] = []
    for stn in station_templates:
        if stn["type"] == "junction" and stn["km"] <= total_km + 5.0:
            connected = [b.id for b in blocks if b.chainage_start <= stn["km"] <= b.chainage_end]
            junctions.append(JunctionNode(
                id=f"JUNC_{stn['code']}",
                name=f"{stn['name']} Interlocking Junction",
                code=stn["code"],
                coordinates=pos_at_km(stn["km"]),
                position=pos_at_km(stn["km"]),
                chainage_km=stn["km"],
                node_type="junction",
                diverging_blocks=connected,
                switch_type="Turnout 1-in-12",
                interlocking_status="Active"
            ))

    assets = generate_synthetic_assets(scenario)

    return NetworkGeometryResponse(
        geometry_schema_version="1.0.0",
        coordinate_system=CoordinateSystemContract(
            name="LOCAL_CORRIDOR",
            crs="LOCAL_CORRIDOR",
            units="meters",
            axis_order=["x", "y", "z"],
            handedness="right-handed",
            origin_description="Synthetic local origin for the bounded railway division",
            geometry_source="synthetic"
        ),
        division="Prayagraj (PRYJ)",
        line_name="Subedarganj - Mirzapur Mainline Corridor",
        total_length_km=total_km,
        is_synthetic=True,
        geometry_source="synthetic",
        coordinate_convention="X: corridor longitudinal (m), Y: elevation (m), Z: lateral offset (m)",
        schema_version="1.0.0",
        nodes=nodes,
        tracks=tracks,
        signals=signals,
        ohe_masts=ohe_masts,
        blocks=blocks,
        conflicts=conflicts,
        junctions=junctions,
        assets=assets,
        disconnected_components=[]
    )

if __name__ == "__main__":
    save_synthetic_data()
    print("Synthetic data generated successfully.")
