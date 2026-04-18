#!/usr/bin/env python3
"""Debug: Test if AeroAssembly responds correctly to wing angle changes."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.aero.aero_assembly import AeroAssembly

def test_wing_angle_response():
    """Test if changing wing angles increases downforce."""

    test_speed = 50.0  # m/s (180 kph)

    # Create 3 setups: LOW, CAL, HIGH
    configs = [
        ("LOW", {"front_wing": 10.0, "rear_wing": 12.0, "b_wing": 10.0}),
        ("CAL", {"front_wing": 16.0, "rear_wing": 18.0, "b_wing": 10.0}),
        ("HIGH", {"front_wing": 22.0, "rear_wing": 24.0, "b_wing": 10.0}),
    ]

    print("\n" + "="*80)
    print("AERO MODULE: WING ANGLE RESPONSE TEST")
    print("="*80)
    print(f"Test speed: {test_speed:.1f} m/s ({test_speed*3.6:.1f} kph)")
    print("-"*80)
    print(f"{'Setup':<10} {'FW':<8} {'RW':<8} {'Downforce (N)':<20} {'Change vs CAL':<15}")
    print("-"*80)

    # First compute all downforces
    results = {}
    for name, setup in configs:
        aero = AeroAssembly()
        aero.set_component_angles(setup)
        forces = aero.compute_forces(speed_ms=test_speed)
        df = forces.f_downforce
        results[name] = (setup, df)

    # Now display results
    cal_df = results["CAL"][1]
    for name, setup in configs:
        setup_dict, df = results[name]
        fw = setup_dict["front_wing"]
        rw = setup_dict["rear_wing"]
        print(f"{name:<10} {fw:<8.1f} {rw:<8.1f} {df:<20.1f}", end="")

        if name == "CAL":
            print(f"{'BASELINE':<15}")
        else:
            delta = df - cal_df
            pct = 100 * delta / cal_df
            print(f"{delta:+.1f} N ({pct:+.1f}%)")

    print("-"*80)

    # Analyze the pattern
    low_df = results["LOW"][1]
    high_df = results["HIGH"][1]

    print("\nANALYSIS:")
    print(f"  LOW:  {low_df:.1f} N")
    print(f"  CAL:  {cal_df:.1f} N (baseline)")
    print(f"  HIGH: {high_df:.1f} N")

    # Expected: LOW < CAL < HIGH
    # Actual: ?
    if low_df < cal_df and cal_df < high_df:
        print("  ✅ CORRECT: More wing → more downforce")
    elif low_df > cal_df and cal_df > high_df:
        print("  ❌ INVERTED: More wing → LESS downforce (BUG!)")
    else:
        print("  ⚠️ UNEXPECTED PATTERN")

    print("="*80 + "\n")

if __name__ == "__main__":
    test_wing_angle_response()
