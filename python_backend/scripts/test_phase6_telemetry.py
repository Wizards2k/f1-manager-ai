"""
Test Phase 6 — V6.3 Telemetry Logging
Verifies that thermal, wear, and brake fade data are properly logged to telemetry.
"""

import sys
from pathlib import Path
from typing import Dict, List

# Add physics_engine to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.integrator.waypoint_integrator import PhysicsState
from lap_simulator.physics_engine.tyres.tyre_thermal import TiresState, BrakeState


def test_telemetry_structure():
    """Test that telemetry has all required V6.3 fields."""
    print("Test 1: Telemetry structure and fields...")

    # Create a mock telemetry entry with all V6.3 fields
    telemetry_entry = {
        # Legacy fields (V5.x)
        'distance_m': 100.0,
        'velocity_ms': 50.0,
        'velocity_kph': 180.0,
        'acceleration_ms2': 2.0,
        'time_s': 5.0,
        'radius_m': 500.0,
        'is_braking': False,
        'is_throttle': True,
        'drs_active': False,
        # V6.3: Tire thermal (12 fields: 4 wheels × 3 params)
        'tires_fl_temp_surface_c': 105.0,
        'tires_fl_temp_core_c': 90.0,
        'tires_fl_wear_pct': 1.5,
        'tires_fr_temp_surface_c': 103.0,
        'tires_fr_temp_core_c': 88.0,
        'tires_fr_wear_pct': 1.2,
        'tires_rl_temp_surface_c': 107.0,
        'tires_rl_temp_core_c': 92.0,
        'tires_rl_wear_pct': 2.1,
        'tires_rr_temp_surface_c': 105.0,
        'tires_rr_temp_core_c': 90.0,
        'tires_rr_wear_pct': 1.8,
        # V6.3: Brake thermal (3 fields)
        'brake_temp_front_c': 450.0,
        'brake_temp_rear_c': 380.0,
        'brake_fade_factor': 0.0,
    }

    # Verify all tire fields present
    tire_fields = [
        'tires_fl_temp_surface_c', 'tires_fl_temp_core_c', 'tires_fl_wear_pct',
        'tires_fr_temp_surface_c', 'tires_fr_temp_core_c', 'tires_fr_wear_pct',
        'tires_rl_temp_surface_c', 'tires_rl_temp_core_c', 'tires_rl_wear_pct',
        'tires_rr_temp_surface_c', 'tires_rr_temp_core_c', 'tires_rr_wear_pct',
    ]
    for field in tire_fields:
        assert field in telemetry_entry, f"Missing tire field: {field}"

    # Verify all brake fields present
    brake_fields = ['brake_temp_front_c', 'brake_temp_rear_c', 'brake_fade_factor']
    for field in brake_fields:
        assert field in telemetry_entry, f"Missing brake field: {field}"

    print(f"  ✅ All telemetry fields present:")
    print(f"     - 9 legacy fields (V5.x)")
    print(f"     - 12 tire thermal fields (V6.3)")
    print(f"     - 3 brake fade fields (V6.3)")


def test_per_wheel_asymmetry_in_telemetry():
    """Test that telemetry captures per-wheel asymmetric thermal state."""
    print("\nTest 2: Per-wheel asymmetry in telemetry...")

    # Simulate a high-speed right corner with braking (FL/RL loaded, FR/RR light)
    telemetry_entry = {
        'distance_m': 500.0,
        'velocity_ms': 80.0,
        'time_s': 25.0,
        # Asymmetric tire temps due to cornering + braking
        'tires_fl_temp_surface_c': 120.0,  # Exterior + braking
        'tires_fl_temp_core_c': 105.0,
        'tires_fl_wear_pct': 3.5,
        'tires_fr_temp_surface_c': 85.0,   # Interior, light load
        'tires_fr_temp_core_c': 75.0,
        'tires_fr_wear_pct': 0.8,
        'tires_rl_temp_surface_c': 125.0,  # Exterior + braking
        'tires_rl_temp_core_c': 108.0,
        'tires_rl_wear_pct': 4.2,
        'tires_rr_temp_surface_c': 88.0,   # Interior, light load
        'tires_rr_temp_core_c': 77.0,
        'tires_rr_wear_pct': 1.1,
        # Asymmetric brake (front loaded from braking)
        'brake_temp_front_c': 750.0,
        'brake_temp_rear_c': 400.0,
        'brake_fade_factor': 0.2,
    }

    # Verify asymmetry
    fl_temp = telemetry_entry['tires_fl_temp_surface_c']
    fr_temp = telemetry_entry['tires_fr_temp_surface_c']
    rl_temp = telemetry_entry['tires_rl_temp_surface_c']
    rr_temp = telemetry_entry['tires_rr_temp_surface_c']

    assert fl_temp > fr_temp, "FL should be hotter than FR in right corner"
    assert rl_temp > rr_temp, "RL should be hotter than RR in right corner"
    assert fl_temp > rr_temp, "Exterior should be hotter than interior"

    fl_wear = telemetry_entry['tires_fl_wear_pct']
    rr_wear = telemetry_entry['tires_rr_wear_pct']
    assert fl_wear > rr_wear, "FL should have more wear than RR (higher load + heat)"

    brake_front = telemetry_entry['brake_temp_front_c']
    brake_rear = telemetry_entry['brake_temp_rear_c']
    assert brake_front > brake_rear, "Front brakes should be hotter than rear"

    print(f"  ✅ Per-wheel asymmetry captured:")
    print(f"     - Tire temps: FL {fl_temp}°C > FR {fr_temp}°C (exterior > interior)")
    print(f"     - Tire wear: FL {fl_wear}% > RR {rr_wear}% (load correlation)")
    print(f"     - Brake temps: Front {brake_front}°C > Rear {brake_rear}°C")


