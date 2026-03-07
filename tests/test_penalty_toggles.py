#!/usr/bin/env python3
"""
Test suite for Penalty System Toggle functionality.

Tests all penalty system flags to ensure they properly enable/disable
individual penalty components.
"""
import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "python_backend"))
sys.path.insert(0, str(PROJECT_ROOT))

from python_backend.lap_simulator.config_loader import load_circuit_config
from python_backend.lap_simulator.data_types import (
    CarState, PUState, DriverIntent, DriverSkills, EnvContext,
    EngineMapName, WheelPosition, TyreCompound, TyreState, AeroSetup
)
from python_backend.lap_simulator.update_section import update_section

# Import flags to test
from python_backend.utils.game_logic import (
    USE_NEW_PENALTY_SYSTEM,
    ENABLE_FUEL_PENALTIES,
    ENABLE_TYRE_PENALTIES,
    ENABLE_DRIVER_SKILL_PENALTIES,
    ENABLE_ENGINE_PENALTIES,
    ENABLE_ENGINE_MAP_PENALTIES,
    ENABLE_BRAKE_PENALTIES,
    ENABLE_SETUP_PENALTIES,
)


def create_test_car(team_code="MCL", fuel_kg=50.0, push_level=5):
    """Create a test car with basic configuration."""
    car_state = CarState(
        car_id="test_car",
        team_code=team_code,
        pu=PUState(
            active_map=EngineMapName.STANDARD,
            fuel_kg=fuel_kg,
        )
    )
    
    # Add tyres
    for wp in WheelPosition:
        car_state.tyres[wp] = TyreState(
            wheel_pos=wp,
            compound=TyreCompound.C3,
        )
    
    return car_state


def test_flag_values():
    """Test that all penalty flags are properly defined."""
    print("🧪 Testing flag definitions...")
    
    # Test master flag
    assert isinstance(USE_NEW_PENALTY_SYSTEM, bool), "USE_NEW_PENALTY_SYSTEM should be boolean"
    print(f"  ✅ USE_NEW_PENALTY_SYSTEM: {USE_NEW_PENALTY_SYSTEM}")
    
    # Test individual flags
    flags = {
        "ENABLE_FUEL_PENALTIES": ENABLE_FUEL_PENALTIES,
        "ENABLE_TYRE_PENALTIES": ENABLE_TYRE_PENALTIES,
        "ENABLE_DRIVER_SKILL_PENALTIES": ENABLE_DRIVER_SKILL_PENALTIES,
        "ENABLE_ENGINE_PENALTIES": ENABLE_ENGINE_PENALTIES,
        "ENABLE_ENGINE_MAP_PENALTIES": ENABLE_ENGINE_MAP_PENALTIES,
        "ENABLE_BRAKE_PENALTIES": ENABLE_BRAKE_PENALTIES,
        "ENABLE_SETUP_PENALTIES": ENABLE_SETUP_PENALTIES,
    }
    
    for flag_name, flag_value in flags.items():
        assert isinstance(flag_value, bool), f"{flag_name} should be boolean"
        print(f"  ✅ {flag_name}: {flag_value}")


def test_penalty_system_with_master_disabled():
    """Test that all penalties are zero when master flag is False."""
    print("🧪 Testing master flag override...")
    
    # Temporarily set master flag to False by direct module patch
    import python_backend.lap_simulator.update_section as update_module
    original_value = update_module.USE_NEW_PENALTY_SYSTEM
    update_module.USE_NEW_PENALTY_SYSTEM = False
    
    try:
        config = load_circuit_config("it-1922_monza")
        car_state = create_test_car(fuel_kg=80.0)  # Heavy fuel
        driver_skills = DriverSkills()
        aero_setup = AeroSetup()
        env = EnvContext()
        
        # Get a straight section
        straight_section = config.sections[0]
        
        result = update_section(
            car_state=car_state,
            aero_setup=aero_setup,
            driver_skills=driver_skills,
            section=straight_section,
            env=env,
            config=config,
            push_level=5  # Low push = penalty
        )
        
        # All penalties should be 0 when master disabled
        assert result.fuel_penalty_s == 0.0, f"Fuel penalty should be 0, got {result.fuel_penalty_s}"
        assert result.tyre_penalty_s == 0.0, f"Tyre penalty should be 0, got {result.tyre_penalty_s}"
        assert result.engine_penalty_s == 0.0, f"Engine penalty should be 0, got {result.engine_penalty_s}"
        assert result.brake_penalty_s == 0.0, f"Brake penalty should be 0, got {result.brake_penalty_s}"
        assert result.setup_penalty_s == 0.0, f"Setup penalty should be 0, got {result.setup_penalty_s}"
        
        print(f"  ✅ Master flag OFF: All penalties = 0.0s")
        
    finally:
        # Restore original value
        update_module.USE_NEW_PENALTY_SYSTEM = original_value


