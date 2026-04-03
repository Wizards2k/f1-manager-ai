"""
Test Universal Motor on Monza with McLaren/Norris - Qualifying Setup

Test setup:
- Circuit: Monza (it-1922_monza)
- Team: McLaren (mclaren)
- Driver: Lando Norris
- Session: Qualifying (push_level=10, min fuel, QUALIFY engine map, QUALIFY ERS mode)
- Aero Setup: Qualifying configuration (low DF: FW=31, RW=21)

Expected output:
- Sector-by-sector comparison vs real telemetry
- All physical parameters: speeds, accelerations, times, grip
"""

import json
import os
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import math

# Importa costanti e funzioni dal motore universale
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_types import (
    CarState, AeroSetup, AeroComponent, SuspensionState,
    EngineMapName, ERSModeName, TyreCompound,
    SectionContext, Waypoint, EnvContext
)
from physics_v3.universal_motor import (
    compute_longitudinal_acceleration,
    compute_lateral_grip,
    compute_max_velocity_equilibrium,
    compute_corner_apex_speed_universal
)
from physics_v3 import constants


@dataclass
class SectorReport:
    """Rapporto settore singolo."""
    sector_id: str
    sector_name: str

    # Velocità [km/h]
    v_entry_real: float
    v_entry_sim: float
    v_exit_real: float
    v_exit_sim: float
    v_min_real: float
    v_min_sim: float
    v_max_real: float
    v_max_sim: float
    v_avg_real: float
    v_avg_sim: float

    # Tempi [s]
    dt_real: float
    dt_sim: float

    # Accelerazioni [g]
    a_mean_real: float
    a_mean_sim: float
    a_lat_real: float
    a_lat_sim: float

    # Parametri fisici
    radius_m: float
    grip_available: float
    grip_utilized_real: float
    grip_utilized_sim: float

    # Analisi
    dv_entry_error: float      # km/h difference
    dv_exit_error: float
    dv_avg_error: float
    dt_error: float            # s difference
    dt_error_pct: float        # percentage


def load_monza_telemetry() -> Optional[Dict[str, Any]]:
    """Carica telemetria Monza reale F1 2025."""
    path = "python_backend/data/circuits/2025/it-1922_monza_Telemetry.json"
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)


def load_monza_waypoints() -> Optional[List[Dict[str, Any]]]:
    """Carica waypoints HD Monza."""
    path = "python_backend/data/circuits/2025/it-1922_monza_HD.json"
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f).get('waypoints', [])


def create_monza_aero_setup() -> AeroSetup:
    """
    Crea setup Monza per qualifica (ultra-basso DF).

    Dati da ai_optimal_setups.json:
    - best_fw: 31 (0-100)
    - best_rw: 21 (0-100)
    - rh_f: 25.0 mm
    - rh_r: 40.0 mm
    - susp_f: 0.5 (0-1)
    - susp_r: 0.5 (0-1)
    - arb_f: 0.5 (0-1)
    - arb_r: 0.5 (0-1)
    """

    # Mappiamo i slider 0-100 a downforce/drag values
    # Low DF per Monza: FW=31 (~30%) e RW=21 (~20%)
    # Questo corrisponde a CLA ≈ 2.90 m² (ultra-basso)

    setup = AeroSetup()

    # Front wing: 31/100 = basso
    setup.front_wing.base_downforce = 31.0
    setup.front_wing.angle_deg = 5.0  # shallow angle for low DF

    # Rear wing: 21/100 = molto basso
    setup.rear_wing.base_downforce = 21.0
    setup.rear_wing.angle_deg = 3.0

    # Ride heights
    setup.ride_height_front_mm = 25.0
    setup.ride_height_rear_mm = 40.0
    setup.ride_height_optimal_front_mm = 25.0
    setup.ride_height_optimal_rear_mm = 40.0

    # Suspension stiffness
    setup.suspension_front.spring_rate_n_mm = 0.5
    setup.suspension_rear.spring_rate_n_mm = 0.5

    # ARB stiffness
    setup.antiroll_front_rigidity = 0.5
    setup.antiroll_rear_rigidity = 0.5

    return setup


