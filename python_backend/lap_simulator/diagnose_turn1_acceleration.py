"""
DIAGNOSTIC: Turn 1 Acceleration Phase - Waypoint-by-Waypoint Analysis

Why does Turn 1 exit at ~104 kph (sim) instead of 121 kph (waypoint target)?

Hypothesis:
The acceleration phase from apex (73.4 kph) to exit (121 kph) requires specific power.
If our physics engine produces less acceleration, the target velocity won't be reached.
"""

import json
import sys
import os
import math
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lap_simulator.data_types import (
    CarState, AeroSetup, PUState, BrakeState, EnvContext, CircuitConfig
)
from lap_simulator.physics_v3.acceleration_profile import compute_drive_force
from lap_simulator.physics_v3.balance_model import compute_balance
from lap_simulator.physics_v3.aero_mapper import map_aero_setup
from lap_simulator.physics_v3 import constants
from lap_simulator.config_loader import load_circuit_config


def calculate_waypoint_physics(
    v_current_ms: float,
    v_ref_kph: float,
    dist_step: float,
    throttle_pct: float,
    radius_m: float,
    aero_setup: AeroSetup,
    env: EnvContext,
    config: CircuitConfig,
) -> Dict[str, Any]:
    """Calculate physics at a waypoint and predict next velocity."""

    mass_kg = constants.MASS_DRY_KG + 12.0  # fuel

    # Aero
    physics_aero = map_aero_setup(
        aero_setup=aero_setup,
        env=env,
        v_estimate_kph=v_current_ms * 3.6,
        drs_active=False,
        config=config,
    )

    # Grip (C5 soft)
    mu_base = 1.90

    # Balance
    balance = compute_balance(
        mu_base=mu_base,
        aero=physics_aero,
        aero_setup=aero_setup,
        v_ms=v_current_ms,
        radius_m=radius_m,
        mass_kg=mass_kg,
        env=env,
        a_long_g=0.0,
    )

    # Power state
    pu_state = PUState(
        ice_power_kw=950.0,
        ers_output_kw=160.0,
        ers_energy_mj=4.0,
        fuel_kg=12.0,
    )

    # Compute drive force
    is_cornering = radius_m > 50.0
    F_drive, a_net_full, wheelspin = compute_drive_force(
        v_ms=v_current_ms,
        aero=physics_aero,
        balance=balance,
        mass_kg=mass_kg,
        pu_state=pu_state,
        radius_m=radius_m,
        is_cornering=is_cornering,
    )

    # Apply throttle scaling (sqrt damping)
    throttle_norm = throttle_pct / 100.0
    throttle_factor = 0.45 + 0.55 * (throttle_norm ** 0.5)
    a_net = a_net_full * throttle_factor

    # Kinematic prediction
    v_new_sq = v_current_ms ** 2 + 2 * a_net * dist_step
    v_new = math.sqrt(max(0, v_new_sq))

    # Clamp to v_ref (7% margin)
    v_ref_ms = v_ref_kph / 3.6
    v_new = min(v_new, v_ref_ms * 1.07)

    # Time
    v_avg = (v_current_ms + v_new) / 2.0
    dt_step = dist_step / v_avg if v_avg > 0.1 else 0.0

    return {
        'v_current_kph': v_current_ms * 3.6,
        'v_ref_kph': v_ref_kph,
        'v_predicted_kph': v_new * 3.6,
        'throttle_pct': throttle_pct,
        'throttle_factor': throttle_factor,
        'a_net_full_ms2': a_net_full,
        'a_net_scaled_ms2': a_net,
        'F_drive_N': F_drive,
        'CDA': physics_aero.CDA,
        'CLA': physics_aero.CLA,
        'mu_rear': balance.mu_rear_eff,
        'radius_m': radius_m,
        'wheelspin': wheelspin,
        'dt_step': dt_step,
        'error_kph': v_new * 3.6 - v_ref_kph,
    }


