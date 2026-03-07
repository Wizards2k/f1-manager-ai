#!/usr/bin/env python3
"""
Debug cache issue - simplified test to isolate the problem.
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
from python_backend.lap_simulator.penalty_cache import get_penalty_cache, clear_penalty_cache

def create_test_car(team_code="MCL", fuel_kg=50.0):
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

def debug_cache_issue():
    """Debug the cache issue step by step."""
    print("🔍 Debugging cache issue...")
    
    config = load_circuit_config("it-1922_monza")
    car_state = create_test_car(fuel_kg=80.0)
    driver_skills = DriverSkills()
    aero_setup = AeroSetup()
    env = EnvContext()
    section = config.sections[0]
    
    print(f"Section: {section.section_id}")
    print(f"Car fuel: {car_state.pu.fuel_kg}kg")
    
    # Test 1: Run without cache
    clear_penalty_cache(config.circuit_id)
    
    # Disable cache temporarily
    import python_backend.lap_simulator.update_section as update_module
    original_cache_enabled = update_module.ENABLE_PENALTY_CACHE
    update_module.ENABLE_PENALTY_CACHE = False
    
    result1 = update_section(
        car_state=car_state,
        aero_setup=aero_setup,
        driver_skills=driver_skills,
        section=section,
        env=env,
        config=config,
        push_level=5
    )
    
    print(f"Without cache: {result1.dt_s:.6f}s")
    print(f"  Fuel penalty: {result1.fuel_penalty_s:.6f}s")
    print(f"  Engine penalty: {result1.engine_penalty_s:.6f}s")
    
    # Test 2: Run with cache disabled but cache populated
    update_module.ENABLE_PENALTY_CACHE = original_cache_enabled
    get_penalty_cache(config)  # Populate cache
    
    # Disable cache again but keep it populated
    update_module.ENABLE_PENALTY_CACHE = False
    
    result2 = update_section(
        car_state=car_state,
        aero_setup=aero_setup,
        driver_skills=driver_skills,
        section=section,
        env=env,
        config=config,
        push_level=5
    )
    
    print(f"Without cache (cache populated): {result2.dt_s:.6f}s")
    print(f"  Fuel penalty: {result2.fuel_penalty_s:.6f}s")
    print(f"  Engine penalty: {result2.engine_penalty_s:.6f}s")
    
    # Test 3: Run with cache enabled
    update_module.ENABLE_PENALTY_CACHE = True
    
    result3 = update_section(
        car_state=car_state,
        aero_setup=aero_setup,
        driver_skills=driver_skills,
        section=section,
        env=env,
        config=config,
        push_level=5
    )
    
    print(f"With cache: {result3.dt_s:.6f}s")
    print(f"  Fuel penalty: {result3.fuel_penalty_s:.6f}s")
    print(f"  Engine penalty: {result3.engine_penalty_s:.6f}s")
    
    # Compare
    print(f"\nDifferences:")
    print(f"  Result1 vs Result2 (both no cache): {abs(result1.dt_s - result2.dt_s):.9f}s")
    print(f"  Result2 vs Result3 (cache vs no cache): {abs(result2.dt_s - result3.dt_s):.9f}s")
    print(f"  Result1 vs Result3: {abs(result1.dt_s - result3.dt_s):.9f}s")
    
    # Restore original cache setting
    update_module.ENABLE_PENALTY_CACHE = original_cache_enabled

if __name__ == "__main__":
    debug_cache_issue()