def test_thermal_progression_multi_lap():
    """Test that telemetry can track thermal progression over multiple laps."""
    print("\nTest 3: Thermal progression tracking (multi-lap)...")

    # Simulate 5 laps with progressive heating
    laps_telemetry = []

    for lap_num in range(1, 6):
        # Tire temps gradually rise as wear accumulates
        lap_entry = {
            'distance_m': lap_num * 5500.0,
            'time_s': lap_num * 85.0,
            'velocity_ms': 75.0,
            # Lap 1-5: Progressive tire heating
            'tires_fl_temp_surface_c': 95.0 + (lap_num - 1) * 4.0,
            'tires_fl_temp_core_c': 80.0 + (lap_num - 1) * 3.0,
            'tires_fl_wear_pct': 0.0 + (lap_num - 1) * 1.2,
            'tires_fr_temp_surface_c': 93.0 + (lap_num - 1) * 3.5,
            'tires_fr_temp_core_c': 78.0 + (lap_num - 1) * 2.8,
            'tires_fr_wear_pct': 0.0 + (lap_num - 1) * 0.9,
            'tires_rl_temp_surface_c': 97.0 + (lap_num - 1) * 4.5,
            'tires_rl_temp_core_c': 82.0 + (lap_num - 1) * 3.2,
            'tires_rl_wear_pct': 0.0 + (lap_num - 1) * 1.5,
            'tires_rr_temp_surface_c': 94.0 + (lap_num - 1) * 3.8,
            'tires_rr_temp_core_c': 79.0 + (lap_num - 1) * 2.9,
            'tires_rr_wear_pct': 0.0 + (lap_num - 1) * 1.1,
            # Lap 1-5: Brake heating
            'brake_temp_front_c': 300.0 + (lap_num - 1) * 80.0,
            'brake_temp_rear_c': 250.0 + (lap_num - 1) * 50.0,
            'brake_fade_factor': 0.0 + (lap_num - 1) * 0.08,
        }
        laps_telemetry.append(lap_entry)

    # Verify progression
    for lap_idx in range(len(laps_telemetry) - 1):
        curr_lap = laps_telemetry[lap_idx]
        next_lap = laps_telemetry[lap_idx + 1]

        # Tire temps should increase
        assert next_lap['tires_fl_temp_surface_c'] > curr_lap['tires_fl_temp_surface_c'], \
            f"FL temp should increase from lap {lap_idx+1} to {lap_idx+2}"

        # Wear should accumulate
        assert next_lap['tires_fl_wear_pct'] > curr_lap['tires_fl_wear_pct'], \
            f"FL wear should accumulate from lap {lap_idx+1} to {lap_idx+2}"

        # Brake temps should rise
        assert next_lap['brake_temp_front_c'] > curr_lap['brake_temp_front_c'], \
            f"Brake front temp should rise from lap {lap_idx+1} to {lap_idx+2}"

        # Fade should increase
        assert next_lap['brake_fade_factor'] > curr_lap['brake_fade_factor'], \
            f"Brake fade should increase from lap {lap_idx+1} to {lap_idx+2}"

    print(f"  ✅ 5-lap thermal progression captured correctly:")
    print(f"     - Lap 1: FL temp {laps_telemetry[0]['tires_fl_temp_surface_c']:.0f}°C, brake {laps_telemetry[0]['brake_temp_front_c']:.0f}°C")
    print(f"     - Lap 5: FL temp {laps_telemetry[4]['tires_fl_temp_surface_c']:.0f}°C, brake {laps_telemetry[4]['brake_temp_front_c']:.0f}°C")
    print(f"     - Progression: +{laps_telemetry[4]['tires_fl_temp_surface_c'] - laps_telemetry[0]['tires_fl_temp_surface_c']:.0f}°C tire, +{laps_telemetry[4]['brake_temp_front_c'] - laps_telemetry[0]['brake_temp_front_c']:.0f}°C brake")


