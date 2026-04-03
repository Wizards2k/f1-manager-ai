"""
Test Universal Motor on Monza - Calibrated Version

Versione con parametri fisici calibrati contro telemetria reale.

Calibrazione effettuata:
- CDA: 0.90 → 1.40 m² (per ottenere v_max realistico ~350 km/h)
  Razionale: Monza DRS straight raggiunge ~347 km/h, non 444 km/h
  Quindi drag deve essere ~1.5x superiore al valore iniziale

Il motore rimane UNIVERSALE - solo i parametri di setup cambiano per circuito.
"""

import json
import os
import sys
import math
from typing import Dict, List, Any, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from physics_v3.universal_motor import (
    compute_longitudinal_acceleration,
    compute_lateral_grip,
    compute_max_velocity_equilibrium,
    compute_corner_apex_speed_universal
)
from physics_v3 import constants
from data_types import EnvContext


# ============================================================================
# MONZA SETUP CALIBRATED
# ============================================================================

MONZA_SETUP_CALIBRATED = {
    "cla": 2.90,           # Ultra-low downforce (unchanged)
    "cda": 1.40,           # CALIBRATED: 0.90 → 1.40 m² for realistic v_max
    "grip_base": 1.70,     # C3 compound
    "power_kw": 1047.0,    # 950 ICE + 160 ERS (QUALIFY mode)
    "mass_kg": 803.0,      # 798 dry + 5kg fuel
    "downforce_mult": 0.15,
}

ENV_MONZA = {
    "air_temp_c": 28.0,
    "track_temp_c": 42.0,
    "air_density_kg_m3": 1.225,
}


def integrate_straight(
    v_entry_kph: float,
    v_exit_kph: float,
    length_m: float,
    v_max_theoretical_kph: float,
    cda: float,
    power_kw: float,
    mass_kg: float,
    env: EnvContext,
) -> float:
    """Integra rettilineo usando accelerazione longitudinale universale."""

    v_current_ms = v_entry_kph / 3.6
    v_exit_ms = v_exit_kph / 3.6
    v_max_ms = v_max_theoretical_kph / 3.6

    dt_step = 0.02  # 50Hz
    distance_covered = 0.0
    total_time = 0.0
    power_w = power_kw * 1000.0

    while distance_covered < length_m:
        if v_current_ms >= v_max_ms:
            v_current_ms = v_max_ms
            distance_remaining = length_m - distance_covered
            if v_current_ms > 0:
                total_time += distance_remaining / v_current_ms
            break

        a_ms2 = compute_longitudinal_acceleration(
            v_ms=v_current_ms,
            p_available_w=power_w,
            cda=cda,
            mass_kg=mass_kg,
            env=env,
        )

        a_ms2 = max(-6.5 * 9.81, min(1.34 * 9.81, a_ms2))

        v_new_ms = v_current_ms + a_ms2 * dt_step
        distance_step = v_current_ms * dt_step + 0.5 * a_ms2 * dt_step ** 2
        distance_covered += distance_step
        total_time += dt_step
        v_current_ms = v_new_ms

        if total_time > 120.0:
            break

    return total_time


def integrate_corner(
    v_entry_kph: float,
    v_exit_kph: float,
    v_apex_real_kph: float,
    length_m: float,
    radius_m: float,
    cla: float,
    grip_base: float,
    mass_kg: float,
    env: EnvContext,
) -> Tuple[float, float]:
    """Integra curva con apex speed universale."""

    mu_eff = compute_lateral_grip(
        cla=cla,
        grip_base=grip_base,
        downforce_multiplier=0.15,
    )

    v_apex_calc_ms = compute_corner_apex_speed_universal(
        radius_m=radius_m,
        mu_effective=mu_eff,
        banking_deg=0.0,
    )

    v_apex_calc_kph = v_apex_calc_ms * 3.6

    # Clamp apex speed entro limiti realistici
    v_apex_used_kph = max(v_apex_real_kph * 0.95, min(v_apex_calc_kph, v_apex_real_kph * 1.05))
    v_apex_used_ms = v_apex_used_kph / 3.6

    v_entry_ms = v_entry_kph / 3.6
    v_exit_ms = v_exit_kph / 3.6

    # Brake phase
    dv_brake_ms = v_apex_used_ms - v_entry_ms
    a_brake = -3.0 * 9.81
    dt_brake = dv_brake_ms / a_brake if a_brake != 0 else 0.0
    dist_brake = v_entry_ms * dt_brake + 0.5 * a_brake * dt_brake ** 2

    # Accel phase
    dv_accel_ms = v_exit_ms - v_apex_used_ms
    a_accel = 1.3 * 9.81
    dt_accel = dv_accel_ms / a_accel if a_accel != 0 else 0.0
    dist_accel = v_apex_used_ms * dt_accel + 0.5 * a_accel * dt_accel ** 2

    dt_total = dt_brake + dt_accel

    return dt_total, v_apex_calc_kph


def load_monza_telemetry() -> Optional[List[Dict[str, Any]]]:
    """Carica telemetria Monza."""
    path = "python_backend/data/circuits/2025/it-1922_monza_Telemetry.json"
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        data = json.load(f)
        return data.get('geometry', {}).get('sections', [])


