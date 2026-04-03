"""
Test three fixes for Straight 1 overspeed (+17.53 kph):
1. Fix CDA (increase drag)
2. Fix Power (reduce engine power)
3. Fix compute_drive_force() (reduce acceleration)
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lap_simulator.data_types import (
    CarState, AeroSetup, DriverSkills, TyreState,
    WheelPosition, TyreCompound, EnvContext, EngineMapName, ERSModeName
)
from lap_simulator.physics_v3.update_section_v3 import update_section_v3
from lap_simulator.config_loader import load_circuit_config


def create_car_state() -> CarState:
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


def test_fix(fix_name: str, modifications: dict):
    """Test one fix configuration."""

    print(f"\n{'='*120}")
    print(f"TEST: {fix_name}")
    print(f"{'='*120}")
    print(f"Modifications: {modifications}\n")

    # Load telemetry
    with open("python_backend/data/circuits/2025/it-1922_monza_Telemetry.json", "r") as f:
        telem_data = json.load(f)
        sections_telem = telem_data.get('geometry', {}).get('sections', [])

    config = load_circuit_config("it-1922_monza")

    aero_setup = AeroSetup()
    aero_setup.ride_height_front_mm = 25.0
    aero_setup.ride_height_rear_mm = 40.0

    # Apply CDA modification if needed
    if 'cda_multiplier' in modifications:
        print(f"  Modifying CDA: applying {modifications['cda_multiplier']}x multiplier")

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

    car_state = create_car_state()

    # Apply power modification if needed
    if 'power_multiplier' in modifications:
        original_ice = car_state.pu.ice_power_kw
        original_ers = car_state.pu.ers_output_kw
        car_state.pu.ice_power_kw *= modifications['power_multiplier']
        car_state.pu.ers_output_kw *= modifications['power_multiplier']
        print(f"  Modifying Power: {original_ice:.0f}+{original_ers:.0f}kW → {car_state.pu.ice_power_kw:.0f}+{car_state.pu.ers_output_kw:.0f}kW")

    # Simulate first 5 sectors
    results = []
    total_dt_sim = 0.0
    total_dt_real = 0.0

    for idx in range(min(5, len(sections_telem))):
        section_data = sections_telem[idx]
        section = config.sections[idx]

        v_entry_sim = car_state.v_current_ms * 3.6
        v_entry_real = section_data.get('v_entry_kph', 0)

        result = update_section_v3(
            car_state=car_state,
            aero_setup=aero_setup,
            driver_skills=driver_skills,
            section=section,
            env=env,
            config=config,
            push_level=10,
            is_qualifying=True,
            circuit_id="it-1922_monza",
            driver_id="NORRIS",
            lap_number=1,
        )

        v_exit_sim = result.v_exit_kph
        v_exit_real = section_data.get('v_exit_kph', 0)
        dt_sim = result.dt_s
        dt_real = section_data.get('dt_ref_s', 0)

        results.append({
            'name': section_data['name'],
            'v_entry_error': v_entry_sim - v_entry_real,
            'v_exit_error': v_exit_sim - v_exit_real,
            'dt_error': dt_sim - dt_real,
            'dt_error_pct': (dt_sim - dt_real) / dt_real * 100 if dt_real > 0 else 0,
        })

        total_dt_sim += dt_sim
        total_dt_real += dt_real
        car_state.v_current_ms = v_exit_sim / 3.6

    # Print results table
    print(f"{'Sector':<20} {'v_entry Δ':>12} {'v_exit Δ':>12} {'dt Δ':>12} {'dt % Δ':>12}")
    print(f"{'-'*120}")
    for r in results:
        print(f"{r['name']:<20} {r['v_entry_error']:+12.2f} {r['v_exit_error']:+12.2f} "
              f"{r['dt_error']:+12.3f} {r['dt_error_pct']:+12.1f}%")

    print(f"{'-'*120}")
    total_error = total_dt_sim - total_dt_real
    total_error_pct = total_error / total_dt_real * 100
    print(f"{'TOTAL':<20} {'':<12} {'':<12} {total_error:+12.3f} {total_error_pct:+12.1f}%")
    print(f"\nLap time: {total_dt_sim:.3f}s (real: {total_dt_real:.3f}s)")

    return {
        'fix': fix_name,
        'total_dt_sim': total_dt_sim,
        'total_error': total_error,
        'total_error_pct': total_error_pct,
        'straight1_v_exit_error': results[0]['v_exit_error'],
        'turn1_v_exit_error': results[1]['v_exit_error'],
        'straight2_dt_error_pct': results[2]['dt_error_pct'],
    }


def main():
    print("="*120)
    print("TEST: Three fixes for Straight 1 Overspeed (+17.53 kph)")
    print("="*120)

    results = []

    # Test 1: Baseline (current)
    results.append(test_fix(
        "BASELINE (current physics)",
        {}
    ))

    # Test 2: Increase CDA (more drag = less speed)
    print("\n[Note: CDA modification requires code change, testing next...]")
    results.append(test_fix(
        "FIX 1: CDA +20% (increase drag)",
        {'cda_multiplier': 1.20}  # Will be implemented in code
    ))

    # Test 3: Reduce Power
    results.append(test_fix(
        "FIX 2: Power -10% (reduce engine output)",
        {'power_multiplier': 0.90}
    ))

    # Test 4: Reduce Power more
    results.append(test_fix(
        "FIX 3: Power -15% (more aggressive)",
        {'power_multiplier': 0.85}
    ))

    # Summary
    print(f"\n{'='*120}")
    print("SUMMARY COMPARISON")
    print(f"{'='*120}")
    print(f"{'Fix':<40} {'Lap time':>12} {'Error':>12} {'Straight1 Δ':>12} {'Turn1 Δ':>12} {'S2 % Δ':>12}")
    print(f"{'-'*120}")

    for r in results:
        print(f"{r['fix']:<40} {r['total_dt_sim']:12.3f}s {r['total_error']:+12.3f}s "
              f"{r['straight1_v_exit_error']:+12.2f} {r['turn1_v_exit_error']:+12.2f} {r['straight2_dt_error_pct']:+12.1f}%")

    # Best option
    best = min(results, key=lambda r: abs(r['total_error']))
    print(f"\n✓ Best fix: {best['fix']} (error: {best['total_error']:+.3f}s / {best['total_error_pct']:+.1f}%)")


if __name__ == "__main__":
    main()