def simulate_section(
    section: SectionContext,
    v_entry_kph: float,
    aero_setup: AeroSetup,
    env: EnvContext,
    mass_kg: float = 803.0,  # 798 + 5kg fuel
) -> tuple[float, float, float, float, float]:
    """
    Simula una singola sezione con il motore universale.

    Returns:
        (dt_s, v_exit_kph, v_min_kph, v_max_kph, v_avg_kph)
    """

    # Parametri fisici
    v_entry_ms = v_entry_kph / 3.6

    # Setup aerodinamico (assumiamo mapping semplice per test)
    # Per Monza: CLA ≈ 2.90 m², CDA ≈ 0.90 m²
    cla = 2.90
    cda = 0.90

    # Grip base da compound
    kind_str = str(section.kind).upper() if section.kind else "STRAIGHT"

    if kind_str in ["STRAIGHT", "ACCELERATION", "DRS"]:
        # Rettilineo: principalmente accelerazione
        dt_s = section.length_m / (v_entry_ms + 5) if v_entry_ms > 0 else section.length_m / 20
        v_exit_ms = v_entry_ms + 5
        v_min_ms = v_entry_ms
        v_max_ms = v_exit_ms
        v_avg_ms = (v_entry_ms + v_exit_ms) / 2

    elif kind_str in ["CORNER", "SHARP_CORNER", "CHICANE"]:
        # Curva: principalmente laterale
        radius_m = section.curve_profile.radius_m or 400
        grip_base = 1.70  # C3 compound

        # Compute effective grip con downforce
        mu_eff = compute_lateral_grip(
            cla=cla,
            grip_base=grip_base,
            downforce_multiplier=0.15
        )

        # Apex speed
        v_apex_ms = compute_corner_apex_speed_universal(
            radius_m=radius_m,
            mu_effective=mu_eff,
            banking_deg=section.curve_profile.banking_deg
        )

        # Entry → Apex → Exit
        dt_s = section.length_m / ((v_entry_ms + v_apex_ms + v_entry_ms) / 3)
        v_exit_ms = v_entry_ms
        v_min_ms = v_apex_ms
        v_max_ms = v_entry_ms
        v_avg_ms = (v_entry_ms + v_apex_ms) / 2

    else:
        # Default: assume constant speed
        dt_s = section.length_m / (v_entry_ms + 1) if v_entry_ms > 0 else section.length_m / 20
        v_exit_ms = v_entry_ms
        v_min_ms = v_entry_ms
        v_max_ms = v_entry_ms
        v_avg_ms = v_entry_ms

    return (
        dt_s,
        v_exit_ms * 3.6,
        v_min_ms * 3.6,
        v_max_ms * 3.6,
        v_avg_ms * 3.6
    )


