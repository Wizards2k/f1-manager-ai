"""
INVESTIGATION: compute_drive_force() Bug Analysis

Question: Why does Turn 1 produce insufficient acceleration at 100-130 kph with 75-89% throttle?

Test: Run compute_drive_force() directly with Turn 1 parameters at different speeds.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lap_simulator.data_types import PUState, EnvContext
from lap_simulator.physics_v3.acceleration_profile import compute_drive_force
from lap_simulator.physics_v3.balance_model import compute_balance
from lap_simulator.physics_v3.aero_mapper import map_aero_setup
from lap_simulator.physics_v3 import constants
from lap_simulator.data_types import AeroSetup
from lap_simulator.config_loader import load_circuit_config


def test_turn1_physics():
    """Test physics at Turn 1 conditions."""

    print("=" * 100)
    print("INVESTIGATING: compute_drive_force() Performance in Turn 1 Acceleration Phase")
    print("=" * 100)

    # Turn 1 parameters
    radius_m = 668.5  # Wide corner
    mass_kg = constants.MASS_DRY_KG + 12.0
    mu_base = 1.90  # C5 soft optimal

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

    pu_state = PUState(
        ice_power_kw=950.0,
        ers_output_kw=160.0,
        ers_energy_mj=4.0,
        fuel_kg=12.0,
    )

    config = load_circuit_config("it-1922_monza")

    # Map aero
    physics_aero = map_aero_setup(
        aero_setup=aero_setup,
        env=env,
        v_estimate_kph=100.0,
        drs_active=False,
        config=config,
    )

    print(f"\nTest Parameters:")
    print(f"  Corner radius: {radius_m:.1f}m (wide → no Kamm circle for R > 200m)")
    print(f"  Mass: {mass_kg:.0f} kg")
    print(f"  Base grip (mu): {mu_base:.2f}")
    print(f"  Power unit: {pu_state.ice_power_kw:.0f} ICE + {pu_state.ers_output_kw:.0f} ERS")
    print(f"  CDA: {physics_aero.CDA:.3f} m²")

    print(f"\n{'Speed':>8} {'Throttle':>10} {'CDF%':>7} {'F_drive':>10} {'a_net':>8} {'Wheelspin':>10}")
    print("-" * 100)

    test_speeds_kph = [80, 90, 100, 110, 115, 120, 125, 130]

    for speed_kph in test_speeds_kph:
        v_ms = speed_kph / 3.6

        # Balance at current speed
        balance = compute_balance(
            mu_base=mu_base,
            aero=physics_aero,
            aero_setup=aero_setup,
            v_ms=v_ms,
            radius_m=radius_m,
            mass_kg=mass_kg,
            env=env,
            a_long_g=0.0,
        )

        # Test at 100% throttle (what the waypoints assume at high throttle)
        F_drive, a_net, wheelspin = compute_drive_force(
            v_ms=v_ms,
            aero=physics_aero,
            balance=balance,
            mass_kg=mass_kg,
            pu_state=pu_state,
            radius_m=radius_m,
            is_cornering=True,
        )

        # Calculate time to go 50m distance at this acceleration (simplified)
        # t = sqrt(2 * d / a)
        dist_m = 50.0
        if a_net > 0.1:
            t_50m = ((v_ms * v_ms + 2 * a_net * dist_m) ** 0.5 - v_ms) / a_net
        else:
            t_50m = dist_m / v_ms

        # Power calculation
        P_total_kw = (pu_state.ice_power_kw + pu_state.ers_output_kw) * constants.DRIVETRAIN_EFFICIENCY
        P_total_w = P_total_kw * 1000.0
        F_drive_power = P_total_w / v_ms
        throttle_utilization = (F_drive / F_drive_power * 100) if F_drive_power > 0 else 0

        print(f"{speed_kph:>8.0f} {100:>9.0f}% {throttle_utilization:>6.1f}% {F_drive:>10.0f}N {a_net:>8.2f} {str(wheelspin):>10}")

    print("\n" + "=" * 100)
    print("ANALYSIS")
    print("=" * 100)

    print("""
Expected behavior at 100% throttle on straight/wide corner:
- Acceleration should decrease with speed (due to increasing drag)
- At 80-90 kph: ~5-6 m/s²
- At 100-110 kph: ~4-5 m/s²
- At 120-130 kph: ~3-4 m/s²

If acceleration INCREASES or stays flat with speed, check:
1. Is drag being calculated correctly? (F_drag = 0.5 * rho * v² * CDA)
2. Is power being limited correctly? (P_total is constant)
3. Is wheelspin detection working? (Should reduce force at low speed)
4. Is there a bug in the Kamm circle calculation?
""")


if __name__ == "__main__":
    test_turn1_physics()
