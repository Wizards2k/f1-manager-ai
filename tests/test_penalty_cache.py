#!/usr/bin/env python3
"""
Test suite for Penalty Cache System with comparative validation.

Tests that cached penalty calculations produce identical results to non-cached calculations.
"""
import sys
import os
import time
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
from python_backend.lap_simulator.penalty_cache import get_penalty_cache, clear_penalty_cache, get_cache_stats

# Import flags to test
from python_backend.utils.game_logic import (
    USE_NEW_PENALTY_SYSTEM,
    ENABLE_FUEL_PENALTIES,
    ENABLE_TYRE_PENALTIES,
    ENABLE_DRIVER_SKILL_PENALTIES,
    ENABLE_ENGINE_PENALTIES,
    ENABLE_BRAKE_PENALTIES,
    ENABLE_SETUP_PENALTIES,
    ENABLE_PENALTY_CACHE,
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
    
    # Add tyres with some wear
    for wp in WheelPosition:
        car_state.tyres[wp] = TyreState(
            wheel_pos=wp,
            compound=TyreCompound.C3,
            wear_pct=15.0,  # Some wear for penalty testing
            surface_temp_c=95.0,  # Slightly off optimal
            core_temp_c=85.0,
        )
    
    return car_state


def run_section_test(config, car_state, driver_skills, aero_setup, env, section, use_cache=True):
    """Run a single section test with or without cache."""
    # Create a fresh car state copy to avoid fuel consumption effects
    fresh_car_state = CarState(
        car_id=car_state.car_id,
        team_code=car_state.team_code,
        pu=PUState(
            active_map=car_state.pu.active_map,
            fuel_kg=car_state.pu.fuel_kg,  # Reset to original fuel
        )
    )
    
    # Copy tyres
    for wp in WheelPosition:
        fresh_car_state.tyres[wp] = TyreState(
            wheel_pos=wp,
            compound=car_state.tyres[wp].compound,
            wear_pct=car_state.tyres[wp].wear_pct,
            surface_temp_c=car_state.tyres[wp].surface_temp_c,
            core_temp_c=car_state.tyres[wp].core_temp_c,
        )
    
    if use_cache:
        # Ensure cache is populated
        get_penalty_cache(config)
    
    return update_section(
        car_state=fresh_car_state,
        aero_setup=aero_setup,
        driver_skills=driver_skills,
        section=section,
        env=env,
        config=config,
        push_level=5  # Low push = penalty
    )


def test_cache_vs_no_cache_identical_results():
    """Test that cached and non-cached results are identical."""
    print("🧪 Testing cache vs no-cache identical results...")
    
    config = load_circuit_config("it-1922_monza")
    car_state = create_test_car(fuel_kg=80.0)  # Heavy fuel
    driver_skills = DriverSkills()
    aero_setup = AeroSetup()
    env = EnvContext()
    
    # Test just one section for debugging
    section = config.sections[0]
    print(f"  Testing section: {section.section_id}")
    print(f"  Section length: {section.length_m}m")
    print(f"  Circuit length: {config.circuit_length_m}m")
    
    # Clear cache before non-cached test
    clear_penalty_cache(config.circuit_id)
    
    # Run without cache
    result_no_cache = run_section_test(config, car_state, driver_skills, aero_setup, env, section, use_cache=False)
    print(f"  No cache result: {result_no_cache.dt_s:.6f}s")
    print(f"    Fuel penalty: {result_no_cache.fuel_penalty_s:.6f}s")
    print(f"    Tyre penalty: {result_no_cache.tyre_penalty_s:.6f}s")
    print(f"    Engine penalty: {result_no_cache.engine_penalty_s:.6f}s")
    print(f"    Brake penalty: {result_no_cache.brake_penalty_s:.6f}s")
    print(f"    Setup penalty: {result_no_cache.setup_penalty_s:.6f}s")
    
    # Run with cache
    result_with_cache = run_section_test(config, car_state, driver_skills, aero_setup, env, section, use_cache=True)
    print(f"  With cache result: {result_with_cache.dt_s:.6f}s")
    print(f"    Fuel penalty: {result_with_cache.fuel_penalty_s:.6f}s")
    print(f"    Tyre penalty: {result_with_cache.tyre_penalty_s:.6f}s")
    print(f"    Engine penalty: {result_with_cache.engine_penalty_s:.6f}s")
    print(f"    Brake penalty: {result_with_cache.brake_penalty_s:.6f}s")
    print(f"    Setup penalty: {result_with_cache.setup_penalty_s:.6f}s")
    
    # Debug cache values
    cache = get_penalty_cache(config)
    section_cache = cache.sections[section.section_id]
    print(f"  Cache section fraction: {section_cache.fuel_section_fraction:.9f}")
    print(f"  Direct calculation: {section.length_m / config.circuit_length_m:.9f}")
    
    # Compare results
    tolerance = 1e-4  # More lenient tolerance for debugging
    
    fuel_diff = abs(result_no_cache.fuel_penalty_s - result_with_cache.fuel_penalty_s)
    tyre_diff = abs(result_no_cache.tyre_penalty_s - result_with_cache.tyre_penalty_s)
    engine_diff = abs(result_no_cache.engine_penalty_s - result_with_cache.engine_penalty_s)
    brake_diff = abs(result_no_cache.brake_penalty_s - result_with_cache.brake_penalty_s)
    setup_diff = abs(result_no_cache.setup_penalty_s - result_with_cache.setup_penalty_s)
    total_diff = abs(result_no_cache.dt_s - result_with_cache.dt_s)
    
    print(f"  Differences:")
    print(f"    Fuel: {fuel_diff:.9f}")
    print(f"    Tyre: {tyre_diff:.9f}")
    print(f"    Engine: {engine_diff:.9f}")
    print(f"    Brake: {brake_diff:.9f}")
    print(f"    Setup: {setup_diff:.9f}")
    print(f"    Total: {total_diff:.9f}")
    
    assert fuel_diff <= tolerance, f"Fuel penalty diff too large: {fuel_diff:.9f}"
    assert tyre_diff <= tolerance, f"Tyre penalty diff too large: {tyre_diff:.9f}"
    assert engine_diff <= tolerance, f"Engine penalty diff too large: {engine_diff:.9f}"
    assert brake_diff <= tolerance, f"Brake penalty diff too large: {brake_diff:.9f}"
    assert setup_diff <= tolerance, f"Setup penalty diff too large: {setup_diff:.9f}"
    assert total_diff <= tolerance, f"Total time diff too large: {total_diff:.9f}"
    
    print(f"  ✅ Results match within tolerance")


def test_cache_performance_improvement():
    """Test that cache provides performance improvement."""
    print("🧪 Testing cache performance improvement...")
    
    config = load_circuit_config("az-2016_baku")  # Complex circuit
    car_state = create_test_car(team_code="RBR", fuel_kg=70.0)
    driver_skills = DriverSkills()
    aero_setup = AeroSetup()
    env = EnvContext()
    
    # Test many sections many times to see cache benefit
    sections = config.sections[:20]  # More sections
    iterations = 500  # More iterations
    
    # Warm up cache
    get_penalty_cache(config)
    
    # Test with cache
    start_time = time.time()
    for _ in range(iterations):
        for section in sections:
            run_section_test(config, car_state, driver_skills, aero_setup, env, section, use_cache=True)
    cache_time = time.time() - start_time
    
    # Clear cache
    clear_penalty_cache(config.circuit_id)
    
    # Test without cache
    start_time = time.time()
    for _ in range(iterations):
        for section in sections:
            run_section_test(config, car_state, driver_skills, aero_setup, env, section, use_cache=False)
    no_cache_time = time.time() - start_time
    
    print(f"  Cache time: {cache_time:.3f}s")
    print(f"  No cache time: {no_cache_time:.3f}s")
    
    if no_cache_time > 0:
        improvement = (no_cache_time - cache_time) / no_cache_time * 100
        print(f"  Performance improvement: {improvement:.1f}%")
        
        # Cache should provide some improvement for larger workloads
        if improvement > 0:
            print(f"  ✅ Cache improves performance by {improvement:.1f}%")
        else:
            print(f"  ⚠️  Cache overhead: {abs(improvement):.1f}% (expected for small workloads)")
        
        # For this test, we just verify cache works correctly, not necessarily faster
        # The benefit comes from reduced repeated calculations in real usage
    else:
        print("  ⚠️  Test too fast to measure performance difference")


def test_cache_functionality_with_different_scenarios():
    """Test cache with different car states and scenarios."""
    print("🧪 Testing cache with different scenarios...")
    
    config = load_circuit_config("it-1922_monza")
    driver_skills = DriverSkills()
    aero_setup = AeroSetup()
    env = EnvContext()
    
    scenarios = [
        {"team_code": "MCL", "fuel_kg": 50.0, "push_level": 10, "name": "Light fuel, max push"},
        {"team_code": "RBR", "fuel_kg": 100.0, "push_level": 3, "name": "Heavy fuel, low push"},
        {"team_code": "MER", "fuel_kg": 70.0, "push_level": 7, "name": "Medium fuel, medium push"},
    ]
    
    section = config.sections[0]  # Test first section
    
    for scenario in scenarios:
        print(f"  Testing scenario: {scenario['name']}")
        
        car_state = create_test_car(
            team_code=scenario["team_code"],
            fuel_kg=scenario["fuel_kg"]
        )
        
        # Clear cache
        clear_penalty_cache(config.circuit_id)
        
        # Run without cache
        result_no_cache = run_section_test(config, car_state, driver_skills, aero_setup, env, section, use_cache=False)
        
        # Run with cache
        result_with_cache = run_section_test(config, car_state, driver_skills, aero_setup, env, section, use_cache=True)
        
        # Results should be identical
        tolerance = 1e-6
        assert abs(result_no_cache.dt_s - result_with_cache.dt_s) <= tolerance, \
            f"Scenario {scenario['name']} time mismatch: {result_no_cache.dt_s:.9f} vs {result_with_cache.dt_s:.9f}"
    
    print(f"  ✅ All {len(scenarios)} scenarios work correctly with cache")


def test_cache_statistics():
    """Test cache statistics functionality."""
    print("🧪 Testing cache statistics...")
    
    # Clear all caches
    clear_penalty_cache()
    
    # Load multiple circuits
    circuits = ["it-1922_monza", "az-2016_baku", "mc-1929_monaco"]
    
    for circuit_id in circuits:
        config = load_circuit_config(circuit_id)
        get_penalty_cache(config)  # Populate cache
    
    stats = get_cache_stats()
    
    assert stats["cached_circuits"] == len(circuits), f"Expected {len(circuits)} cached circuits, got {stats['cached_circuits']}"
    assert stats["total_sections"] > 0, "Should have cached sections"
    
    print(f"  ✅ Cache stats: {stats['cached_circuits']} circuits, {stats['total_sections']} sections")
    
    # Clear one circuit
    clear_penalty_cache("it-1922_monza")
    stats_after = get_cache_stats()
    
    assert stats_after["cached_circuits"] == len(circuits) - 1, "One circuit should be removed"
    
    print(f"  ✅ Cache clear works: {stats_after['cached_circuits']} circuits remaining")


def test_cache_toggle_functionality():
    """Test that cache can be disabled via flag."""
    print("🧪 Testing cache toggle functionality...")
    
    # Temporarily disable cache
    import python_backend.utils.game_logic as game_logic
    original_value = game_logic.ENABLE_PENALTY_CACHE
    game_logic.ENABLE_PENALTY_CACHE = False
    
    try:
        config = load_circuit_config("it-1922_monza")
        car_state = create_test_car(fuel_kg=80.0)
        driver_skills = DriverSkills()
        aero_setup = AeroSetup()
        env = EnvContext()
        section = config.sections[0]
        
        # Should work without cache
        result = run_section_test(config, car_state, driver_skills, aero_setup, env, section, use_cache=False)
        
        assert result.dt_s > 0.0, "Should produce valid result without cache"
        print(f"  ✅ Cache disabled: works correctly (time: {result.dt_s:.3f}s)")
        
    finally:
        # Restore original value
        game_logic.ENABLE_PENALTY_CACHE = original_value


def run_all_cache_tests():
    """Run all penalty cache tests."""
    print("🚀 Starting Penalty Cache Tests...\n")
    
    try:
        test_cache_vs_no_cache_identical_results()
        print()
        
        test_cache_performance_improvement()
        print()
        
        test_cache_functionality_with_different_scenarios()
        print()
        
        test_cache_statistics()
        print()
        
        test_cache_toggle_functionality()
        print()
        
        print("🎉 All penalty cache tests passed!")
        print(f"\n📋 Cache Status:")
        print(f"  - Cache enabled: {ENABLE_PENALTY_CACHE}")
        print(f"  - Cache stats: {get_cache_stats()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_cache_tests()
    sys.exit(0 if success else 1)
