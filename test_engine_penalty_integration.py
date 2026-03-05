#!/usr/bin/env python3
"""
Simple integration test for Engine Penalty System.

Tests the complete flow:
1. Load circuit config with engine penalty parameters
2. Create a car with team code
3. Run update_section() and verify engine penalty is applied
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from python_backend.lap_simulator.config_loader import load_circuit_config
from python_backend.lap_simulator.data_types import (
    CarState, PUState, DriverIntent, DriverSkills, EnvContext,
    EngineMapName, WheelPosition, TyreCompound, TyreState
)
from python_backend.lap_simulator.update_section import update_section


def test_engine_penalty_integration():
    """Test engine penalty integration with update_section."""
    
    # Load Baku circuit config (has engine penalty parameters)
    config = load_circuit_config("az-2016_baku")
    
    # Verify engine penalty config is loaded
    assert config.engine_reference_cv == 1008.0
    assert config.engine_penalty_coeff == 0.01
    assert "QUALY" in config.engine_map_penalties
    assert config.engine_map_penalties["QUALY"] == 0.0
    
    # Create car state for RBR (Honda engine, 1015 CV)
    car_state = CarState(
        car_id="rbr_test",
        team_code="RBR",  # This will be used for engine CV lookup
        pu=PUState(
            active_map=EngineMapName.STANDARD,
            fuel_kg=20.0,
        )
    )
    
    # Add tyres
    for wp in WheelPosition:
        car_state.tyres[wp] = TyreState(
            wheel_pos=wp,
            compound=TyreCompound.C5,
        )
    
    # Create driver intent
    driver_intent = DriverIntent(
        pace_factor=1.0,
        push_level=10,
    )
    
    # Create driver skills
    driver_skills = DriverSkills()
    
    # Create environment
    env = EnvContext()
    
    # Get a straight section from Baku
    straight_section = None
    for section in config.sections:
        if section.kind.value in ["Straight", "MediumStraight"]:
            straight_section = section
            break
    
    assert straight_section is not None, "No straight section found"
    
    # Create aero setup
    from python_backend.lap_simulator.data_types import AeroSetup
    aero_setup = AeroSetup()
    
    # Run update_section
    result = update_section(
        car_state=car_state,
        aero_setup=aero_setup,
        driver_skills=driver_skills,
        section=straight_section,
        env=env,
        config=config,
        push_level=10,
        is_qualifying=True,
        circuit_id="az-2016_baku",
        driver_id="test_driver",
        lap_number=1,
    )
    
    # Verify engine penalty was applied
    assert result.engine_penalty_s > 0.0, "Engine penalty should be positive for RBR"
    
    # Expected: CV penalty (+7 CV × 0.01 = +0.07s) + map penalty (STANDARD = +0.25s)
    expected_engine_penalty = 0.07 + 0.25
    assert abs(result.engine_penalty_s - expected_engine_penalty) < 0.01, \
        f"Expected {expected_engine_penalty}, got {result.engine_penalty_s}"
    
    print(f"✓ Engine penalty integration test passed!")
    print(f"  - RBR CV: 1015 (vs Mercedes 1008)")
    print(f"  - Engine penalty applied: {result.engine_penalty_s:.3f}s")
    print(f"  - Expected: {expected_engine_penalty:.3f}s")
    
    # Test with QUALY map (should have no map penalty)
    car_state.pu.active_map = EngineMapName.QUALY
    result_qualy = update_section(
        car_state=car_state,
        aero_setup=aero_setup,
        driver_skills=driver_skills,
        section=straight_section,
        env=env,
        config=config,
        push_level=10,
        is_qualifying=True,
        circuit_id="az-2016_baku",
        driver_id="test_driver",
        lap_number=1,
    )
    
    # Should only have CV penalty, no map penalty
    expected_qualy_penalty = 0.07  # Only CV penalty
    assert abs(result_qualy.engine_penalty_s - expected_qualy_penalty) < 0.01, \
        f"Expected {expected_qualy_penalty}, got {result_qualy.engine_penalty_s}"
    
    print(f"✓ QUALY map test passed!")
    print(f"  - Engine penalty with QUALY map: {result_qualy.engine_penalty_s:.3f}s")
    print(f"  - Expected: {expected_qualy_penalty:.3f}s")
    
    # Test with corner section (should have no engine penalty)
    corner_section = None
    for section in config.sections:
        if "Corner" in section.kind.value:
            corner_section = section
            break
    
    if corner_section:
        result_corner = update_section(
            car_state=car_state,
            aero_setup=aero_setup,
            driver_skills=driver_skills,
            section=corner_section,
            env=env,
            config=config,
            push_level=10,
            is_qualifying=True,
            circuit_id="az-2016_baku",
            driver_id="test_driver",
            lap_number=1,
        )
        
        assert result_corner.engine_penalty_s == 0.0, "Engine penalty should be 0 on corners"
        print(f"✓ Corner section test passed! Engine penalty: {result_corner.engine_penalty_s:.3f}s")
    
    print(f"\n🎉 All engine penalty integration tests passed!")


if __name__ == "__main__":
    test_engine_penalty_integration()
