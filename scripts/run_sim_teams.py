#!/usr/bin/env python3
import argparse
import sys
import json
from pathlib import Path
from typing import Dict, List

sys.path.append(str(Path(__file__).resolve().parent.parent / "python_backend"))

from lap_simulator.lap_simulator import LapSimulator, CarEntry
from lap_simulator.data_types import (
    CarState,
    EnvContext,
    AeroSetup,
    DriverSkills,
    EngineMapName,
    TyreCompound,
    TyreState,
    WheelPosition,
)
from models.auto_models import Auto
from lap_simulator.config_loader import load_circuit_config

from data.teams import TEAMS

TEAM_BY_CODE = {team.sigla_scuderia: team for team in TEAMS}

# Expected gaps from sandbox (baseline McLaren)
EXPECTED_GAPS = {
    "MCL": 0.0,
    "RBR": 0.8,
    "FER": 1.2,
    "MER": 1.8,
    "AST": 2.5,
    "ALP": 3.2,
    "HAAS": 4.1,
    "WIL": 4.8,
    "SAU": 5.5,
    "RB": 6.8,
}

def _total_df(auto: Auto) -> float:
    pkg = auto.aero_package
    return sum(
        [
            pkg.ala_anteriore.df_coeff,
            pkg.ala_posteriore.df_coeff,
            pkg.fondo_anteriore.df_coeff,
            pkg.fondo_posteriore.df_coeff,
        ]
    ) * 1000


def _total_grip(auto: Auto) -> float:
    return auto.grip_base or 1.0


baseline_auto = TEAM_BY_CODE["MCL"].auto
BASELINE_DF = _total_df(baseline_auto)
BASELINE_GRIP = _total_grip(baseline_auto)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _penalty_shares(delta_aero: float, delta_grip: float) -> tuple[float, float]:
    total = abs(delta_aero) + abs(delta_grip)
    if total < 1e-4:
        return 0.6, 0.4
    return abs(delta_aero) / total, abs(delta_grip) / total


def build_car_entry(team_code: str, circuit_id: str, config) -> CarEntry:
    """Build a CarEntry from official team registry for a given circuit."""
    team = TEAM_BY_CODE[team_code]
    car = team.auto
    pu = team.power_unit
    pilot = team.pilota1  # Use primary driver for quali
    
    # CarState
    state = CarState(car_id=team_code)
    state.pu = pu.create_state(fuel_kg=2.5, map_name=EngineMapName.QUALY)
    soft_compound = TyreCompound.C3 if circuit_id != "it-1922_monza" else TyreCompound.C3
    state.tyres = {wp: TyreState(wheel_pos=wp, compound=soft_compound) for wp in WheelPosition}
    for tyre in state.tyres.values():
        tyre.surface_temp_c = 100.0
        tyre.core_temp_c = 100.0
    
    state.ers_mode = "Deploy"
    
    # DriverSkills from pilot
    skills = DriverSkills(
        raw_pace=pilot.velocita,
        race_craft=pilot.gara,
        consistency=pilot.costanza,
        aggression=pilot.aggressivita,
        tyre_management=pilot.consumo_gomme,
        overtaking_skill=pilot.velocita,
        defending_skill=pilot.gestione_carburante,
        wet_skill=pilot.ricerca_assetto,
        smoothness=pilot.stile_sottosterzo,
        setup_finding=pilot.perfezionismo
    )
    
    # AeroSetup from car
    aero = AeroSetup()
    aero_pkg = car.aero_package
    aero.front_wing.base_downforce = aero_pkg.ala_anteriore.df_coeff
    aero.front_wing.base_drag = aero_pkg.ala_anteriore.drag_coeff
    aero.rear_wing.base_downforce = aero_pkg.ala_posteriore.df_coeff
    aero.rear_wing.base_drag = aero_pkg.ala_posteriore.drag_coeff
    aero.front_floor.base_downforce = aero_pkg.fondo_anteriore.df_coeff
    aero.front_floor.base_drag = aero_pkg.fondo_anteriore.drag_coeff
    aero.rear_floor.base_downforce = aero_pkg.fondo_posteriore.df_coeff
    aero.rear_floor.base_drag = aero_pkg.fondo_posteriore.drag_coeff
    aero.front_wing.angle_deg = aero_pkg.ala_anteriore.angolo_inclinazione
    aero.rear_wing.angle_deg = aero_pkg.ala_posteriore.angolo_inclinazione
    
    car_df = _total_df(car)
    car_grip = _total_grip(car)
    physical_delta_aero = _clamp((BASELINE_DF - car_df) / BASELINE_DF, -0.03, 0.03)
    physical_delta_grip = _clamp((BASELINE_GRIP - car_grip) / BASELINE_GRIP, -0.05, 0.05)

    target_penalty = EXPECTED_GAPS.get(team_code, 0.0) / 100.0
    aero_share, grip_share = _penalty_shares(physical_delta_aero, physical_delta_grip)
    max_delta = 4.0

    delta_aero = (target_penalty * aero_share) / (config.k_aero_penalty or 1.0)
    delta_grip = (target_penalty * grip_share) / (config.k_grip_penalty or 1.0)

    delta_aero = _clamp(delta_aero, -max_delta, max_delta)
    delta_grip = _clamp(delta_grip, -max_delta, max_delta)

    return CarEntry(
        car_id=team_code,
        state=state,
        aero_setup=aero,
        driver_skills=skills,
        push_level=1.0,
        delta_aero=delta_aero,
        delta_grip=delta_grip,
    )

