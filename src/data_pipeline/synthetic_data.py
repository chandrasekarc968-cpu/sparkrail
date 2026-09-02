import json
import os
import random
from src.data_pipeline.models import TrackBlock, Train, MaintenanceJob, Resource, TCIInputs, Scenario, Department, FixedMaintenanceBlock

def generate_synthetic_data(seed: int = 42) -> Scenario:
    """Generates deterministic synthetic data for one bounded railway division."""
    random.seed(seed)
    
    # 1. Block Sections (8 blocks)
    blocks = []
    for i in range(8):
        blocks.append(TrackBlock(
            id=f"B{i+1}", 
            chainage_start=float(i * 10), 
            chainage_end=float((i + 1) * 10), 
            description=f"Station {chr(65+i)} to {chr(66+i)}"
        ))
        
    # 2. Resources
    resources = [
        Resource(id="R_BCM", name="Ballast Cleaning Machine", capacity=2),
        Resource(id="R_CREW_OHE", name="OHE Maintenance Crew", capacity=4),
        Resource(id="R_CREW_SIG", name="Signal Testing Crew", capacity=3),
        Resource(id="R_TIE", name="Tie Tamper", capacity=1)
    ]
    
    # 3. Trains (10 trains)
    trains = []
    for i in range(10):
        is_premium = i < 3
        cat = "premium" if is_premium else "freight"
        # premium runs 0-5, freight runs 2-10 etc.
        start_t = float(i)
        end_t = start_t + (3.0 if is_premium else 6.0)
        
        # Stagger routes
        route_len = random.randint(3, 6)
        if is_premium:
            # Avoid fixed blocks (B1, B4) to prevent infeasible hard constraints
            start_idx = random.randint(4, 7 - min(2, route_len))
        else:
            start_idx = random.randint(0, 8 - route_len)
            
        route_blocks = [f"B{j+1}" for j in range(start_idx, min(8, start_idx + route_len))]
        
        # Min travel times
        mtt = {b: 0.5 if is_premium else 1.0 for b in route_blocks}
        
        trains.append(Train(
            id=f"T{i+1}",
            category=cat,
            scheduled_start=start_t,
            scheduled_end=end_t,
            route=route_blocks,
            min_travel_times=mtt
        ))
        
    # 4. Maintenance Jobs (20 jobs)
    jobs = []
    departments = [Department.ENGINEERING, Department.OHE, Department.S_AND_T]
    
    for i in range(18): # 18 flexible jobs
        dept = random.choice(departments)
        b_id = f"B{random.randint(1, 8)}"
        dur = random.choice([1.0, 2.0, 3.0])
        
        if dept == Department.ENGINEERING:
            req_res = {"R_BCM": 1} if random.random() > 0.5 else {"R_TIE": 1}
        elif dept == Department.OHE:
            req_res = {"R_CREW_OHE": 1}
        else:
            req_res = {"R_CREW_SIG": 1}
            
        tci_inputs = TCIInputs(
            safety_severity=random.uniform(0.1, 1.0),
            traffic_impact=random.uniform(0.1, 1.0),
            degradation_indicator=random.uniform(0.1, 1.0),
            overdue_days=random.randint(0, 40)
        )
        
        jobs.append(MaintenanceJob(
            id=f"J{i+1}",
            department=dept,
            block_id=b_id,
            duration=dur,
            required_resources=req_res,
            tci_inputs=tci_inputs,
            is_fixed=False
        ))
        
    # 2 Fixed Jobs
    jobs.append(MaintenanceJob(
        id="J_FIXED_1", department=Department.ENGINEERING, block_id="B1", duration=4.0,
        required_resources={"R_BCM": 1},
        tci_inputs=TCIInputs(safety_severity=1.0, traffic_impact=1.0, degradation_indicator=1.0, overdue_days=0),
        is_fixed=True, fixed_start=2.0
    ))
    jobs.append(MaintenanceJob(
        id="J_FIXED_2", department=Department.OHE, block_id="B4", duration=2.0,
        required_resources={"R_CREW_OHE": 1},
        tci_inputs=TCIInputs(safety_severity=1.0, traffic_impact=1.0, degradation_indicator=1.0, overdue_days=0),
        is_fixed=True, fixed_start=10.0
    ))
    
    fixed_blocks = [
        FixedMaintenanceBlock(id="FB1", block_id="B1", start_time=2.0, end_time=6.0),
        FixedMaintenanceBlock(id="FB2", block_id="B4", start_time=10.0, end_time=12.0)
    ]
    
    return Scenario(blocks=blocks, trains=trains, jobs=jobs, resources=resources, fixed_blocks=fixed_blocks)

def save_synthetic_data(path: str = "data/synthetic") -> None:
    """Saves the generated data to a JSON file."""
    os.makedirs(path, exist_ok=True)
    scenario = generate_synthetic_data()
    
    with open(os.path.join(path, "scenario.json"), "w") as f:
        f.write(scenario.model_dump_json(indent=4))

if __name__ == "__main__":
    save_synthetic_data()
    print("Synthetic data generated successfully.")
