"""
DIAGNOSTIC TOOL: Analyze Straight 2 acceleration deficit

Straight 2 details:
- Real: 13.260s to accelerate from 83.4 kph to 322 kph in 1013m
- Sim:  18.232s (27% slower)
- Real acceleration: 5.0 m/s²
- Sim acceleration: 3.94 m/s²

Goal: Identify where the 27% power deficit comes from.
"""

import json
import sys
import os
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lap_simulator.data_types import (
    CarState, AeroSetup, DriverSkills, TyreState, BrakeState, PUState,
    WheelPosition, TyreCompound, EnvContext, CircuitConfig,
    EngineMapName, ERSModeName
)
from lap_simulator.physics_v3.update_section_v3 import update_section_v3
from lap_simulator.physics_v3.acceleration_profile import compute_drive_force
from lap_simulator.physics_v3.balance_model import compute_balance
from lap_simulator.physics_v3.aero_mapper import map_aero_setup
from lap_simulator.physics_v3 import constants
from lap_simulator.config_loader import load_circuit_config


def create_car_state_straight2_entry() -> CarState:
    """Stato auto all'entry di Straight 2 (dopo Turn 1)."""
    car_state = CarState(
        car_id="mclaren_norris",
        team_code="MCL",
        current_section_idx=2,
        section_progress=0.0,
        lap_time_acc_s=0.0,
        lap_number=3,
        v_current_ms=83.4 / 3.6,  # 23.17 m/s (real entry speed)
    )

    for position in WheelPosition:
        car_state.tyres[position] = TyreState(
            wheel_pos=position,
            compound=TyreCompound.C5,
            surface_temp_c=118.0,
            core_temp_c=115.0,
            wear_pct=2.0,
        )

    car_state.brakes.temp_front_c = 650.0
    car_state.brakes.temp_rear_c = 620.0
    car_state.pu.active_map = EngineMapName.QUALIFY
    car_state.pu.ers_mode = ERSModeName.QUALIFY
    car_state.pu.ice_power_kw = 950.0
    car_state.pu.ers_output_kw = 160.0
    car_state.pu.ers_energy_mj = 4.0
    car_state.pu.fuel_kg = 12.0

    return car_state


def analyze_acceleration_force(
    v_ms: float,
    aero_setup: AeroSetup,
    env: EnvContext,
    config: CircuitConfig,
) -> Dict[str, Any]:
    """Analizza le forze di trazione e resistenza a una data velocità."""

    # Parametri auto
    mass_kg = constants.MASS_DRY_KG + 12.0  # + fuel

    # Aero mapping
    physics_aero = map_aero_setup(
        aero_setup=aero_setup,
        env=env,
        v_estimate_kph=v_ms * 3.6,
        drs_active=False,
        config=config,
    )

    # Grip
    mu_base = 1.90  # C5 SOFT optimal temperature

    # Balance (straight, radius=0)
    balance = compute_balance(
        mu_base=mu_base,
        aero=physics_aero,
        aero_setup=aero_setup,
        v_ms=v_ms,
        radius_m=0.0,  # STRAIGHT
        mass_kg=mass_kg,
        env=env,
        a_long_g=0.0,
    )

    # Power state
    pu_state = PUState(
        active_map=EngineMapName.QUALIFY,
        ers_mode=ERSModeName.QUALIFY,
        ice_temp_c=80.0,
        ice_power_kw=950.0,
        ers_output_kw=160.0,
        ers_energy_mj=4.0,
        fuel_kg=12.0,
    )

    # Compute drive force
    F_drive, a_net, wheelspin = compute_drive_force(
        v_ms=v_ms,
        aero=physics_aero,
        balance=balance,
        mass_kg=mass_kg,
        pu_state=pu_state,
        radius_m=0.0,  # STRAIGHT
        is_cornering=False,
    )

    # Drag calculation
    rho = env.air_density_kg_m3
    F_drag_aero = 0.5 * rho * (v_ms ** 2) * physics_aero.CDA
    F_drag_rolling = constants.ROLLING_RESISTANCE_COEFF * balance.Fz_rear
    F_drag_total = F_drag_aero + F_drag_rolling

    # Power calculation
    P_total_kw = (pu_state.ice_power_kw + pu_state.ers_output_kw) * constants.DRIVETRAIN_EFFICIENCY
    P_total_w = P_total_kw * 1000.0
    F_drive_power = P_total_w / v_ms if v_ms > 0.1 else 0

    return {
        'v_kph': v_ms * 3.6,
        'v_ms': v_ms,
        'P_total_kw': P_total_kw,
        'F_drive_power_N': F_drive_power,
        'F_drive_actual_N': F_drive,
        'F_drag_aero_N': F_drag_aero,
        'F_drag_rolling_N': F_drag_rolling,
        'F_drag_total_N': F_drag_total,
        'F_net_N': F_drive - F_drag_total,
        'a_net_ms2': a_net,
        'CLA': physics_aero.CLA,
        'CDA': physics_aero.CDA,
        'mu_rear_eff': balance.mu_rear_eff,
        'Fz_rear_N': balance.Fz_rear,
        'wheelspin': wheelspin,
    }