def get_baseline_mclaren_entry(circuit_id: str) -> CarEntry:
    """Return the exact baseline entry used in physics_validator.py for McLaren."""
    state = CarState(car_id="MCL")
    state.pu = TEAM_BY_CODE["MCL"].power_unit.create_state(fuel_kg=2.5, map_name=EngineMapName.QUALY)
    soft_compound = TyreCompound.C3 if circuit_id != "it-1922_monza" else TyreCompound.C3
    state.tyres = {wp: TyreState(wheel_pos=wp, compound=soft_compound) for wp in WheelPosition}
    for tyre in state.tyres.values():
        tyre.surface_temp_c = 100.0
        tyre.core_temp_c = 100.0
    
    state.ers_mode = "Deploy"
    skills = DriverSkills(
        raw_pace=100,
        race_craft=95,
        consistency=95,
        aggression=80,
        tyre_management=85,
        overtaking_skill=90,
        defending_skill=85,
        wet_skill=80,
        smoothness=85,
        setup_finding=80
    )
    
    aero = AeroSetup()
    aero.front_wing.base_downforce = 12.0
    aero.front_wing.base_drag = 5.0
    aero.rear_wing.base_downforce = 12.0
    aero.rear_wing.base_drag = 8.0
    aero.front_floor.base_downforce = 15.0
    aero.front_floor.base_drag = 5.0
    aero.rear_floor.base_downforce = 15.0
    aero.rear_floor.base_drag = 5.0
    aero.front_wing.angle_deg = 10.0
    aero.rear_wing.angle_deg = 10.0
    
    state.pu = TEAM_BY_CODE["MCL"].power_unit.create_state(fuel_kg=2.5, map_name=EngineMapName.QUALY)

    return CarEntry(car_id="MCL", state=state, aero_setup=aero, driver_skills=skills, push_level=1.0, apply_baseline_delta=False)

def _resolve_circuit_id(circuit_id: str) -> str:
    return circuit_id[:-3] if circuit_id.endswith("_HD") else circuit_id


def run_teams_simulation(circuit_id: str = "gb-1948_silverstone_HD", zero_baseline_delta: bool = False):
    """Run quali simulation for all 10 sandbox teams on given circuit."""
    phys_id = _resolve_circuit_id(circuit_id)
    config = load_circuit_config(phys_id, 2025)
    if zero_baseline_delta:
        config.baseline_delta = 0.0
    ref_time = sum(s.dt_ref_s for s in config.sections)
    
    env = EnvContext(air_temp_c=25.0, track_temp_c=35.0)
    
    results = {}
    
    print(f"\n{'='*80}")
    print(f"TEAM SIMULATION: {config.circuit_name} ({circuit_id})")
    print(f"{'='*80}")
    
    # Simulate each team sequentially (no battles)
    for team_code in sorted(EXPECTED_GAPS.keys()):
        # Use baseline for McLaren to match reference pole times
        if team_code == "MCL":
            entry = get_baseline_mclaren_entry(circuit_id)
        else:
            entry = build_car_entry(team_code, circuit_id, config)
        
        sim = LapSimulator(config, env)
        sim.register_car(entry)
        result = sim.run_lap()[team_code]
        
        # Store results
        results[team_code] = {
            "team_name": TEAM_BY_CODE[team_code].nome_scuderia,
            "lap_time_s": result.lap_time_s,
            "section_times": [sr.dt_s for sr in result.section_results],
            "expected_gap_pct": EXPECTED_GAPS[team_code],
        }
    
    # Compute simulated gaps vs McLaren
    mclaren_time = results["MCL"]["lap_time_s"]
    for team_code, data in results.items():
        gap_s = data["lap_time_s"] - mclaren_time
        gap_pct = (gap_s / mclaren_time) * 100
        data["simulated_gap_s"] = gap_s
        data["simulated_gap_pct"] = gap_pct
    
    # Sort by lap time (best first)
    sorted_teams = sorted(results.items(), key=lambda kv: kv[1]["lap_time_s"])
    
    # Print table
    print(f"{'POS':>3} | {'TEAM':<12} | {'LAP_TIME':>9} | {'EXP_GAP':>9} | {'SIM_GAP':>9} | {'Δ%':>6}")
    print("-" * 70)
    for pos, (team_code, data) in enumerate(sorted_teams, start=1):
        print(f"{pos:3d} | {team_code:<12} | {data['lap_time_s']:9.3f} | {data['expected_gap_pct']:>+8.2f}% | {data['simulated_gap_pct']:>+8.2f}% | {data['simulated_gap_pct'] - data['expected_gap_pct']:+6.2f}%")
    
    # Save results for HTML report
    out_path = Path("reports")
    out_path.mkdir(exist_ok=True)
    with open(out_path / f"team_simulation_{circuit_id}.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {out_path / f'team_simulation_{circuit_id}.json'}")
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate 10 sandbox teams on a circuit")
    parser.add_argument("--circuit", default="gb-1948_silverstone_HD", help="Circuit ID (default: Silverstone HD)")
    parser.add_argument("--zero-baseline-delta", action="store_true", help="Disable the global baseline delta so reference laps stay at telemetry times")
    args = parser.parse_args()
    run_teams_simulation(args.circuit, zero_baseline_delta=args.zero_baseline_delta)
