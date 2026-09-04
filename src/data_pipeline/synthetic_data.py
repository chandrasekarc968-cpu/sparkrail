import json
import os
import random
from typing import List
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
    SystemEvent
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

def generate_synthetic_assets(scenario: Scenario) -> List[AssetHealthRecord]:
    """Generates asset health telemetry synchronized with current scenario blocks."""
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
            associated_job_id="J2"
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
            associated_job_id="J_FIXED_2"
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
            associated_job_id="J_FIXED_1"
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

if __name__ == "__main__":
    save_synthetic_data()
    print("Synthetic data generated successfully.")
