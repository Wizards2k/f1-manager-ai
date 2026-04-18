#!/usr/bin/env python3
"""Analyze lap energy budget: time gained in corners vs time lost to drag."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.aero.aero_assembly import AeroAssembly
from lap_simulator.physics_v4.integrator.waypoint_integrator import load_hd_waypoints
from lap_simulator.physics_v4.core.constants import G

def analyze_energy():
    """Estimate drag penalty vs corner speed benefit."""

    circuit_id = "us-2012_austin"
    waypoints = load_hd_waypoints(circuit_id)

    # Calculate total drag at 100 m/s (straight speed)
    test_speed = 100.0

    configs = [
        ("LOW", {"front_wing": 16.0, "rear_wing": 20.0, "b_wing": 10.0}),
        ("CAL", {"front_wing": 22.0, "rear_wing": 26.0, "b_wing": 10.0}),
        ("HIGH", {"front_wing": 28.0, "rear_wing": 32.0, "b_wing": 10.0}),
    ]

    print("\n" + "="*100)
    print("ENERGY ANALYSIS: Drag Penalty vs Corner Benefit")
    print("="*100)

    # Get aero data
    aero_data = {}
    for name, setup in configs:
        aero = AeroAssembly()
        aero.set_component_angles(setup)
        forces = aero.compute_forces(speed_ms=test_speed)
        aero_data[name] = (forces.f_downforce, forces.f_drag)

    # Calculate average corner speed for each setup
    corners = []
    for wp in waypoints:
        radius = wp.get('radius_m', 999)
        if 50.0 < radius < 400.0:  # Only moderate/tight corners
            corners.append(wp)

    print(f"\nCircuit: {circuit_id}")
    print(f"Average corners (50m < r < 400m): {len(corners)} waypoints")
    print(f"Total waypoints: {len(waypoints)}")

    # Estimate straight vs corner percentages
    corner_dist = sum(wp.get('dist_step', 5.0) for wp in corners if 50.0 < wp.get('radius_m', 999) < 400.0)
    total_dist = waypoints[-1]['dist_m'] if waypoints else 5000.0
    corner_pct = 100 * corner_dist / total_dist
    straight_pct = 100 - corner_pct

    print(f"Estimated corner distance: {corner_pct:.1f}%")
    print(f"Estimated straight distance: {straight_pct:.1f}%")

    print("\n" + "-"*100)
    print("AERO DATA AT 100 M/S (TYPICAL STRAIGHT SPEED):")
    print(f"{'Setup':<10} {'Downforce (kN)':<20} {'Drag (kN)':<20} {'L/D Ratio':<15}")
    print("-"*100)

    for name, setup in configs:
        df, drag = aero_data[name]
        ld_ratio = df / drag
        print(f"{name:<10} {df/1000:<20.1f} {drag/1000:<20.1f} {ld_ratio:<15.2f}")

    print("\n" + "-"*100)
    print("TIME IMPACT ESTIMATE:")
    print("-"*100)

    # Assume power-limited acceleration
    # Power = Force * Velocity
    # To maintain same speed against higher drag requires more power
    # At fixed power, higher drag means lower speed

    cal_df, cal_drag = aero_data["CAL"]
    low_df, low_drag = aero_data["LOW"]
    high_df, high_drag = aero_data["HIGH"]

    # Approximate the time cost of extra drag
    # At constant power, extra drag reduces top speed
    # v_top ∝ sqrt(Power / Drag)
    import math
    v_low_ratio = math.sqrt(cal_drag / low_drag)  # Relative top speed vs CAL
    v_high_ratio = math.sqrt(cal_drag / high_drag)

    print(f"\nOn straights (assuming constant power budget):")
    print(f"  LOW relative straight speed vs CAL: {v_low_ratio:.4f} ({100*(v_low_ratio-1):+.2f}%)")
    print(f"  HIGH relative straight speed vs CAL: {v_high_ratio:.4f} ({100*(v_high_ratio-1):+.2f}%)")

    # Estimate lap time impact
    lap_time_cal = 93.4  # From testing
    corner_time_cal = lap_time_cal * corner_pct / 100
    straight_time_cal = lap_time_cal * straight_pct / 100

    print(f"\nEstimated CAL lap composition:")
    print(f"  Corner time: {corner_time_cal:.2f}s ({corner_pct:.1f}%)")
    print(f"  Straight time: {straight_time_cal:.2f}s ({straight_pct:.1f}%)")

    # Corner speed benefit (from v_max_corner calculations)
    # LOW: 222.40 kph, CAL: 228.58 kph, HIGH: 233.59 kph
    # Assuming corners are 20% of lap distance at average v_max
    corner_v_low = 222.40
    corner_v_cal = 228.58
    corner_v_high = 233.59

    # Time in corner ≈ distance / speed
    # If corner distance is 20% of lap, and we travel at v_max:
    # corner_time = corner_distance / v_max
    # More precisely, if corner is at constant radius r, time ≈ arc_length / v_max
    # For simplification, use relative speed advantage

    print(f"\nCorner speed advantage:")
    print(f"  LOW vs CAL: {100*(corner_v_low/corner_v_cal-1):+.2f}%")
    print(f"  HIGH vs CAL: {100*(corner_v_high/corner_v_cal-1):+.2f}%")

    # Approximate time gain/loss
    # Time is inversely proportional to speed
    corner_time_low = corner_time_cal * (corner_v_cal / corner_v_low)
    corner_time_high = corner_time_cal * (corner_v_cal / corner_v_high)

    straight_time_low = straight_time_cal / v_low_ratio
    straight_time_high = straight_time_cal / v_high_ratio

    total_time_low = corner_time_low + straight_time_low
    total_time_high = corner_time_high + straight_time_high

    print(f"\nEstimated lap times (rough calculation):")
    print(f"  LOW:  corner={corner_time_low:.2f}s + straight={straight_time_low:.2f}s = {total_time_low:.2f}s ({total_time_low-lap_time_cal:+.2f}s vs CAL)")
    print(f"  CAL:  corner={corner_time_cal:.2f}s + straight={straight_time_cal:.2f}s = {lap_time_cal:.2f}s")
    print(f"  HIGH: corner={corner_time_high:.2f}s + straight={straight_time_high:.2f}s = {total_time_high:.2f}s ({total_time_high-lap_time_cal:+.2f}s vs CAL)")

    print("\nCONCLUSION:")
    if total_time_low < lap_time_cal:
        print("  LOW's better straight speed outweighs worse corner speed → NET FASTER")
    elif total_time_high > lap_time_cal:
        print("  HIGH's extra drag outweighs better corner speed → NET SLOWER")
    else:
        print("  Balance somewhere in between")

    print("="*100 + "\n")

if __name__ == "__main__":
    analyze_energy()
