"""
DEBUG: Apex Speed Calculation for Problem Turns (Turn 1, Turn 3)

Verifica:
1. Quale v_apex viene calcolato per ogni curva
2. Quale dovrebbe essere basato su telemetria reale
3. Perché Turn 1 frena troppo e Turn 3 non frena abbastanza
"""

import json
import os
import sys
from typing import Dict, Any, Optional, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lap_simulator.data_types import (
    CarState, AeroSetup, DriverSkills, SectionContext, EnvContext,
    CircuitConfig, WheelPosition, TyreCompound, TyreState,
    EngineMapName, ERSModeName, SectionKind, CurveProfile
)
from lap_simulator.physics_v3.update_section_v3 import update_section_v3
from lap_simulator.physics_v3.aero_mapper import map_aero_setup
from lap_simulator.physics_v3.balance_model import compute_balance
from lap_simulator.physics_v3.corner_solver import solve_corner_apex_speed
from lap_simulator.config_loader import load_circuit_config


def debug_corner(
    section_idx: int,
    section_name: str,
    v_entry_real_kph: float,
    v_exit_real_kph: float,
    radius_m: float,
    length_m: float,
    car_state: CarState,
    aero_setup: AeroSetup,
    config: CircuitConfig,
    env: EnvContext,
):
    """Debug apex speed calculation per una curva."""

    print(f"\n{'='*100}")
    print(f"[SEZIONE {section_idx}: {section_name}]")
    print(f"{'='*100}")

    print(f"\n[DATI REALI]")
    print(f"  Radius: {radius_m:.1f} m")
    print(f"  Length: {length_m:.1f} m")
    print(f"  v_entry (real):  {v_entry_real_kph:.1f} kph")
    print(f"  v_exit (real):   {v_exit_real_kph:.1f} kph")
    print(f"  ΔV frenata (real): {v_entry_real_kph - v_exit_real_kph:.1f} kph")

    # Calcola v_apex atteso dalla telemetria
    # v_apex è il punto minimo della velocità in una curva
    # Approssimativamente: v_apex ~ v_exit (il punto di uscita è dove si riaccelera)
    # Per una stima approssimativa, usiamo la velocità minima telemetria
    v_apex_real_estimate = v_exit_real_kph  # Semplificazione
    print(f"  v_apex (real ~): {v_apex_real_estimate:.1f} kph (stima da v_exit)")

    print(f"\n[PARAMETRI SIMULAZIONE]")

    # Aero setup
    print(f"  Ride height F: {aero_setup.ride_height_front_mm:.1f} mm")
    print(f"  Ride height R: {aero_setup.ride_height_rear_mm:.1f} mm")

    # Map aero
    physics_aero = map_aero_setup(
        aero_setup=aero_setup,
        env=env,
        v_estimate_kph=250.0,  # Stima velocità media
        drs_active=False,
        config=config,
    )
    print(f"  CLA: {physics_aero.CLA:.3f} m²")
    print(f"  CDA: {physics_aero.CDA:.3f} m²")

    # Balance
    v_entry_ms = v_entry_real_kph / 3.6
    mass_kg = car_state.pu.fuel_kg + 798.0

    balance = compute_balance(
        mu_base=1.90,  # C5 SOFT base grip
        aero=physics_aero,
        aero_setup=aero_setup,
        v_ms=v_entry_ms,
        radius_m=radius_m,
        mass_kg=mass_kg,
        env=env,
        a_long_g=0.0,
    )

    print(f"\n[BALANCE STATE]")
    print(f"  μ_front_eff: {balance.mu_front_eff:.3f}")
    print(f"  μ_rear_eff:  {balance.mu_rear_eff:.3f}")
    print(f"  μ_eff (min): {min(balance.mu_front_eff, balance.mu_rear_eff):.3f}")
    print(f"  load_transfer_lat: {balance.load_transfer_lat:.1f} N")
    print(f"  load_transfer_long: {balance.load_transfer_long:.1f} N")
    print(f"  a_lat_g: {balance.a_lat_g:.2f} g")
    print(f"  a_long_g: {balance.a_long_g:.2f} g")

    # Calcola v_apex con corner solver
    mu_eff = min(balance.mu_front_eff, balance.mu_rear_eff)
    v_apex_sim_ms = solve_corner_apex_speed(
        radius_m=radius_m,
        aero=physics_aero,
        balance=balance,
        mass_kg=mass_kg,
        mu_base=1.90,
        env_rho=env.air_density_kg_m3,
        banking_deg=0.0,
    )
    v_apex_sim_kph = v_apex_sim_ms * 3.6

    print(f"\n[CORNER SOLVER CALCULATION]")
    print(f"  v_apex_sim: {v_apex_sim_kph:.1f} kph ({v_apex_sim_ms:.1f} m/s)")
    print(f"  v_apex_real (stima): {v_apex_real_estimate:.1f} kph")
    print(f"  ΔV_apex: {v_apex_sim_kph - v_apex_real_estimate:+.1f} kph")

    # Analiza il problema
    print(f"\n[ANALISI]")
    if abs(v_apex_sim_kph - v_apex_real_estimate) > 5:
        if v_apex_sim_kph > v_apex_real_estimate:
            print(f"  ⚠️ PROBLEMA: Apex troppo ALTO (sim={v_apex_sim_kph:.1f} vs real={v_apex_real_estimate:.1f})")
            print(f"     → Non frena abbastanza in curva")
            print(f"     → Cause possibili:")
            print(f"        1. μ_eff troppo basso ({mu_eff:.3f})")
            print(f"        2. CLA troppo basso ({physics_aero.CLA:.3f})")
            print(f"        3. Radius non corretto ({radius_m:.1f}m)")
        else:
            print(f"  ⚠️ PROBLEMA: Apex troppo BASSO (sim={v_apex_sim_kph:.1f} vs real={v_apex_real_estimate:.1f})")
            print(f"     → Frena troppo in curva")
            print(f"     → Cause possibili:")
            print(f"        1. μ_eff troppo alto ({mu_eff:.3f})")
            print(f"        2. CLA troppo alto ({physics_aero.CLA:.3f})")
            print(f"        3. Radius non corretto ({radius_m:.1f}m)")
    else:
        print(f"  ✓ Apex OK: differenza < 5 kph")

    # Calcoli ausiliari
    print(f"\n[FORMULA CORNER SOLVER]")
    A = mass_kg / radius_m - 0.5 * env.air_density_kg_m3 * physics_aero.CLA * mu_eff
    C = mu_eff * mass_kg * 9.81
    print(f"  A = m/R - 0.5*ρ*CLA*μ = {A:.2f}")
    print(f"  C = μ*m*g = {C:.2f}")
    if A > 0:
        print(f"  v_apex² = C/A = {C/A:.2f}")
        print(f"  v_apex = √(v_apex²) = {(C/A)**0.5:.1f} m/s")
    else:
        print(f"  ⚠️ A <= 0: usando fallback formula (senza downforce)")


