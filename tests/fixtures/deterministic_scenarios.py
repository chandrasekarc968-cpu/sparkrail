"""
Deterministic scenarios and fixtures for SparkRail Indian Railways optimization test suite.
Provides repeatable test fixtures for multi-tier optimization, safety invariants,
disruption handling, and BDMS advisory governance.
"""

from typing import List, Tuple
from src.data_pipeline.models import (
    Scenario,
    TrackBlock,
    MaintenanceJob,
    Train,
    TrainPriority,
    PossessionLifecycle,
    ElementaryElectricalSection,
    Department,
    TCIInputs
)


def get_standard_blocks() -> List[TrackBlock]:
    """Returns 8 contiguous 10km block sections along PRYJ-MZP corridor."""
    return [
        TrackBlock(id="B1", chainage_start=0.0, chainage_end=10.0, description="SFG to PRYJ", track_type="Mainline", speed_restriction_kmh=110.0, electrification_status="25kV AC", signaling_type="Automatic"),
        TrackBlock(id="B2", chainage_start=10.0, chainage_end=20.0, description="PRYJ to NYN", track_type="Mainline", speed_restriction_kmh=80.0, electrification_status="25kV AC", signaling_type="Automatic"),
        TrackBlock(id="B3", chainage_start=20.0, chainage_end=30.0, description="NYN to KCN", track_type="Mainline", speed_restriction_kmh=120.0, electrification_status="25kV AC", signaling_type="Automatic"),
        TrackBlock(id="B4", chainage_start=30.0, chainage_end=40.0, description="KCN to BEP", track_type="Mainline", speed_restriction_kmh=75.0, electrification_status="25kV AC", signaling_type="Automatic"),
        TrackBlock(id="B5", chainage_start=40.0, chainage_end=50.0, description="BEP to MJA", track_type="Mainline", speed_restriction_kmh=130.0, electrification_status="25kV AC", signaling_type="Automatic"),
        TrackBlock(id="B6", chainage_start=50.0, chainage_end=60.0, description="MJA to UND", track_type="Mainline", speed_restriction_kmh=90.0, electrification_status="25kV AC", signaling_type="Automatic"),
        TrackBlock(id="B7", chainage_start=60.0, chainage_end=70.0, description="UND to MNF", track_type="Mainline", speed_restriction_kmh=120.0, electrification_status="25kV AC", signaling_type="Automatic"),
        TrackBlock(id="B8", chainage_start=70.0, chainage_end=80.0, description="MNF to MZP", track_type="Mainline", speed_restriction_kmh=130.0, electrification_status="25kV AC", signaling_type="Automatic"),
    ]


def create_compatible_shadow_bundle_scenario() -> Scenario:
    """
    Scenario: Civil Track Tamping (J_CIVIL) + OHE Contact Wire Renewal (J_OHE)
    Both request Block B5 during overlapping time windows [14.0, 18.0].
    Department pair Engineering + OHE is compatible (Civil under de-energized OHE).
    """
    blocks = get_standard_blocks()
    jobs = [
        MaintenanceJob(
            id="J_CIVIL_01",
            block_id="B5",
            department=Department.ENGINEERING,
            duration=2.5,
            required_resources={"R_TIE": 1},
            job_type="Tamping & Track Packing",
            tci_inputs=TCIInputs(safety_severity=0.8, traffic_impact=0.6, degradation_indicator=0.75, overdue_days=15),
            chainage_km="42.0-46.0"
        ),
        MaintenanceJob(
            id="J_OHE_01",
            block_id="B5",
            department=Department.OHE,
            duration=3.0,
            required_resources={"R_CREW_OHE": 1},
            job_type="Contact Wire Renewal",
            tci_inputs=TCIInputs(safety_severity=0.85, traffic_impact=0.65, degradation_indicator=0.7, overdue_days=12),
            chainage_km="41.0-48.0"
        )
    ]
    trains = [
        Train(
            id="T_PASS_01",
            name="12428 Prayagraj Express",
            category="express",
            scheduled_start=19.0,
            scheduled_end=20.0,
            route=["B5"],
            min_travel_times={"B5": 0.3}
        )
    ]
    return Scenario(blocks=blocks, jobs=jobs, trains=trains, resources=[])