if __name__ == "__main__":
    print("=" * 120)
    print("DIAGNOSTIC: Turn 1 Acceleration Phase (Waypoint-by-Waypoint)")
    print("=" * 120)

    # Load data
    with open('python_backend/data/circuits/2025/it-1922_monza_HD.json', 'r') as f:
        hd_data = json.load(f)

    config = load_circuit_config("it-1922_monza")

    # Extract Turn 1 acceleration phase (apex to exit)
    # Apex at ~955m, exit at ~995m
    turn1_wps = [wp for wp in hd_data['waypoints'] if 950 <= wp['dist_m'] <= 1000]

    aero_setup = AeroSetup()
    aero_setup.ride_height_front_mm = 25.0
    aero_setup.ride_height_rear_mm = 40.0
    aero_setup.ride_height_optimal_front_mm = 25.0
    aero_setup.ride_height_optimal_rear_mm = 40.0

    env = EnvContext(
        air_temp_c=28.0,
        track_temp_c=42.0,
        air_density_kg_m3=1.175,
    )

    print(f"\nTurn 1 Acceleration Phase: {len(turn1_wps)} waypoints (950-1000m)")
    print(f"\nTarget: {turn1_wps[0]['v_ref_kph']:.1f} kph entry → {turn1_wps[-1]['v_ref_kph']:.1f} kph exit")
    print(f"\n{'Wp#':>4} {'Dist':>7} {'V_cur':>7} {'V_ref':>7} {'V_pred':>7} {'Error':>7} {'Throttle':>8} {'a_full':>7} {'a_scaled':>8}")
    print("-" * 120)

    v_current_ms = turn1_wps[0]['v_ref_kph'] / 3.6
    cumulative_error_kph = 0.0

    for i, wp in enumerate(turn1_wps):
        if i == 0:
            continue  # Skip first waypoint

        wp_prev = turn1_wps[i - 1]
        dist_step = wp['dist_m'] - wp_prev['dist_m']
        throttle_pct = wp_prev.get('throttle_pct', 0)
        radius_m = wp_prev.get('radius_m', 0)

        physics = calculate_waypoint_physics(
            v_current_ms=v_current_ms,
            v_ref_kph=wp['v_ref_kph'],
            dist_step=dist_step,
            throttle_pct=throttle_pct,
            radius_m=radius_m,
            aero_setup=aero_setup,
            env=env,
            config=config,
        )

        error = physics['error_kph']
        cumulative_error_kph += error

        print(f"{i:4d} {wp['dist_m']:7.1f} {physics['v_current_kph']:7.1f} {physics['v_ref_kph']:7.1f} "
              f"{physics['v_predicted_kph']:7.1f} {error:7.2f} {throttle_pct:7.1f}% "
              f"{physics['a_net_full_ms2']:7.2f} {physics['a_net_scaled_ms2']:7.2f}")

        v_current_ms = physics['v_predicted_kph'] / 3.6

    print("-" * 120)
    print(f"FINAL: {turn1_wps[-2]['v_ref_kph']:.1f} kph (ref) → {v_current_ms * 3.6:.1f} kph (sim)")
    print(f"CUMULATIVE ERROR: {cumulative_error_kph:.2f} kph")
    print(f"ERROR PERCENTAGE: {cumulative_error_kph / turn1_wps[-1]['v_ref_kph'] * 100:.1f}%")

    print("\n" + "=" * 120)
    print("ANALYSIS")
    print("=" * 120)
    print(f"\nTurn 1 should exit at {turn1_wps[-1]['v_ref_kph']:.1f} kph")
    print(f"Simulation exits at {v_current_ms * 3.6:.1f} kph")
    print(f"Deficit: {turn1_wps[-1]['v_ref_kph'] - v_current_ms * 3.6:.1f} kph")
    print(f"\nThis deficit causes Straight 2 to start {turn1_wps[-1]['v_ref_kph'] - v_current_ms * 3.6:.1f} kph slower,")
    print(f"requiring extra time to accelerate up to speed, causing +33% error in Straight 2.")
