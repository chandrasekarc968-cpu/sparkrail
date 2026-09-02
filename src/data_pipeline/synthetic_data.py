import json
import os
from src.data_pipeline.models import BlockSection, Train, MaintenanceJob, Resource, TCIInputs, Scenario

def generate_synthetic_data() -> Scenario:
    """Generates deterministic synthetic data for one bounded railway division."""
    
    # 1. Block Sections (Discrete operational sections mapped to chainage)
    blocks = [
        BlockSection(id="B1", chainage_start=0.0, chainage_end=10.0, description="Station A to B"),
        BlockSection(id="B2", chainage_start=10.0, chainage_end=25.0, description="Station B to C"),
        BlockSection(id="B3", chainage_start=25.0, chainage_end=40.0, description="Station C to D"),
    ]
    
    # 2. Resources (Track machines, crews)
    resources = [
        Resource(id="R_BCM", name="Ballast Cleaning Machine", capacity=1),
        Resource(id="R_CREW_OHE", name="OHE Maintenance Crew", capacity=2),
        Resource(id="R_CREW_SIG", name="Signal Testing Crew", capacity=2),
    ]
    
    # 3. Trains (Premium, Express, Freight)
    trains = [
        Train(id="T1", category="premium", scheduled_start=2.0, scheduled_end=5.0, 
              route=["B1", "B2", "B3"], min_travel_times={"B1": 1.0, "B2": 1.0, "B3": 1.0}),
        Train(id="T2", category="freight", scheduled_start=3.0, scheduled_end=9.0, 
              route=["B2", "B3"], min_travel_times={"B2": 2.0, "B3": 2.0}),
    ]
    
    # 4. Maintenance Jobs (across multiple departments for shadow block potential)
    jobs = [
        # Engineering Job
        MaintenanceJob(
            id="J_ENG_1", department="Engineering", block_id="B2", duration=2.0,
            required_resources={"R_BCM": 1},
            tci_inputs=TCIInputs(safety_severity=0.8, traffic_impact=0.9, degradation_indicator=0.7, overdue_days=2),
            is_fixed=False
        ),
        # OHE Job on same block (Compatible for shadow block)
        MaintenanceJob(
            id="J_OHE_1", department="OHE", block_id="B2", duration=2.0,
            required_resources={"R_CREW_OHE": 1},
            tci_inputs=TCIInputs(safety_severity=0.5, traffic_impact=0.6, degradation_indicator=0.4, overdue_days=5),
            is_fixed=False
        ),
        # Signal Job on different block
        MaintenanceJob(
            id="J_SIG_1", department="S&T", block_id="B3", duration=1.0,
            required_resources={"R_CREW_SIG": 1},
            tci_inputs=TCIInputs(safety_severity=0.9, traffic_impact=0.8, degradation_indicator=0.6, overdue_days=0),
            is_fixed=False
        ),
        # Fixed maintenance block (e.g., mega block already sanctioned)
        MaintenanceJob(
            id="J_FIXED_1", department="Engineering", block_id="B1", duration=2.0,
            required_resources={"R_BCM": 0}, # Assume handled
            tci_inputs=TCIInputs(safety_severity=1.0, traffic_impact=1.0, degradation_indicator=1.0, overdue_days=0),
            is_fixed=True, fixed_start=6.0
        )
    ]
    
    return Scenario(blocks=blocks, trains=trains, jobs=jobs, resources=resources)

def save_synthetic_data(path: str = "data/synthetic") -> None:
    """Saves the generated data to a JSON file."""
    os.makedirs(path, exist_ok=True)
    scenario = generate_synthetic_data()
    
    with open(os.path.join(path, "scenario.json"), "w") as f:
        # Pydantic v2 usage
        f.write(scenario.model_dump_json(indent=4))

if __name__ == "__main__":
    save_synthetic_data()
    print("Synthetic data generated successfully.")
