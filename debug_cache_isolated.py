#!/usr/bin/env python3
"""
Isolated cache test to identify the exact source of the issue.
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

def test_isolated_cache_effect():
    """Test cache effect in isolation."""
    print("🔍 Testing isolated cache effect...")
    
    # Load config fresh
    config = load_circuit_config("it-1922_monza")
    
    # Create identical car states
    car_state1 = create_test_car(fuel_kg=80.0)
    car_state2 = create_test_car(fuel_kg=80.0)
    
    driver_skills = DriverSkills()
    aero_setup = AeroSetup()
    env = EnvContext()
    section = config.sections[0]
    
    print(f"Car1 fuel: {car_state1.pu.fuel_kg}kg")
    print(f"Car2 fuel: {car_state2.pu.fuel_kg}kg")
    
    # Test 1: Run with car1, no cache
    clear_penalty_cache(config.circuit_id)
    
    result1 = update_section(
        car_state=car_state1,
        aero_setup=aero_setup,
        driver_skills=driver_skills,
        section=section,
        env=env,
        config=config,
        push_level=5
    )
    
    print(f"Car1 (no cache): {result1.dt_s:.6f}s")
    print(f"  Fuel penalty: {result1.fuel_penalty_s:.6f}s")
    
    # Test 2: Populate cache
    cache = get_penalty_cache(config)
    print(f"Cache populated: {len(cache.sections)} sections")
    
    # Test 3: Run with car2, cache enabled
    result2 = update_section(
        car_state=car_state2,
        aero_setup=aero_setup,
        driver_skills=driver_skills,
        section=section,
        env=env,
        config=config,
        push_level=5
    )
    
    print(f"Car2 (with cache): {result2.dt_s:.6f}s")
    print(f"  Fuel penalty: {result2.fuel_penalty_s:.6f}s")
    
    # Test 4: Run again with car1, cache enabled
    result3 = update_section(
        car_state=car_state1,
        aero_setup=aero_setup,
        driver_skills=driver_skills,
        section=section,
        env=env,
        config=config,
        push_level=5
    )
    
    print(f"Car1 (with cache): {result3.dt_s:.6f}s")
    print(f"  Fuel penalty: {result3.fuel_penalty_s:.6f}s")
    
    # Compare
    print(f"\nDifferences:")
    print(f"  Car1 no cache vs Car1 with cache: {abs(result1.dt_s - result3.dt_s):.9f}s")
    print(f"  Car1 no cache vs Car2 with cache: {abs(result1.dt_s - result2.dt_s):.9f}s")
    print(f"  Car2 with cache vs Car1 with cache: {abs(result2.dt_s - result3.dt_s):.9f}s")
    
    # Check if car states are still identical
    print(f"\nCar state comparison:")
    print(f"  Car1 fuel: {car_state1.pu.fuel_kg}kg")
    print(f"  Car2 fuel: {car_state2.pu.fuel_kg}kg")
    print(f"  Fuel identical: {car_state1.pu.fuel_kg == car_state2.puel.fuel_kg}")

if __name__ == "__main__":
    test_isolated_cache_effect()
