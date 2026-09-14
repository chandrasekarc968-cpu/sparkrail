import pytest
from src.data_pipeline.synthetic_data import generate_synthetic_data
from src.ai_ml.justification_generator import JustificationGenerator
from src.data_pipeline.models import WeatherContext

def test_justification_generator_bilingual():
    scenario = generate_synthetic_data(seed=42, num_blocks=8, num_jobs=10, num_trains=6)
    job = scenario.jobs[0]
    
    scheduled_info = {
        "block_id": job.block_id,
        "start_time": 4.0,
        "end_time": 6.0,
        "is_shadow_block": True,
        "shadow_with_jobs": ["J2", "J3"]
    }

    justification = JustificationGenerator.generate_job_justification(
        job=job,
        scheduled_info=scheduled_info,
        scenario=scenario,
        job_tci=82.5
    )

    assert justification.job_id == job.id
    assert justification.headline_en
    assert justification.headline_hi
    assert "ब्लॉक" in justification.headline_hi
    assert len(justification.detailed_en) > 10
    assert len(justification.detailed_hi) > 10
    assert len(justification.binding_constraints) >= 1

def test_kinetic_energy_calculation():
    # 5,000 tonnes at 75 km/h
    # 0.5 * 5,000,000 kg * (75 / 3.6 m/s)^2 = 1.085e9 Joules = ~301.4 kWh
    energy = JustificationGenerator.calculate_kinetic_energy_kwh(5000.0, 75.0)
    assert 290.0 <= energy <= 315.0

def test_weather_and_crew_narrative():
    scenario = generate_synthetic_data(seed=42, num_blocks=6, num_jobs=6, num_trains=4)
    # Simulate high rail temp
    scenario.weather = WeatherContext(
        ambient_temp_celsius=42.0,
        rail_temp_celsius=64.0,
        destressing_temp_celsius=40.0,
        fog_visibility_meters=1500.0
    )
    job = scenario.jobs[0]
    scheduled_info = {"block_id": job.block_id, "start_time": 1.0, "end_time": 3.0}

    just = JustificationGenerator.generate_job_justification(
        job=job,
        scheduled_info=scheduled_info,
        scenario=scenario,
        job_tci=60.0
    )
    assert "IRPWM Para 509 Summer Rail Buckling Guard" in just.binding_constraints
    assert "बकलिंग" in just.tradeoff_hi or "तापमान" in just.tradeoff_hi
