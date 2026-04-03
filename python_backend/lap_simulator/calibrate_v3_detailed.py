"""
CALIBRATION TOOL: Physics V3 - Detailed Microsector Analysis

Per ogni settore (es. Turn 1 con 43 waypoints):
1. Simula update_section_v3()
2. Estrae telemetry_points dai waypoints
3. Confronta: v_entry, v_exit, accelerazioni, tempi
4. Identifica DOVE diverge dalla realtà
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
from lap_simulator.config_loader import load_circuit_config


def create_car_state_launched() -> CarState:
    """Stato auto LANCIATA (giro warm-up, non primo giro)."""
    car_state = CarState(
        car_id="mclaren_norris",
        team_code="MCL",
        current_section_idx=0,
        section_progress=0.0,
        lap_time_acc_s=0.0,
        lap_number=3,
        v_current_ms=321.6 / 3.6,
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


def analyze_section_detailed(
    section_idx: int,
    section_name: str,
    config_section,
    telem_section: Dict[str, Any],
    car_state: CarState,
    aero_setup: AeroSetup,
    driver_skills: DriverSkills,
    env: EnvContext,
    config: CircuitConfig,
) -> Dict[str, Any]:
    """Analizza dettagliatamente un singolo settore."""

    # Velocità di ingresso
    v_entry_sim = car_state.v_current_ms * 3.6
    v_entry_real = telem_section.get('v_entry_kph', 0)

    # Simula
    result = update_section_v3(
        car_state=car_state,
        aero_setup=aero_setup,
        driver_skills=driver_skills,
        section=config_section,
        env=env,
        config=config,
        push_level=10,
        is_qualifying=True,
        circuit_id="it-1922_monza",
        driver_id="NORRIS",
        lap_number=1,
    )

    # Velocità di uscita
    v_exit_sim = result.v_exit_kph
    v_exit_real = telem_section.get('v_exit_kph', 0)

    # Tempo
    dt_sim = result.dt_s
    dt_real = telem_section.get('dt_ref_s', 0)

    # Telemetry points (da integrazione)
    telemetry = result.telemetry_points

    # Analizza accelerazioni medie
    if len(telemetry) > 1:
        a_avg_sim = sum(tp.get('a_net', 0) for tp in telemetry) / len(telemetry)
    else:
        a_avg_sim = 0.0

    return {
        'section_idx': section_idx,
        'section_name': section_name,
        'v_entry_sim': v_entry_sim,
        'v_entry_real': v_entry_real,
        'v_entry_error': v_entry_sim - v_entry_real,
        'v_exit_sim': v_exit_sim,
        'v_exit_real': v_exit_real,
        'v_exit_error': v_exit_sim - v_exit_real,
        'dt_sim': dt_sim,
        'dt_real': dt_real,
        'dt_error': dt_sim - dt_real,
        'dt_error_pct': (dt_sim - dt_real) / dt_real * 100 if dt_real > 0 else 0,
        'a_avg_sim': a_avg_sim,
        'telemetry_points': telemetry,
        'n_waypoints': len(config_section.waypoints) if config_section.waypoints else 0,
    }


def print_section_report(analysis: Dict[str, Any]):
    """Stampa report dettagliato per un settore."""
    print(f"\n{'='*120}")
    print(f"SECTOR {analysis['section_idx']}: {analysis['section_name']}")
    print(f"{'='*120}")

    print(f"\nVelocity Entry:")
    print(f"  Sim: {analysis['v_entry_sim']:7.2f} kph")
    print(f"  Real: {analysis['v_entry_real']:7.2f} kph")
    print(f"  Error: {analysis['v_entry_error']:+7.2f} kph ({analysis['v_entry_error']/max(1, analysis['v_entry_real'])*100:+6.1f}%)")

    print(f"\nVelocity Exit:")
    print(f"  Sim: {analysis['v_exit_sim']:7.2f} kph")
    print(f"  Real: {analysis['v_exit_real']:7.2f} kph")
    print(f"  Error: {analysis['v_exit_error']:+7.2f} kph ({analysis['v_exit_error']/max(1, analysis['v_exit_real'])*100:+6.1f}%)")

    print(f"\nTime:")
    print(f"  Sim: {analysis['dt_sim']:7.3f} s")
    print(f"  Real: {analysis['dt_real']:7.3f} s")
    print(f"  Error: {analysis['dt_error']:+7.3f} s ({analysis['dt_error_pct']:+6.1f}%)")

    print(f"\nAcceleration (average):")
    print(f"  Sim avg: {analysis['a_avg_sim']:+7.3f} m/s²")

    # Telemetry points sample
    if analysis['telemetry_points']:
        print(f"\nTelemetry Sample ({analysis['n_waypoints']} waypoints, {len(analysis['telemetry_points'])} samples):")
        print(f"  {'dist_m':>8} {'v_kph':>8} {'a_net':>8} {'throttle':>8} {'brake':>8}")

        # First, middle, last
        indices = [0, len(analysis['telemetry_points'])//2, -1]
        for idx in indices:
            tp = analysis['telemetry_points'][idx]
            print(f"  {tp.get('dist_m', 0):8.1f} {tp.get('v_kph', 0):8.2f} {tp.get('a_net', 0):8.3f} "
                  f"{tp.get('throttle_pct', 0):8.0f} {tp.get('brake_pct', 0):8.0f}")


def main():
    print("="*120)
    print("DETAILED MICROSECTOR CALIBRATION: Physics V3 - Monza Qualifying")
    print("="*120)

    # Load data
    with open("python_backend/data/circuits/2025/it-1922_monza_Telemetry.json", "r") as f:
        telem_data = json.load(f)
        sections_telem = telem_data.get('geometry', {}).get('sections', [])

    config = load_circuit_config("it-1922_monza")

    # Setup
    aero_setup = AeroSetup()
    aero_setup.ride_height_front_mm = 25.0
    aero_setup.ride_height_rear_mm = 40.0

    driver_skills = DriverSkills(
        raw_pace=93, consistency=94, race_craft=93, aggression=86,
        tyre_management=88, overtaking_skill=80, defending_skill=80,
        wet_skill=75, smoothness=88, setup_finding=85
    )

    env = EnvContext(
        air_temp_c=28.0,
        track_temp_c=42.0,
        air_density_kg_m3=1.225,
        wind_speed_kph=2.0,
    )

    # Analyze first 5 sectors in detail
    analyses = []
    car_state = create_car_state_launched()

    for idx in range(min(5, len(sections_telem))):
        section_data = sections_telem[idx]
        section = config.sections[idx]

        analysis = analyze_section_detailed(
            section_idx=idx,
            section_name=section_data['name'],
            config_section=section,
            telem_section=section_data,
            car_state=car_state,
            aero_setup=aero_setup,
            driver_skills=driver_skills,
            env=env,
            config=config,
        )

        analyses.append(analysis)
        print_section_report(analysis)

        # Update car state for next section
        car_state.v_current_ms = analysis['v_exit_sim'] / 3.6

    # Summary table
    print(f"\n{'='*120}")
    print("SUMMARY TABLE")
    print(f"{'='*120}")
    print(f"{'Sector':<20} {'v_entry Δ':>12} {'v_exit Δ':>12} {'dt Δ':>12} {'dt % Δ':>12}")
    print(f"{'-'*120}")

    for a in analyses:
        print(f"{a['section_name']:<20} {a['v_entry_error']:+12.2f} {a['v_exit_error']:+12.2f} "
              f"{a['dt_error']:+12.3f} {a['dt_error_pct']:+12.1f}%")

    # Total
    total_dt_sim = sum(a['dt_sim'] for a in analyses)
    total_dt_real = sum(a['dt_real'] for a in analyses)
    print(f"{'-'*120}")
    print(f"{'TOTAL':<20} {'':<12} {'':<12} {total_dt_sim-total_dt_real:+12.3f} "
          f"{(total_dt_sim-total_dt_real)/total_dt_real*100:+12.1f}%")

    print(f"\n✓ Analysis complete")


if __name__ == "__main__":
    main()