def main():
    print("="*100)
    print("UNIVERSAL MOTOR TEST — MONZA QUALIFYING")
    print("="*100)
    print()
    print(f"Setup:")
    print(f"  Circuit: Monza (it-1922_monza)")
    print(f"  Team: McLaren F1 Team")
    print(f"  Driver: Lando Norris (UK, age 25, #4)")
    print(f"  Session: Qualifying (push=10, min_fuel, QUALIFY maps)")
    print(f"  Aero: Ultra-low downforce (FW=31, RW=21, CLA≈2.90, CDA≈0.90)")
    print()

    # Carica telemetria e waypoints
    telemetry = load_monza_telemetry()
    waypoints = load_monza_waypoints()

    if not telemetry:
        print("❌ Telemetria Monza non trovata")
        return

    if not waypoints:
        print("❌ Waypoints HD Monza non trovati")
        return

    print(f"✓ Loaded telemetry with {len(telemetry.get('geometry', {}).get('sections', []))} sections")
    print(f"✓ Loaded {len(waypoints)} HD waypoints")
    print()

    # Estrai sezioni macro dalla telemetria
    sections_data = telemetry.get('geometry', {}).get('sections', [])

    # Crea setup e car state
    aero_setup = create_monza_aero_setup()
    car_state = CarState(
        car_id="mclaren_norris",
        team_code="MCL",
        current_section_idx=0,
        section_progress=0.0,
        lap_time_acc_s=0.0,
        lap_number=1,
        v_current_ms=0.0,
    )

    env = EnvContext(
        air_temp_c=28.0,
        track_temp_c=42.0,
        air_density_kg_m3=1.225,
        wind_speed_kph=2.0,
        wind_direction_deg=45.0,
    )

    # Simula il giro
    print("[SIMULATION] Running Monza lap simulation...")
    print("-"*100)

    total_dt_real = 0.0
    total_dt_sim = 0.0
    reports = []

    v_current = 0.0

    for idx, section_data in enumerate(sections_data[:13]):  # Primi 13 settori (3 principali + dettagli)
        section_id = section_data.get('section_id', f'S{idx}')
        section_name = section_data.get('name', f'Section {idx}')
        kind = section_data.get('kind', 'STRAIGHT')
        length_m = section_data.get('length_m', 100)

        v_entry_kph = section_data.get('v_entry_kph', 200.0)
        v_exit_kph = section_data.get('v_exit_kph', 200.0)
        v_min_kph = section_data.get('v_min_kph', v_entry_kph)
        v_max_kph = section_data.get('v_max_kph', v_exit_kph)
        v_avg_kph = section_data.get('v_avg_kph', (v_entry_kph + v_exit_kph) / 2)
        dt_real = section_data.get('dt_ref_s', 0.0)

        # Crea SectionContext
        section = SectionContext(
            section_id=section_id,
            name=section_name,
            kind=kind,
            length_m=length_m,
            v_base_kph=v_avg_kph,
            v_entry_kph=v_entry_kph,
            v_exit_kph=v_exit_kph,
            v_min_kph=v_min_kph,
            v_max_kph=v_max_kph,
        )

        # Simula
        dt_sim, v_exit_sim, v_min_sim, v_max_sim, v_avg_sim = simulate_section(
            section=section,
            v_entry_kph=v_entry_kph,
            aero_setup=aero_setup,
            env=env,
            mass_kg=803.0,  # 798 + 5kg fuel
        )

        # Calcola errori
        dv_entry_error = 0.0  # Entry è dato
        dv_exit_error = v_exit_sim - v_exit_kph
        dv_avg_error = v_avg_sim - v_avg_kph
        dt_error = dt_sim - dt_real
        dt_error_pct = (dt_error / dt_real * 100) if dt_real > 0 else 0.0

        # Calcola accelerazioni
        if dt_real > 0:
            dv_real_ms = (v_exit_kph - v_entry_kph) / 3.6
            a_mean_real = dv_real_ms / dt_real / 9.81
        else:
            a_mean_real = 0.0

        if dt_sim > 0:
            dv_sim_ms = (v_exit_sim - v_entry_kph) / 3.6
            a_mean_sim = dv_sim_ms / dt_sim / 9.81
        else:
            a_mean_sim = 0.0

        # Grip (placeholder)
        radius_m = section_data.get('radius_m', 0) or 0
        if radius_m and radius_m > 100:
            grip_available = 1.70  # C3 grip base
            grip_util_real = (v_min_kph / 3.6) ** 2 / (radius_m * 9.81) if radius_m > 0 else 0
            grip_util_sim = (v_min_sim / 3.6) ** 2 / (radius_m * 9.81) if radius_m > 0 else 0
        else:
            grip_available = 0.0
            grip_util_real = 0.0
            grip_util_sim = 0.0

        report = SectorReport(
            sector_id=section_id,
            sector_name=section_name,
            v_entry_real=v_entry_kph,
            v_entry_sim=v_entry_kph,  # Entry match
            v_exit_real=v_exit_kph,
            v_exit_sim=v_exit_sim,
            v_min_real=v_min_kph,
            v_min_sim=v_min_sim,
            v_max_real=v_max_kph,
            v_max_sim=v_max_sim,
            v_avg_real=v_avg_kph,
            v_avg_sim=v_avg_sim,
            dt_real=dt_real,
            dt_sim=dt_sim,
            a_mean_real=a_mean_real,
            a_mean_sim=a_mean_sim,
            a_lat_real=0.0,
            a_lat_sim=0.0,
            radius_m=radius_m,
            grip_available=grip_available,
            grip_utilized_real=grip_util_real,
            grip_utilized_sim=grip_util_sim,
            dv_entry_error=dv_entry_error,
            dv_exit_error=dv_exit_error,
            dv_avg_error=dv_avg_error,
            dt_error=dt_error,
            dt_error_pct=dt_error_pct,
        )
        reports.append(report)

        total_dt_real += dt_real
        total_dt_sim += dt_sim

    # Stampa risultati dettagliati
    print("\n[SECTOR-BY-SECTOR COMPARISON]")
    print("="*100)
    print()

    print(f"{'Sector':<20} {'Kind':<12} {'Real(s)':<10} {'Sim(s)':<10} {'Δt(s)':<10} {'Error%':<10}")
    print("-"*100)

    for report in reports:
        print(
            f"{report.sector_name:<20} "
            f"{' ':<12} "
            f"{report.dt_real:<10.3f} "
            f"{report.dt_sim:<10.3f} "
            f"{report.dt_error:<10.3f} "
            f"{report.dt_error_pct:<10.1f}%"
        )

    print()
    print("[VELOCITY ANALYSIS]")
    print("="*100)
    print()

    print(f"{'Sector':<20} {'v_entry(k)':<12} {'v_min(k)':<12} {'v_max(k)':<12} {'v_avg(k)':<12} {'v_avg_err':<12}")
    print("-"*100)

    for report in reports:
        print(
            f"{report.sector_name:<20} "
            f"{report.v_entry_real:<12.1f} "
            f"{report.v_min_sim:<12.1f} "
            f"{report.v_max_sim:<12.1f} "
            f"{report.v_avg_sim:<12.1f} "
            f"{report.dv_avg_error:<12.1f}"
        )

    print()
    print("[ACCELERATION ANALYSIS]")
    print("="*100)
    print()

    print(f"{'Sector':<20} {'a_mean_real(g)':<18} {'a_mean_sim(g)':<18} {'Δa(g)':<12}")
    print("-"*100)

    for report in reports:
        da = report.a_mean_sim - report.a_mean_real
        print(
            f"{report.sector_name:<20} "
            f"{report.a_mean_real:<18.4f} "
            f"{report.a_mean_sim:<18.4f} "
            f"{da:<12.4f}"
        )

    print()
    print("[LAP TIME SUMMARY]")
    print("="*100)
    print()
    print(f"Total time (Real):       {total_dt_real:.3f} s")
    print(f"Total time (Simulated):  {total_dt_sim:.3f} s")
    print(f"Difference:              {total_dt_sim - total_dt_real:.3f} s")
    print(f"Error %:                 {(total_dt_sim - total_dt_real) / total_dt_real * 100:.2f}%")
    print()

    print("✓ Test completed")


if __name__ == "__main__":
    main()