def create_incompatible_ohe_snt_scenario() -> Scenario:
    """
    Scenario: OHE 25kV power isolation (J_OHE) + S&T live circuit testing (J_SNT).
    Both request Block B4 during window [10.0, 14.0].
    Safety Rule: S&T live circuit testing is incompatible with simultaneous 25kV de-energization/grounding.
    Must NOT be bundled into a shadow possession.
    """
    blocks = get_standard_blocks()
    jobs = [
        MaintenanceJob(
            id="J_OHE_ISO",
            block_id="B4",
            department=Department.OHE,
            duration=2.0,
            required_resources={"R_CREW_OHE": 1},
            job_type="25kV Catenary Isolation",
            tci_inputs=TCIInputs(safety_severity=0.75, traffic_impact=0.5, degradation_indicator=0.6, overdue_days=10),
            chainage_km="32.0-38.0"
        ),
        MaintenanceJob(
            id="J_SNT_LIVE",
            block_id="B4",
            department=Department.S_AND_T,
            duration=2.0,
            required_resources={"R_CREW_SIG": 1},
            job_type="Live AFTC Circuit Modulation",
            tci_inputs=TCIInputs(safety_severity=0.7, traffic_impact=0.5, degradation_indicator=0.55, overdue_days=8),
            chainage_km="33.0-36.0"
        )
    ]
    return Scenario(blocks=blocks, jobs=jobs, trains=[], resources=[])


def create_premium_train_conflict_scenario() -> Scenario:
    """
    Scenario: High priority Vande Bharat Express (22436) traversing B2 between 14:00 and 15:00.
    A heavy BCM track ballast cleaning possession J_BCM requests 4 hours [13:00 to 17:00].
    Safety Invariant: Class 1 passenger trains must have zero delay.
    """
    blocks = get_standard_blocks()
    jobs = [
        MaintenanceJob(
            id="J_BCM_BALLAST",
            block_id="B2",
            department=Department.ENGINEERING,
            duration=4.0,
            required_resources={"R_BCM": 1},
            job_type="BCM Ballast Deep Screening",
            tci_inputs=TCIInputs(safety_severity=0.65, traffic_impact=0.7, degradation_indicator=0.6, overdue_days=14),
            chainage_km="12.0-18.0"
        )
    ]
    trains = [
        Train(
            id="T_VANDE_BHARAT",
            name="22436 Vande Bharat Express",
            category="premium",
            scheduled_start=14.0,
            scheduled_end=15.0,
            route=["B2"],
            min_travel_times={"B2": 0.25}
        )
    ]
    return Scenario(blocks=blocks, jobs=jobs, trains=trains, resources=[])


def create_granted_possession_scenario() -> Scenario:
    """
    Scenario: J_ACTIVE is already GRANTED and IN_PROGRESS on B1 from 02:00 to 06:00.
    Safety Invariant: GRANTED and IN_PROGRESS possessions are physically immutable.
    """
    blocks = get_standard_blocks()
    jobs = [
        MaintenanceJob(
            id="J_ACTIVE_GRANT",
            block_id="B1",
            department=Department.ENGINEERING,
            duration=4.0,
            required_resources={"R_BCM": 1},
            job_type="Emergency Bridge Bearing Regirdering",
            tci_inputs=TCIInputs(safety_severity=0.95, traffic_impact=0.85, degradation_indicator=0.9, overdue_days=25),
            chainage_km="4.0-8.0",
            is_fixed=True,
            fixed_start=2.0
        ),
        MaintenanceJob(
            id="J_ROUTINE_01",
            block_id="B2",
            department=Department.S_AND_T,
            duration=1.5,
            required_resources={"R_CREW_SIG": 1},
            job_type="Point Machine Lubrication",
            tci_inputs=TCIInputs(safety_severity=0.45, traffic_impact=0.3, degradation_indicator=0.4, overdue_days=5),
            chainage_km="14.0-16.0"
        )
    ]
    return Scenario(blocks=blocks, jobs=jobs, trains=[], resources=[])


def create_ohe_isolation_scenario() -> Tuple[Scenario, ElementaryElectricalSection]:
    """
    Scenario: Elementary Electrical Section ES-B4-01 is isolated (de-energized).
    An electric passenger train attempts to traverse B4 during isolation.
    """
    scen = Scenario(
        blocks=get_standard_blocks(),
        jobs=[
            MaintenanceJob(
                id="J_OHE_RENEWAL",
                block_id="B4",
                department=Department.OHE,
                duration=2.0,
                required_resources={"R_CREW_OHE": 1},
                job_type="Bracket Assembly Overhaul",
                tci_inputs=TCIInputs(safety_severity=0.75, traffic_impact=0.5, degradation_indicator=0.6, overdue_days=10),
                chainage_km="31.0-39.0"
            )
        ],
        trains=[
            Train(
                id="T_ELEC_TRAIN",
                name="12301 Rajdhani Express",
                category="premium",
                scheduled_start=10.0,
                scheduled_end=12.0,
                route=["B4"],
                min_travel_times={"B4": 0.25}
            )
        ],
        resources=[]
    )
    es = ElementaryElectricalSection(
        id="ES-B4-01",
        section_id="ES-B4-01",
        name="Karchana Up Catenary Elementary Section",
        feeding_post_id="FP-KCN",
        is_isolated=True,
        chainage_start_km=30.0,
        chainage_end_km=40.0,
        block_ids=["B4"]
    )
    return scen, es