def test_individual_flag_logic():
    """Test that individual flag logic works in isolation."""
    print("🧪 Testing individual flag logic...")
    
    # Test fuel penalty logic directly
    config = load_circuit_config("it-1922_monza")
    car_state = create_test_car(fuel_kg=80.0)
    
    # Simulate the fuel penalty calculation
    fuel_delta_s = 0.0
    if ENABLE_FUEL_PENALTIES and USE_NEW_PENALTY_SYSTEM and config.fuel_penalty_coeff > 0.0:
        extra_fuel = max(0.0, car_state.pu.fuel_kg - config.fuel_reference_kg)
        section_fraction = 100.0 / config.circuit_length_m  # Assume 100m section
        fuel_delta_s = config.fuel_penalty_coeff * extra_fuel * section_fraction
    
    if ENABLE_FUEL_PENALTIES and USE_NEW_PENALTY_SYSTEM:
        assert fuel_delta_s > 0.0, "Fuel penalty should be > 0 when enabled"
        print(f"  ✅ Fuel penalty logic: {fuel_delta_s:.3f}s (enabled)")
    else:
        assert fuel_delta_s == 0.0, "Fuel penalty should be 0 when disabled"
        print(f"  ✅ Fuel penalty logic: {fuel_delta_s:.3f}s (disabled)")
    
    # Test engine map penalty logic
    from python_backend.lap_simulator.engine_penalty import DEFAULT_ENGINE_MAP_PENALTIES
    
    map_penalty = 0.0
    if ENABLE_ENGINE_MAP_PENALTIES:
        map_penalties = DEFAULT_ENGINE_MAP_PENALTIES
        map_penalty = map_penalties.get(EngineMapName.STANDARD, 0.0)
    
    if ENABLE_ENGINE_MAP_PENALTIES:
        assert map_penalty > 0.0, "Engine map penalty should be > 0 when enabled"
        print(f"  ✅ Engine map penalty logic: {map_penalty:.3f}s (enabled)")
    else:
        assert map_penalty == 0.0, "Engine map penalty should be 0 when disabled"
        print(f"  ✅ Engine map penalty logic: {map_penalty:.3f}s (disabled)")


def test_fallback_values():
    """Test that fallback values work when flags are not available."""
    print("🧪 Testing fallback values...")
    
    # Test fallback in update_section module
    import python_backend.lap_simulator.update_section as update_module
    
    # Check that fallback values are defined
    assert hasattr(update_module, 'USE_NEW_PENALTY_SYSTEM'), "Fallback USE_NEW_PENALTY_SYSTEM should exist"
    assert hasattr(update_module, 'ENABLE_FUEL_PENALTIES'), "Fallback ENABLE_FUEL_PENALTIES should exist"
    assert hasattr(update_module, 'ENABLE_TYRE_PENALTIES'), "Fallback ENABLE_TYRE_PENALTIES should exist"
    
    # Check fallback values
    assert update_module.USE_NEW_PENALTY_SYSTEM == True, "Fallback should be True"
    assert update_module.ENABLE_FUEL_PENALTIES == True, "Fallback should be True"
    assert update_module.ENABLE_TYRE_PENALTIES == True, "Fallback should be True"
    
    print(f"  ✅ Fallback values defined correctly")


def run_all_toggle_tests():
    """Run all penalty toggle tests."""
    print("🚀 Starting Penalty System Toggle Tests...\n")
    
    try:
        test_flag_values()
        print()
        
        test_individual_flag_logic()
        print()
        
        test_penalty_system_with_master_disabled()
        print()
        
        test_fallback_values()
        print()
        
        print("🎉 All penalty toggle tests passed!")
        print("\n📋 Summary:")
        print(f"  - Master flag: USE_NEW_PENALTY_SYSTEM = {USE_NEW_PENALTY_SYSTEM}")
        print(f"  - Fuel penalties: {'ENABLED' if ENABLE_FUEL_PENALTIES else 'DISABLED'}")
        print(f"  - Tyre penalties: {'ENABLED' if ENABLE_TYRE_PENALTIES else 'DISABLED'}")
        print(f"  - Driver skill penalties: {'ENABLED' if ENABLE_DRIVER_SKILL_PENALTIES else 'DISABLED'}")
        print(f"  - Engine penalties: {'ENABLED' if ENABLE_ENGINE_PENALTIES else 'DISABLED'}")
        print(f"  - Engine map penalties: {'ENABLED' if ENABLE_ENGINE_MAP_PENALTIES else 'DISABLED'}")
        print(f"  - Brake penalties: {'ENABLED' if ENABLE_BRAKE_PENALTIES else 'DISABLED'}")
        print(f"  - Setup penalties: {'ENABLED' if ENABLE_SETUP_PENALTIES else 'DISABLED'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_toggle_tests()
    sys.exit(0 if success else 1)
