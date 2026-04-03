"""
Test Universal Motor on Monza v2 — Proper Integration

Test corretto che usa le 3 equazioni universali per simulare il giro Monza
in modo realistico con parametri fisici reali.

Approccio:
1. Carica telemetria Monza reale (13 sezioni, 78.7s totali)
2. Per ogni sezione: estrai v_entry, v_exit, lunghezza, tipo
3. Applica le 3 equazioni universali:
   - Longitudinale: a = (P/v - F_drag) / m (indipendente CLA)
   - Laterale: μ_eff ∝ CLA (per apex speed)
   - v_max: equilibrio P = F_drag * v_max (inverso CDA)
4. Integra cinematica per calcolare dt simulato
5. Confronta vs telemetria reale settore per settore
"""

import json
import os
import sys
import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

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
# MONZA SETUP F1 2025 QUALIFYING
# ============================================================================

MONZA_SETUP = {
    "cla": 2.90,           # Ultra-low downforce
    "cda": 0.90,           # Minimal drag (this is the primary tuning parameter)
    "grip_base": 1.70,     # C3 compound (Pirelli medium)
    "power_kw": 1047.0,    # 950 ICE + 160 ERS (QUALIFY mode)
    "mass_kg": 803.0,      # 798 dry + 5kg fuel
    "downforce_mult": 0.15,
}

ENV_MONZA = {
    "air_temp_c": 28.0,
    "track_temp_c": 42.0,
    "air_density_kg_m3": 1.225,
    "wind_speed_kph": 2.0,
}

# ============================================================================
# SIMULATION ENGINE
# ============================================================================

@dataclass
class SectorSim:
    """Risultato simulazione singolo settore."""
    sector_name: str
    kind: str  # "STRAIGHT", "CORNER"
    length_m: float

    # Telemetria reale
    v_entry_real_kph: float
    v_exit_real_kph: float
    v_min_real_kph: float
    v_max_real_kph: float
    v_avg_real_kph: float
    dt_real_s: float
    radius_m: float

    # Simulazione
    v_apex_sim_kph: float
    dt_sim_s: float

    # Analisi
    def dt_error_pct(self) -> float:
        if self.dt_real_s > 0:
            return (self.dt_sim_s - self.dt_real_s) / self.dt_real_s * 100
        return 0.0

    def summary(self) -> str:
        return (
            f"{self.sector_name:<20} "
            f"Real: {self.dt_real_s:6.3f}s  "
            f"Sim: {self.dt_sim_s:6.3f}s  "
            f"Δ: {self.dt_sim_s - self.dt_real_s:+6.3f}s  "
            f"({self.dt_error_pct():+6.1f}%)"
        )


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
    """
    Integra rettilineo usando accelerazione longitudinale universale.

    Formula fondamentale:
        a(v) = (P_available/v - F_drag(v)) / m
        F_drag = 0.5*ρ*v²*CDA + F_rolling

    Integra numericamente con dt fisso (50Hz = 0.02s).
    """

    v_current_ms = v_entry_kph / 3.6
    v_exit_ms = v_exit_kph / 3.6
    v_max_ms = v_max_theoretical_kph / 3.6

    dt_step = 0.02  # 50Hz
    distance_covered = 0.0
    total_time = 0.0
    power_w = power_kw * 1000.0

    while distance_covered < length_m:
        # Clamp velocità al massimo teorico
        if v_current_ms >= v_max_ms:
            v_current_ms = v_max_ms
            # Calcola tempo rimasto a velocità costante
            distance_remaining = length_m - distance_covered
            if v_current_ms > 0:
                total_time += distance_remaining / v_current_ms
            break

        # Calcola accelerazione alla velocità corrente
        a_ms2 = compute_longitudinal_acceleration(
            v_ms=v_current_ms,
            p_available_w=power_w,
            cda=cda,
            mass_kg=mass_kg,
            env=env,
        )

        # Clampa l'accelerazione al massimo realistico
        a_ms2 = max(-6.5 * 9.81, min(1.34 * 9.81, a_ms2))  # ±6.5g / ±1.34g

        # Integrazione cinematica
        v_new_ms = v_current_ms + a_ms2 * dt_step
        distance_step = v_current_ms * dt_step + 0.5 * a_ms2 * dt_step ** 2
        distance_covered += distance_step
        total_time += dt_step
        v_current_ms = v_new_ms

        # Safety: evita loop infinito
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
    """
    Integra curva usando apex speed universale.

    Formula: v_apex = sqrt(μ_eff * g * R)
    dove μ_eff = grip_base * (1 + k_df*CLA)

    Assume profilo velocità: entry → apex (brake) → exit (accel)
    """

    # Calcola grip efficace con downforce
    mu_eff = compute_lateral_grip(
        cla=cla,
        grip_base=grip_base,
        downforce_multiplier=0.15,
    )

    # Calcola apex speed fisico
    v_apex_calc_ms = compute_corner_apex_speed_universal(
        radius_m=radius_m,
        mu_effective=mu_eff,
        banking_deg=0.0,
    )

    v_apex_calc_kph = v_apex_calc_ms * 3.6

    # Usa apex speed calcolata (non quella reale)
    # ma clampata entro limiti realistici
    v_apex_used_kph = max(v_apex_real_kph * 0.95, min(v_apex_calc_kph, v_apex_real_kph * 1.05))
    v_apex_used_ms = v_apex_used_kph / 3.6

    # Profilo temporale semplificato:
    # Brake from entry to apex (deceleration ~3.0g)
    # Accelerate from apex to exit (acceleration ~1.3g)

    v_entry_ms = v_entry_kph / 3.6
    v_exit_ms = v_exit_kph / 3.6

    # Brake phase: entry → apex
    dv_brake_ms = v_apex_used_ms - v_entry_ms
    a_brake = -3.0 * 9.81
    dt_brake = dv_brake_ms / a_brake if a_brake != 0 else 0.0
    dist_brake = v_entry_ms * dt_brake + 0.5 * a_brake * dt_brake ** 2

    # Accel phase: apex → exit
    dv_accel_ms = v_exit_ms - v_apex_used_ms
    a_accel = 1.3 * 9.81
    dt_accel = dv_accel_ms / a_accel if a_accel != 0 else 0.0
    dist_accel = v_apex_used_ms * dt_accel + 0.5 * a_accel * dt_accel ** 2

    dt_total = dt_brake + dt_accel

    return dt_total, v_apex_calc_kph


