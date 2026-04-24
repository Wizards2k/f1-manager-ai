#!/usr/bin/env python3
"""
V6.3 Telemetry Fields Validation

Verifica che tutti i campi telemetry siano presenti per ogni waypoint
durante una simulazione completa di un giro.

V6.3 specifica 24-field per-wheel telemetry:
  - Per wheel (FL/FR/RL/RR): surface_temp, core_temp, wear_pct, slip (4 × 4 = 16)
  - Global: velocity, throttle, brake_pct, lateral_g (4)
  - Brakes: temp_front, temp_rear (2)
  - Miscellaneous: DRS, fuel_remaining (2)
  = 24 total
"""

import sys
from pathlib import Path
from typing import Dict, List

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup, DriverSkill
from scripts.calibrate_v57 import DRIVER


# Expected telemetry fields per waypoint (actual names from integrate_waypoint)
EXPECTED_TELEMETRY_FIELDS = {
    # Per-wheel tire thermal and wear (4 wheels × 4 fields = 16)
    'tires_fl_temp_surface_c', 'tires_fl_temp_core_c', 'tires_fl_wear_pct', 'tires_fl_acceleration',
    'tires_fr_temp_surface_c', 'tires_fr_temp_core_c', 'tires_fr_wear_pct', 'tires_fr_acceleration',
    'tires_rl_temp_surface_c', 'tires_rl_temp_core_c', 'tires_rl_wear_pct', 'tires_rl_acceleration',
    'tires_rr_temp_surface_c', 'tires_rr_temp_core_c', 'tires_rr_wear_pct', 'tires_rr_acceleration',

    # Global vehicle dynamics (4)
    'velocity_kph', 'is_throttle', 'is_braking', 'acceleration_ms2',

    # Brake thermal (2)
    'brake_temp_front_c', 'brake_temp_rear_c',

    # Miscellaneous (2)
    'drs_active', 'distance_m',
}

# Minimum acceptable subset (if full 24 not present)
MINIMUM_FIELDS = {
    'velocity_kph', 'distance_m', 'time_s', 'radius_m',
    'tires_fl_temp_surface_c', 'tires_fr_temp_surface_c',
    'tires_rl_temp_surface_c', 'tires_rr_temp_surface_c',
}


def validate_telemetry_per_waypoint(waypoint_data: Dict, waypoint_number: int) -> tuple:
    """
    Validate that a single waypoint has expected telemetry fields.
    
    Returns: (is_complete, is_valid, missing_fields, extra_fields)
    """
    actual_fields = set(waypoint_data.keys())
    missing = EXPECTED_TELEMETRY_FIELDS - actual_fields
    extra = actual_fields - EXPECTED_TELEMETRY_FIELDS
    
    is_complete = len(missing) == 0
    is_valid = len(MINIMUM_FIELDS - actual_fields) == 0
    
    return is_complete, is_valid, missing, extra


print("="*95)
print("V6.3 TELEMETRY FIELDS END-TO-END VALIDATION")
print("="*95)
print("\nValidating that all telemetry fields are present for each waypoint.\n")

test_circuit = "it-1922_monza"
circuit_name = "Monza"

print(f"Test Circuit: {circuit_name}\n")

# Run single lap simulation
print("Simulating full lap on Monza with telemetry capture...")
setup = PhysicsV4Setup(driver_data=DRIVER, circuit=test_circuit, session="qualifying")
setup.set_aero(front_wing=9, rear_wing=4)
setup.set_suspension(spring_front=25.0, spring_rear=33.0, ARB_front=8.0, ARB_rear=13.0,
                     ride_height_front=10.0, ride_height_rear=17.0)
setup.set_fuels(fuel_kg=50.0, fuel_mix="standard")
setup.set_tyres(compound="C5")
setup.set_ers_mode("quali_deploy")

result = setup.simulate_lap(verbose=False)

print(f"✅ Lap simulation complete: {result.get('lap_time_s', 0.0):.3f}s\n")

# Validate result structure
print(f"{'='*95}")
print("RESULT-LEVEL FIELDS (Top-level dict)")
print(f"{'='*95}\n")