def main():
    print("\n" + "="*100)
    print("DEBUG: Apex Speed Calculation — Problem Turns")
    print("="*100)

    # Load data
    config = load_circuit_config("it-1922_monza")
    if not config or not config.sections:
        print("❌ Circuit config non trovato")
        return

    # Setup
    driver_skills = DriverSkills(
        raw_pace=93, race_craft=93, aggression=86, consistency=94,
        tyre_management=88, overtaking_skill=80, defending_skill=80,
        wet_skill=75, smoothness=88, setup_finding=85,
    )

    aero_setup = AeroSetup()
    aero_setup.ride_height_front_mm = 25.0
    aero_setup.ride_height_rear_mm = 40.0

    env = EnvContext(
        air_temp_c=28.0, track_temp_c=42.0,
        air_density_kg_m3=1.225, wind_speed_kph=2.0,
    )

    car_state = CarState(
        car_id="mclaren_norris",
        team_code="MCL",
        lap_number=3,
        v_current_ms=321.6 / 3.6,
    )

    for pos in WheelPosition:
        car_state.tyres[pos] = TyreState(
            wheel_pos=pos, compound=TyreCompound.C5,
            surface_temp_c=118.0, core_temp_c=115.0, wear_pct=2.0,
        )

    car_state.brakes.temp_front_c = 650.0
    car_state.brakes.temp_rear_c = 620.0
    car_state.pu.active_map = EngineMapName.QUALIFY
    car_state.pu.ers_mode = ERSModeName.QUALIFY
    car_state.pu.ice_power_kw = 950.0
    car_state.pu.ers_output_kw = 160.0
    car_state.pu.ers_energy_mj = 4.0
    car_state.pu.fuel_kg = 12.0

    # Carica dati telemetria
    telemetry_sections = None
    paths_to_try = [
        "python_backend/data/circuits/2025/it-1922_monza_Telemetry.json",
        "data/circuits/2025/it-1922_monza_Telemetry.json",
    ]
    for path in paths_to_try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                telemetry_sections = data.get('geometry', {}).get('sections', [])
                break

    if not telemetry_sections:
        print("❌ Telemetria non trovata")
        return

    # DEBUG TURN 1 (index 1)
    debug_corner(
        section_idx=1,
        section_name="Turn 1",
        v_entry_real_kph=347.0,
        v_exit_real_kph=108.0,
        radius_m=config.sections[1].curve_profile.radius_m,
        length_m=config.sections[1].length_m,
        car_state=car_state,
        aero_setup=aero_setup,
        config=config,
        env=env,
    )

    # DEBUG TURN 3 (index 5)
    debug_corner(
        section_idx=5,
        section_name="Turn 3",
        v_entry_real_kph=253.0,
        v_exit_real_kph=208.0,
        radius_m=config.sections[5].curve_profile.radius_m,
        length_m=config.sections[5].length_m,
        car_state=car_state,
        aero_setup=aero_setup,
        config=config,
        env=env,
    )

    # DEBUG TURN 4 (index 7)
    debug_corner(
        section_idx=7,
        section_name="Turn 4",
        v_entry_real_kph=201.4,
        v_exit_real_kph=196.4,
        radius_m=config.sections[7].curve_profile.radius_m,
        length_m=config.sections[7].length_m,
        car_state=car_state,
        aero_setup=aero_setup,
        config=config,
        env=env,
    )

    print("\n" + "="*100)
    print("✓ Debug completato")
    print("="*100)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    main()