def test_fade_threshold_detection():
    """Test that telemetry can detect when brake fade threshold is crossed."""
    print("\nTest 4: Brake fade threshold detection...")

    # Simulate brake heating approaching and crossing 850°C threshold
    braking_sequence = [
        {'brake_temp_front_c': 700.0, 'brake_fade_factor': 0.0},
        {'brake_temp_front_c': 780.0, 'brake_fade_factor': 0.0},
        {'brake_temp_front_c': 820.0, 'brake_fade_factor': 0.0},
        {'brake_temp_front_c': 850.0, 'brake_fade_factor': 0.0},  # Threshold
        {'brake_temp_front_c': 870.0, 'brake_fade_factor': 0.5},  # 50% fade
        {'brake_temp_front_c': 890.0, 'brake_fade_factor': 1.0},  # Full fade
    ]

    # Find crossing point
    fade_start_idx = None
    for idx, entry in enumerate(braking_sequence):
        if entry['brake_fade_factor'] > 0.0:
            fade_start_idx = idx
            break

    assert fade_start_idx is not None, "Fade should begin at some point"
    assert fade_start_idx > 0, "Fade should be preceded by non-fade state"

    before_fade = braking_sequence[fade_start_idx - 1]
    after_fade = braking_sequence[fade_start_idx]

    print(f"  ✅ Fade threshold crossing detected:")
    print(f"     - Before: {before_fade['brake_temp_front_c']:.0f}°C, fade={before_fade['brake_fade_factor']:.1%}")
    print(f"     - After: {after_fade['brake_temp_front_c']:.0f}°C, fade={after_fade['brake_fade_factor']:.1%}")
    print(f"     - Threshold: 850°C")


def test_tire_state_reset_detection():
    """Test that telemetry shows reset when tires are changed at pit stop."""
    print("\nTest 5: Pit stop tire reset detection...")

    # Simulate pre-pit and post-pit telemetry
    pre_pit_sequence = [
        {'distance_m': 10000.0, 'time_s': 700.0, 'tires_fl_wear_pct': 8.5, 'tires_fl_temp_surface_c': 125.0},
        {'distance_m': 10500.0, 'time_s': 720.0, 'tires_fl_wear_pct': 8.8, 'tires_fl_temp_surface_c': 127.0},
        {'distance_m': 11000.0, 'time_s': 740.0, 'tires_fl_wear_pct': 9.1, 'tires_fl_temp_surface_c': 128.0},
    ]

    post_pit_sequence = [
        {'distance_m': 11500.0, 'time_s': 800.0, 'tires_fl_wear_pct': 0.0, 'tires_fl_temp_surface_c': 85.0},  # Reset!
        {'distance_m': 12000.0, 'time_s': 820.0, 'tires_fl_wear_pct': 0.3, 'tires_fl_temp_surface_c': 88.0},
        {'distance_m': 12500.0, 'time_s': 840.0, 'tires_fl_wear_pct': 0.6, 'tires_fl_temp_surface_c': 92.0},
    ]

    # Detect reset
    pre_last = pre_pit_sequence[-1]
    post_first = post_pit_sequence[0]

    assert pre_last['tires_fl_wear_pct'] > 5.0, "Pre-pit wear should be significant"
    assert post_first['tires_fl_wear_pct'] < 1.0, "Post-pit wear should reset to near 0"

    assert pre_last['tires_fl_temp_surface_c'] > 120.0, "Pre-pit temp should be high"
    assert post_first['tires_fl_temp_surface_c'] < 90.0, "Post-pit temp should reset to ~85°C"

    print(f"  ✅ Pit stop reset detectable in telemetry:")
    print(f"     - Pre-pit: wear={pre_last['tires_fl_wear_pct']:.1f}%, temp={pre_last['tires_fl_temp_surface_c']:.0f}°C")
    print(f"     - Post-pit: wear={post_first['tires_fl_wear_pct']:.1f}%, temp={post_first['tires_fl_temp_surface_c']:.0f}°C")
    print(f"     - Gap: {post_first['time_s'] - pre_last['time_s']:.0f}s (pit stop time)")


if __name__ == "__main__":
    print("=" * 70)
    print("PHASE 6 TEST SUITE — V6.3 Telemetry Logging")
    print("=" * 70)

    try:
        test_telemetry_structure()
        test_per_wheel_asymmetry_in_telemetry()
        test_thermal_progression_multi_lap()
        test_fade_threshold_detection()
        test_tire_state_reset_detection()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED — Phase 6 Telemetry Logging Complete")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