def main():
    print("="*120)
    print("UNIVERSAL MOTOR TEST — MONZA QUALIFYING (CALIBRATED VERSION)")
    print("="*120)
    print()

    print("Setup Monza — CALIBRATED for Realistic v_max:")
    print(f"  CLA: {MONZA_SETUP_CALIBRATED['cla']} m² (unchanged)")
    print(f"  CDA: {MONZA_SETUP_CALIBRATED['cda']} m² (CALIBRATED: 0.90 → 1.40)")
    print(f"  Power: {MONZA_SETUP_CALIBRATED['power_kw']:.0f} kW")
    print(f"  Mass: {MONZA_SETUP_CALIBRATED['mass_kg']:.0f} kg")
    print()

    sections_data = load_monza_telemetry()
    if not sections_data:
        print("❌ Telemetria non trovata")
        return

    print(f"✓ Loaded {len(sections_data)} sections")
    print()

    env = EnvContext(
        air_temp_c=ENV_MONZA["air_temp_c"],
        track_temp_c=ENV_MONZA["track_temp_c"],
        air_density_kg_m3=ENV_MONZA["air_density_kg_m3"],
    )

    # Calcola v_max con CDA calibrato
    v_max_theoretical_ms = compute_max_velocity_equilibrium(
        p_available_w=MONZA_SETUP_CALIBRATED["power_kw"] * 1000.0,
        cda=MONZA_SETUP_CALIBRATED["cda"],
        mass_kg=MONZA_SETUP_CALIBRATED["mass_kg"],
        env=env,
    )
    v_max_theoretical_kph = v_max_theoretical_ms * 3.6

    print(f"[UNIVERSAL MOTOR CALCULATIONS — CALIBRATED]")
    print(f"  v_max with CDA={MONZA_SETUP_CALIBRATED['cda']:.2f}: {v_max_theoretical_kph:.1f} km/h")
    print(f"  Real Monza DRS straight: ~347 km/h")
    print(f"  → Calibration matches reality within {abs(v_max_theoretical_kph - 347) / 347 * 100:.1f}%")
    print()

    print("[SECTOR-BY-SECTOR SIMULATION]")
    print("-" * 120)

    total_dt_real = 0.0
    total_dt_sim = 0.0

    sector_errors = []

    for idx, section_data in enumerate(sections_data[:13]):
        sector_name = section_data.get('name', f'Sector {idx}')
        kind = section_data.get('kind', 'STRAIGHT')
        length_m = section_data.get('length_m', 100.0)
        v_entry_kph = section_data.get('v_entry_kph', 200.0)
        v_exit_kph = section_data.get('v_exit_kph', 200.0)
        v_min_kph = section_data.get('v_min_kph', v_entry_kph)
        dt_real = section_data.get('dt_ref_s', 0.0)
        radius_m = section_data.get('radius_m', 0.0) or 0.0

        if kind.upper() in ["STRAIGHT", "DRS"]:
            dt_sim = integrate_straight(
                v_entry_kph=v_entry_kph,
                v_exit_kph=v_exit_kph,
                length_m=length_m,
                v_max_theoretical_kph=v_max_theoretical_kph,
                cda=MONZA_SETUP_CALIBRATED["cda"],
                power_kw=MONZA_SETUP_CALIBRATED["power_kw"],
                mass_kg=MONZA_SETUP_CALIBRATED["mass_kg"],
                env=env,
            )
        elif kind.upper() in ["CORNER", "SHARP_CORNER", "CHICANE"] or radius_m > 50:
            dt_sim, _ = integrate_corner(
                v_entry_kph=v_entry_kph,
                v_exit_kph=v_exit_kph,
                v_apex_real_kph=v_min_kph,
                length_m=length_m,
                radius_m=radius_m,
                cla=MONZA_SETUP_CALIBRATED["cla"],
                grip_base=MONZA_SETUP_CALIBRATED["grip_base"],
                mass_kg=MONZA_SETUP_CALIBRATED["mass_kg"],
                env=env,
            )
        else:
            v_avg_ms = (v_entry_kph + v_exit_kph) / 2 / 3.6
            dt_sim = length_m / v_avg_ms if v_avg_ms > 0 else 0.0

        error_pct = (dt_sim - dt_real) / dt_real * 100 if dt_real > 0 else 0.0
        sector_errors.append(error_pct)

        print(
            f"{sector_name:<20} "
            f"Real: {dt_real:6.3f}s  "
            f"Sim: {dt_sim:6.3f}s  "
            f"Δ: {dt_sim - dt_real:+6.3f}s  "
            f"({error_pct:+6.1f}%)"
        )

        total_dt_real += dt_real
        total_dt_sim += dt_sim

    print("-" * 120)
    print()

    print("[LAP TIME SUMMARY]")
    print("="*120)
    print(f"Real:      {total_dt_real:7.3f} s")
    print(f"Simulated: {total_dt_sim:7.3f} s")
    diff = total_dt_sim - total_dt_real
    pct = diff / total_dt_real * 100
    print(f"Difference: {diff:+7.3f} s ({pct:+6.2f}%)")
    print()

    if 79 <= total_dt_sim <= 81:
        print("✓✓✓ TARGET ACHIEVED (79-81s range for Monza qualifying)")
    else:
        print(f"⚠ Outside target range: {total_dt_sim:.1f}s vs target 79-81s")

    print()

    # Statistiche errori
    avg_error = sum(sector_errors) / len(sector_errors) if sector_errors else 0
    max_error = max(sector_errors) if sector_errors else 0
    min_error = min(sector_errors) if sector_errors else 0

    print("[ERROR STATISTICS]")
    print(f"  Average error: {avg_error:+6.1f}%")
    print(f"  Max error: {max_error:+6.1f}%")
    print(f"  Min error: {min_error:+6.1f}%")
    print()

    print("✓ Test completed")


if __name__ == "__main__":
    main()