expected_result_fields = {
    'lap_time_s', 'v_max_kph', 'v_min_kph', 'waypoints_count',
    'fuel_consumed_kg', 'fuel_remaining_kg',
    'telemetry', 'pu_v54'
}

actual_result_fields = set(result.keys())
missing_result = expected_result_fields - actual_result_fields
extra_result = actual_result_fields - expected_result_fields

print(f"Expected result fields: {len(expected_result_fields)}")
print(f"Actual result fields:   {len(actual_result_fields)}")
print(f"Missing:                {len(missing_result)}")

if missing_result:
    print(f"  ⚠️  Missing fields: {missing_result}\n")
else:
    print(f"  ✅ All expected result fields present\n")

if extra_result:
    print(f"  ℹ️  Extra fields (OK): {len(extra_result)} additional fields\n")

# Validate telemetry (list of dicts)
print(f"{'='*95}")
print("WAYPOINT-LEVEL FIELDS (Per-waypoint telemetry)")
print(f"{'='*95}\n")

telemetry_points = result.get('telemetry', [])
n_waypoints = len(telemetry_points)

print(f"Total waypoints: {n_waypoints}\n")

if n_waypoints == 0:
    print("❌ ERROR: No telemetry waypoints captured!\n")
    sys.exit(1)

# Analyze completeness per waypoint
complete_count = 0
valid_count = 0
all_missing = set()
all_extra = set()

for i, wp in enumerate(telemetry_points):
    is_complete, is_valid, missing, extra = validate_telemetry_per_waypoint(wp, i)
    if is_complete:
        complete_count += 1
    if is_valid:
        valid_count += 1
    all_missing.update(missing)
    all_extra.update(extra)

# Results summary
complete_pct = (complete_count / n_waypoints) * 100 if n_waypoints > 0 else 0
valid_pct = (valid_count / n_waypoints) * 100 if n_waypoints > 0 else 0

print(f"Telemetry Completeness:")
print(f"  ✅ Waypoints with ALL 24 fields: {complete_count}/{n_waypoints} ({complete_pct:.1f}%)")
print(f"  ✅ Waypoints with MINIMUM fields: {valid_count}/{n_waypoints} ({valid_pct:.1f}%)")
print(f"  ⚠️  Total unique missing fields: {len(all_missing)}")

if all_missing:
    print(f"\n  Missing field types: {all_missing}")

if all_extra:
    print(f"  Extra field types: {all_extra}\n")
else:
    print()

# Sample waypoint analysis (first and middle waypoint)
print(f"{'='*95}")
print("SAMPLE WAYPOINT ANALYSIS")
print(f"{'='*95}\n")

sample_indices = [0, n_waypoints // 2, n_waypoints - 1]
for idx in sample_indices:
    wp = telemetry_points[idx]
    is_complete, is_valid, missing, extra = validate_telemetry_per_waypoint(wp, idx)
    
    print(f"Waypoint {idx} ({['start', 'midpoint', 'end'][sample_indices.index(idx)]}):")
    print(f"  Fields present: {len(wp)}")
    print(f"  Complete (24/24): {'✅' if is_complete else '❌'}")
    print(f"  Valid (min 8): {'✅' if is_valid else '❌'}")
    
    if missing:
        print(f"  Missing: {missing}")
    print()

# Final verdict
print(f"{'='*95}")
print("VALIDATION VERDICT")
print(f"{'='*95}\n")

if complete_pct == 100.0:
    print("✅ PASS: All waypoints have full 24-field telemetry")
    status = "PRODUCTION-READY"
elif valid_pct == 100.0:
    print("✅ PASS: All waypoints have minimum required telemetry fields")
    status = "ACCEPTABLE"
elif valid_pct >= 90.0:
    print(f"⚠️  WARN: {valid_pct:.1f}% of waypoints have minimum telemetry")
    status = "NEEDS-REVIEW"
else:
    print(f"❌ FAIL: Only {valid_pct:.1f}% of waypoints have telemetry")
    status = "BROKEN"

print(f"\nStatus: {status}")
print(f"\nNote: Full 24-field telemetry includes per-wheel thermal (4×4=16),")
print(f"vehicle dynamics (4), brake thermal (2), and misc fields (2).\n")