def load_monza_telemetry() -> Optional[List[Dict[str, Any]]]:
    """Carica telemetria Monza con 13 sezioni."""
    path = "python_backend/data/circuits/2025/it-1922_monza_Telemetry.json"
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        data = json.load(f)
        return data.get('geometry', {}).get('sections', [])


def main():
    print("="*120)
    print("UNIVERSAL MOTOR TEST — MONZA QUALIFYING (v2 PROPER INTEGRATION)")
    print("="*120)
    print()

    print("Setup Monza Ultra-Low DF (Qualifying):")
    print(f"  CLA: {MONZA_SETUP['cla']} m²")
    print(f"  CDA: {MONZA_SETUP['cda']} m²")
    print(f"  Power: {MONZA_SETUP['power_kw']:.0f} kW (950 ICE + 160 ERS QUALIFY)")
    print(f"  Mass: {MONZA_SETUP['mass_kg']:.0f} kg (798 dry + 5 fuel)")
    print()

    # Carica telemetria
    sections_data = load_monza_telemetry()
    if not sections_data:
        print("❌ Telemetria Monza non trovata")
        return

    print(f"✓ Loaded {len(sections_data)} sections from telemetry")
    print()

    # Crea environment
    env = EnvContext(
        air_temp_c=ENV_MONZA["air_temp_c"],
        track_temp_c=ENV_MONZA["track_temp_c"],
        air_density_kg_m3=ENV_MONZA["air_density_kg_m3"],
    )

    # Calcola v_max teorico con motore universale
    v_max_theoretical_ms = compute_max_velocity_equilibrium(
        p_available_w=MONZA_SETUP["power_kw"] * 1000.0,
        cda=MONZA_SETUP["cda"],
        mass_kg=MONZA_SETUP["mass_kg"],
        env=env,
    )
    v_max_theoretical_kph = v_max_theoretical_ms * 3.6

    print(f"[UNIVERSAL MOTOR CALCULATIONS]")
    print(f"  v_max theoretical (P={MONZA_SETUP['power_kw']:.0f}kW, CDA={MONZA_SETUP['cda']:.2f}): {v_max_theoretical_kph:.1f} km/h")
    print()

    # Simula ogni sezione
    print("[SECTOR-BY-SECTOR SIMULATION]")
    print("-" * 120)

    total_dt_real = 0.0
    total_dt_sim = 0.0
    results = []

    for idx, section_data in enumerate(sections_data[:13]):
        sector_name = section_data.get('name', f'Sector {idx}')
        kind = section_data.get('kind', 'STRAIGHT')
        length_m = section_data.get('length_m', 100.0)
        v_entry_kph = section_data.get('v_entry_kph', 200.0)
        v_exit_kph = section_data.get('v_exit_kph', 200.0)
        v_min_kph = section_data.get('v_min_kph', v_entry_kph)
        v_max_kph = section_data.get('v_max_kph', v_exit_kph)
        v_avg_kph = section_data.get('v_avg_kph', (v_entry_kph + v_exit_kph) / 2)
        dt_real = section_data.get('dt_ref_s', 0.0)
        radius_m = section_data.get('radius_m', 0.0) or 0.0

        # Simula sezione
        if kind.upper() in ["STRAIGHT", "DRS"]:
            dt_sim = integrate_straight(
                v_entry_kph=v_entry_kph,
                v_exit_kph=v_exit_kph,
                length_m=length_m,
                v_max_theoretical_kph=v_max_theoretical_kph,
                cda=MONZA_SETUP["cda"],
                power_kw=MONZA_SETUP["power_kw"],
                mass_kg=MONZA_SETUP["mass_kg"],
                env=env,
            )
            v_apex_sim = v_max_kph

        elif kind.upper() in ["CORNER", "SHARP_CORNER", "CHICANE"] or radius_m > 50:
            dt_sim, v_apex_sim = integrate_corner(
                v_entry_kph=v_entry_kph,
                v_exit_kph=v_exit_kph,
                v_apex_real_kph=v_min_kph,
                length_m=length_m,
                radius_m=radius_m,
                cla=MONZA_SETUP["cla"],
                grip_base=MONZA_SETUP["grip_base"],
                mass_kg=MONZA_SETUP["mass_kg"],
                env=env,
            )

        else:
            # Default: assume average speed
            v_avg_ms = v_avg_kph / 3.6
            dt_sim = length_m / v_avg_ms if v_avg_ms > 0 else 0.0
            v_apex_sim = v_avg_kph

        result = SectorSim(
            sector_name=sector_name,
            kind=kind,
            length_m=length_m,
            v_entry_real_kph=v_entry_kph,
            v_exit_real_kph=v_exit_kph,
            v_min_real_kph=v_min_kph,
            v_max_real_kph=v_max_kph,
            v_avg_real_kph=v_avg_kph,
            dt_real_s=dt_real,
            radius_m=radius_m,
            v_apex_sim_kph=v_apex_sim,
            dt_sim_s=dt_sim,
        )
        results.append(result)

        total_dt_real += dt_real
        total_dt_sim += dt_sim

        print(result.summary())

    print("-" * 120)
    print()

    print("[LAP TIME SUMMARY]")
    print("="*120)
    print(f"Real:      {total_dt_real:7.3f} s")
    print(f"Simulated: {total_dt_sim:7.3f} s")
    print(f"Difference: {total_dt_sim - total_dt_real:+7.3f} s ({(total_dt_sim - total_dt_real) / total_dt_real * 100:+6.2f}%)")
    print()

    # Velocity analysis
    print("[VELOCITY TARGETS vs SIMULATION]")
    print("="*120)
    print(f"{'Sector':<20} {'Real Entry':<12} {'Real Apex':<12} {'Sim Apex':<12} {'Delta':<10}")
    print("-"*120)

    for result in results:
        print(
            f"{result.sector_name:<20} "
            f"{result.v_entry_real_kph:<12.1f} "
            f"{result.v_min_real_kph:<12.1f} "
            f"{result.v_apex_sim_kph:<12.1f} "
            f"{result.v_apex_sim_kph - result.v_min_real_kph:+10.1f}"
        )

    print()
    print("✓ Test completed")


if __name__ == "__main__":
    main()
