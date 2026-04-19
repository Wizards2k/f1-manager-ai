#!/usr/bin/env python3
"""Debug: Trace behavior at a single corner with detailed logging."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_engine.aero.aero_assembly import AeroAssembly
from lap_simulator.physics_engine.integrator.waypoint_integrator import (
    compute_v_max_corners,
    load_hd_waypoints,
)
from lap_simulator.physics_engine.core.constants import G, RHO_SEA_LEVEL

def trace_corner():
    """Trace what happens to a single corner with different setups."""

    circuit_id = "us-2012_austin"
    waypoints = load_hd_waypoints(circuit_id)

    # Find a representative corner (100-300m radius)
    target_wp = None
    for wp in waypoints:
        dist = wp.get('dist_m', 0)
        radius = wp.get('radius_m', 999)
        if 100.0 < radius < 300.0:
            target_wp = wp
            break

    if not target_wp:
        print("Could not find suitable corner")
        return

    print("\n" + "="*100)
    print("TRACE: Corner Physics at Turn 1 (Austin)")
    print("="*100)
    print(f"Waypoint: dist={target_wp['dist_m']:.1f}m, radius={target_wp['radius_m']:.1f}m, v_ref={target_wp['v_ref_kph']:.1f} kph")
    print("-"*100)

    configs = [
        ("LOW", {"front_wing": 16.0, "rear_wing": 20.0, "b_wing": 10.0}),
        ("CAL", {"front_wing": 22.0, "rear_wing": 26.0, "b_wing": 10.0}),
        ("HIGH", {"front_wing": 28.0, "rear_wing": 32.0, "b_wing": 10.0}),
    ]

    mu_cal = 1.847
    mass_kg = 798.0
    radius_m = target_wp['radius_m']
    load_sensitivity_k = 0.010
    cu = min(0.95, 0.35 + radius_m / 150.0)

    print(f"Cornering utilization (cu): {cu:.3f}")
    print(f"Load sensitivity K: {load_sensitivity_k}")
    print("-"*100)

    headers = ["Setup", "FW", "RW", "DF@50m/s", "F_vert", "Load Factor", "F_grip", "v_max_corner", "v_max (kph)"]
    print(f"{'Setup':<10} {'FW':<6} {'RW':<6} {'DF (kN)':<10} {'F_v (kN)':<10} {'Load Fac':<10} {'F_grip (kN)':<12} {'v_max (m/s)':<15} {'v_max (kph)':<15}")
    print("-"*100)

    test_speed = 50.0  # m/s for aero forces
    results = {}

    for name, setup in configs:
        aero = AeroAssembly()
        aero.set_component_angles(setup)
        forces = aero.compute_forces(speed_ms=test_speed)

        f_downforce = forces.f_downforce
        f_vertical = mass_kg * G + f_downforce
        f_vertical_kn = f_vertical / 1000.0

        lat_load_factor = 1.0 - (load_sensitivity_k * f_vertical_kn)
        lat_load_factor = max(0.75, min(1.0, lat_load_factor))

        f_grip = mu_cal * f_vertical * lat_load_factor
        v_max_ms = (f_grip * cu * radius_m / mass_kg) ** 0.5
        v_max_kph = v_max_ms * 3.6

        results[name] = {
            'df': f_downforce / 1000.0,
            'f_vert': f_vertical_kn,
            'load_fac': lat_load_factor,
            'f_grip': f_grip / 1000.0,
            'v_max': v_max_ms,
        }

        print(f"{name:<10} {setup['front_wing']:>6.1f} {setup['rear_wing']:>6.1f} {f_downforce/1000:>10.1f} {f_vertical_kn:>10.1f} {lat_load_factor:>10.3f} {f_grip/1000:>12.1f} {v_max_ms:>15.2f} {v_max_kph:>15.2f}")

    print("-"*100)

    # Calculate changes
    cal_data = results["CAL"]
    low_data = results["LOW"]
    high_data = results["HIGH"]

    print("\nCHANGES FROM CAL:")
    print(f"  LOW:")
    print(f"    DF:        {low_data['df']-cal_data['df']:+.1f} kN ({100*(low_data['df']-cal_data['df'])/cal_data['df']:+.1f}%)")
    print(f"    F_vertical:{low_data['f_vert']-cal_data['f_vert']:+.1f} kN ({100*(low_data['f_vert']-cal_data['f_vert'])/cal_data['f_vert']:+.1f}%)")
    print(f"    Load Fac:  {low_data['load_fac']-cal_data['load_fac']:+.4f} ({100*(low_data['load_fac']-cal_data['load_fac'])/cal_data['load_fac']:+.2f}%)")
    print(f"    F_grip:    {low_data['f_grip']-cal_data['f_grip']:+.1f} kN ({100*(low_data['f_grip']-cal_data['f_grip'])/cal_data['f_grip']:+.1f}%)")
    print(f"    v_max:     {low_data['v_max']-cal_data['v_max']:+.2f} m/s ({100*(low_data['v_max']-cal_data['v_max'])/cal_data['v_max']:+.1f}%)")

    print(f"\n  HIGH:")
    print(f"    DF:        {high_data['df']-cal_data['df']:+.1f} kN ({100*(high_data['df']-cal_data['df'])/cal_data['df']:+.1f}%)")
    print(f"    F_vertical:{high_data['f_vert']-cal_data['f_vert']:+.1f} kN ({100*(high_data['f_vert']-cal_data['f_vert'])/cal_data['f_vert']:+.1f}%)")
    print(f"    Load Fac:  {high_data['load_fac']-cal_data['load_fac']:+.4f} ({100*(high_data['load_fac']-cal_data['load_fac'])/cal_data['load_fac']:+.2f}%)")
    print(f"    F_grip:    {high_data['f_grip']-cal_data['f_grip']:+.1f} kN ({100*(high_data['f_grip']-cal_data['f_grip'])/cal_data['f_grip']:+.1f}%)")
    print(f"    v_max:     {high_data['v_max']-cal_data['v_max']:+.2f} m/s ({100*(high_data['v_max']-cal_data['v_max'])/cal_data['v_max']:+.1f}%)")

    print("="*100 + "\n")

if __name__ == "__main__":
    trace_corner()
