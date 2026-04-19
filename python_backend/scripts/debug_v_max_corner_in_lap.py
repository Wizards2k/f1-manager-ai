#!/usr/bin/env python3
"""Debug: Check v_max_corner values during lap simulation."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_engine.aero.aero_assembly import AeroAssembly
from lap_simulator.physics_engine.integrator.waypoint_integrator import (
    compute_v_max_corners,
    load_hd_waypoints,
    integrate_lap_hd,
)
from scripts.calibrate_v57 import SUSP_SETUPS

def test_v_max_corner_debug():
    """Test v_max_corner values for different wing angles."""

    circuit_id = "us-2012_austin"

    print("\n" + "="*80)
    print("DEBUG: V_MAX_CORNER COMPUTATION")
    print("="*80)
    print(f"Circuit: {circuit_id}")
    print("-"*80)

    # Load waypoints
    waypoints = load_hd_waypoints(circuit_id)

    # Test configurations
    configs = [
        ("LOW", {"front_wing": 16.0, "rear_wing": 20.0, "b_wing": 10.0}),
        ("CAL", {"front_wing": 22.0, "rear_wing": 26.0, "b_wing": 10.0}),
        ("HIGH", {"front_wing": 28.0, "rear_wing": 32.0, "b_wing": 10.0}),
    ]

    mu_cal = 1.847  # From calibration
    mass_kg = 798.0
    susp_setup = SUSP_SETUPS["silverstone"]

    print(f"mu_cal: {mu_cal:.3f}")
    print(f"Suspension: silverstone")
    print("-"*80)

    for name, aero_config in configs:
        aero = AeroAssembly()
        aero.set_component_angles(aero_config)

        # Compute v_max_corner
        v_max_array = compute_v_max_corners(
            waypoints=waypoints,
            aero=aero,
            mu_cal=mu_cal,
            mass_kg=mass_kg,
            n_iter=3,
        )

        # Find max value (excluding 999.0 which is straights)
        v_max_values = [v for v in v_max_array if v < 999.0]
        if v_max_values:
            min_v = min(v_max_values)
            max_v = max(v_max_values)
            avg_v = sum(v_max_values) / len(v_max_values)
            print(f"{name}:")
            print(f"  FW={aero_config['front_wing']:>5.1f}, RW={aero_config['rear_wing']:>5.1f}")
            print(f"  v_max: min={min_v:>6.2f} m/s, avg={avg_v:>6.2f} m/s, max={max_v:>6.2f} m/s")
            print(f"  v_max: min={min_v*3.6:>6.2f} kph, avg={avg_v*3.6:>6.2f} kph, max={max_v*3.6:>6.2f} kph")

    print("-"*80)

    # Now run full simulation and check the lap times
    print("\nFull Lap Simulation Times:")
    print(f"{'Setup':<10} {'Lap Time (s)':<20} {'v_max profile':<20}")
    print("-"*80)

    for name, aero_config in configs:
        result = integrate_lap_hd(
            circuit_id=circuit_id,
            aero_setup=aero_config,
            mass_kg=mass_kg,
            tyre_compound="C4",
            driver_skill=1.0,
            verbose=False,
            suspension_setup=susp_setup,
        )
        lap_time = result["lap_time_s"]
        print(f"{name:<10} {lap_time:<20.3f}")

    print("="*80 + "\n")

if __name__ == "__main__":
    test_v_max_corner_debug()