if __name__ == "__main__":
    print("=" * 100)
    print("DIAGNOSTIC: Straight 2 Acceleration Deficit Analysis")
    print("=" * 100)

    # Load circuit config
    config = load_circuit_config("it-1922_monza")

    # Get Straight 2 section
    section_idx = 2  # Index 2 is Straight 2
    straight2_config = config.sections[section_idx]

    print(f"\nSection: {straight2_config.name}")
    print(f"  Entry (real):  83.4 kph")
    print(f"  Exit (real):   322 kph")
    print(f"  Length:        1013m")
    print(f"  Duration (real): 13.26s")
    print(f"  Required a_avg: 5.0 m/s²")

    # Setup
    aero_setup = AeroSetup()
    aero_setup.ride_height_front_mm = 25.0
    aero_setup.ride_height_rear_mm = 40.0
    aero_setup.ride_height_optimal_front_mm = 25.0
    aero_setup.ride_height_optimal_rear_mm = 40.0

    # Environment (Monza, hot day)
    env = EnvContext(
        air_temp_c=28.0,
        track_temp_c=42.0,
        air_density_kg_m3=1.175,
        rain_intensity=0.0,
    )

    print("\n" + "=" * 100)
    print("FORCE ANALYSIS AT DIFFERENT SPEEDS")
    print("=" * 100)

    speeds_kph = [83.4, 100, 150, 200, 250, 300, 322]

    print(f"\n{'Speed':>8} {'P_total':>10} {'F_drive':>10} {'F_drag':>10} {'F_net':>10} {'a_net':>8} {'Wheelspin':>10}")
    print("-" * 100)

    for speed_kph in speeds_kph:
        v_ms = speed_kph / 3.6
        analysis = analyze_acceleration_force(
            v_ms=v_ms,
            aero_setup=aero_setup,
            env=env,
            config=config,
        )

        print(f"{speed_kph:>8.1f} {analysis['P_total_kw']:>10.0f} {analysis['F_drive_actual_N']:>10.0f} "
              f"{analysis['F_drag_total_N']:>10.0f} {analysis['F_net_N']:>10.0f} "
              f"{analysis['a_net_ms2']:>8.2f} {str(analysis['wheelspin']):>10}")

    # Calculate integrated acceleration from entry to exit
    print("\n" + "=" * 100)
    print("INTEGRATION: Entry to Exit")
    print("=" * 100)

    # Required physics for 13.26s to go from 83.4 to 322 kph in 1013m
    v_entry_ms = 83.4 / 3.6
    v_exit_ms = 322 / 3.6
    dt_real = 13.260
    distance = 1013

    # Average acceleration
    a_avg_required = (v_exit_ms ** 2 - v_entry_ms ** 2) / (2 * distance)
    print(f"\nReal trajectory:")
    print(f"  v_entry: {v_entry_ms:.2f} m/s ({83.4:.1f} kph)")
    print(f"  v_exit:  {v_exit_ms:.2f} m/s ({322:.1f} kph)")
    print(f"  distance: {distance}m")
    print(f"  time: {dt_real:.3f}s")
    print(f"  a_avg required: {a_avg_required:.3f} m/s²")

    # Analysis at different points
    print(f"\nForce analysis at key points:")

    key_speeds = [v_entry_ms, (v_entry_ms + v_exit_ms) / 2, v_exit_ms]
    for v_ms in key_speeds:
        analysis = analyze_acceleration_force(
            v_ms=v_ms,
            aero_setup=aero_setup,
            env=env,
            config=config,
        )
        print(f"\n  At {analysis['v_kph']:.1f} kph:")
        print(f"    a = {analysis['a_net_ms2']:.3f} m/s² (required: {a_avg_required:.3f})")
        print(f"    F_drive = {analysis['F_drive_actual_N']:.0f}N (power-limited: {analysis['F_drive_power_N']:.0f}N)")
        print(f"    F_drag = {analysis['F_drag_total_N']:.0f}N")
        print(f"    CDA = {analysis['CDA']:.3f} m²")
        print(f"    mu_rear = {analysis['mu_rear_eff']:.3f}")
