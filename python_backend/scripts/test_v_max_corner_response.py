#!/usr/bin/env python3
"""Debug: Test if compute_v_max_corners responds correctly to DF changes."""

import sys
from pathlib import Path
import math

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.aero.aero_assembly import AeroAssembly
from lap_simulator.physics_v4.integrator.waypoint_integrator import compute_v_max_corners, load_hd_waypoints

def test_v_max_corner_response():
    """Test if v_max_corner increases with more downforce (wing angle)."""

    # Load Monaco circuit waypoints
    waypoints = load_hd_waypoints("mc-1929_monaco")

    # Pick the Sainte-Dévote (tight, slow) corner for testing
    # radius ~100m, v_ref ~85 kph
    target_wp = None
    for wp in waypoints:
        if 90.0 < wp.get('radius_m', 999) < 110.0:
            target_wp = wp
            break

    if not target_wp:
        print("Could not find suitable corner in Monaco")
        return

    print("\n" + "="*80)
    print("COMPUTE_V_MAX_CORNER: DOWNFORCE RESPONSE TEST")
    print("="*80)
    print(f"Test circuit: Monaco")
    print(f"Test corner: radius={target_wp['radius_m']:.1f}m, v_ref={target_wp['v_ref_kph']:.1f} kph")
    print("-"*80)
    print(f"{'Setup':<10} {'FW':<8} {'RW':<8} {'v_max (m/s)':<15} {'v_max (kph)':<15} {'Change vs CAL':<15}")
    print("-"*80)

    # Create 3 setups
    configs = [
        ("LOW", {"front_wing": 10.0, "rear_wing": 12.0, "b_wing": 10.0}),
        ("CAL", {"front_wing": 16.0, "rear_wing": 18.0, "b_wing": 10.0}),
        ("HIGH", {"front_wing": 22.0, "rear_wing": 24.0, "b_wing": 10.0}),
    ]

    mu_cal = 1.55  # Standard mu
    mass_kg = 798.0
    results = {}

    # Compute v_max for each setup
    for name, setup in configs:
        aero = AeroAssembly()
        aero.set_component_angles(setup)

        # Create a minimal waypoint array with just our test corner
        test_waypoints = [target_wp]

        v_max_array = compute_v_max_corners(
            waypoints=test_waypoints,
            aero=aero,
            mu_cal=mu_cal,
            mass_kg=mass_kg,
            n_iter=3,
        )

        v_max_ms = v_max_array[0]
        v_max_kph = v_max_ms * 3.6
        results[name] = (setup, v_max_ms, v_max_kph)

    # Display results with comparisons
    for name, setup in configs:
        setup_dict, v_max_ms, v_max_kph = results[name]
        fw = setup_dict["front_wing"]
        rw = setup_dict["rear_wing"]
        print(f"{name:<10} {fw:<8.1f} {rw:<8.1f} {v_max_ms:<15.2f} {v_max_kph:<15.2f}", end="")

        if name == "CAL":
            print(f"{'BASELINE':<15}")
        else:
            cal_ms = results["CAL"][1]
            delta_ms = v_max_ms - cal_ms
            delta_kph = v_max_kph - results["CAL"][2]
            pct = 100 * delta_ms / cal_ms
            print(f"{delta_ms:+.2f} m/s ({delta_kph:+.2f} kph, {pct:+.1f}%)")

    print("-"*80)

    # Analyze the pattern
    low_vmax = results["LOW"][1]
    cal_vmax = results["CAL"][1]
    high_vmax = results["HIGH"][1]

    print("\nANALYSIS:")
    print(f"  LOW:  {low_vmax:.2f} m/s ({low_vmax*3.6:.2f} kph)")
    print(f"  CAL:  {cal_vmax:.2f} m/s ({cal_vmax*3.6:.2f} kph) (baseline)")
    print(f"  HIGH: {high_vmax:.2f} m/s ({high_vmax*3.6:.2f} kph)")

    # Expected: LOW < CAL < HIGH
    if low_vmax < cal_vmax and cal_vmax < high_vmax:
        print("  ✅ CORRECT: More wing → higher v_max_corner")
    elif low_vmax > cal_vmax and cal_vmax > high_vmax:
        print("  ❌ INVERTED: More wing → LOWER v_max_corner (BUG FOUND!)")
    else:
        print("  ⚠️ UNEXPECTED PATTERN")

    print("="*80 + "\n")

if __name__ == "__main__":
    test_v_max_corner_response()
