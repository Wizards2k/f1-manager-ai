#!/usr/bin/env python3
import argparse
import sys
import json
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Dict, List

sys.path.append(str(Path(__file__).resolve().parent.parent / "python_backend"))

from lap_simulator import power_unit as lap_power_unit
from lap_simulator.lap_simulator import LapSimulator, CarEntry
from lap_simulator.data_types import (
    CarState, EnvContext, AeroSetup, DriverSkills, TyreCompound, TyreState, WheelPosition
)
from lap_simulator.config_loader import load_circuit_config

# Import sandbox data
from tmp_data.power_units_2025 import POWER_UNITS_2025
from tmp_data.cars_2025 import CARS_2025
from tmp_data.teams_2025 import TEAMS_2025

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
    "RBRB": 6.8,
}

ENGINE_SUPPLIER_BY_TEAM = {
    "MCL": "Mercedes",
    "MER": "Mercedes",
    "WIL": "Mercedes",
    "AST": "Mercedes",
    "RBR": "Red Bull",
    "RBRB": "Red Bull",
    "FER": "Ferrari",
    "HAAS": "Ferrari",
    "SAU": "Ferrari",
    "ALP": "Renault",
}

ENGINE_PENALTIES = {
    "Mercedes": 0.0,
    "Red Bull": 0.01,
    "Ferrari": 0.015,
    "Renault": 0.03,
}

BASE_ICE_POWER_KW = lap_power_unit.ICE_BASE_POWER_KW


@contextmanager
def override_ice_power(ice_kw: float):
    original = lap_power_unit.ICE_BASE_POWER_KW
    lap_power_unit.ICE_BASE_POWER_KW = ice_kw
    try:
        yield
    finally:
        lap_power_unit.ICE_BASE_POWER_KW = original


def _scale_power_unit_ers(pu, penalty: float):
    if penalty <= 0:
        return pu
    scaled = deepcopy(pu)
    for ers_map in scaled.ers_maps.values():
        ers_map.ers_output_kw *= (1.0 - penalty)
        ers_map.mguh_power_kw *= (1.0 - penalty)
        ers_map.deploy_budget_mj *= (1.0 - penalty)
    return scaled

def build_car_entry(team_code: str, circuit_id: str) -> CarEntry:
    """Build a CarEntry from sandbox team data for a given circuit."""
    team = TEAMS_2025[team_code]
    car = team.auto
    pu = team.power_unit
    pilot = team.pilota1  # Use primary driver for quali
    
    # CarState
    state = CarState(car_id=team_code)
    state.pu.fuel_kg = 2.5  # Quali fuel
    soft_compound = TyreCompound.C5 if circuit_id != "it-1922_monza" else TyreCompound.C4
    state.tyres = {wp: TyreState(wheel_pos=wp, compound=soft_compound) for wp in WheelPosition}
    for tyre in state.tyres.values():
        tyre.surface_temp_c = 100.0
        tyre.core_temp_c = 100.0
    
    state.ers_mode = "Deploy"
    
    # DriverSkills from pilot
    skills = DriverSkills(
        raw_pace=pilot.velocita,
        consistency=pilot.costanza,
        overtaking_skill=pilot.sorpasso
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
    
    # PUState from power unit (apply supplier penalties)
    supplier = ENGINE_SUPPLIER_BY_TEAM.get(team_code, "Mercedes")
    penalty = ENGINE_PENALTIES.get(supplier, 0.0)
    ice_power = BASE_ICE_POWER_KW * (1.0 - penalty)
    scaled_pu = _scale_power_unit_ers(pu, penalty)
    with override_ice_power(ice_power):
        pu_state, _ = scaled_pu.make_pu_state()
    state.pu = pu_state
    
    return CarEntry(car_id=team_code, state=state, aero_setup=aero, driver_skills=skills, push_level=1.0)

def get_baseline_mclaren_entry(circuit_id: str) -> CarEntry:
    """Return the exact baseline entry used in physics_validator.py for McLaren."""
    state = CarState(car_id="MCL")
    state.pu.fuel_kg = 2.5
    soft_compound = TyreCompound.C5 if circuit_id != "it-1922_monza" else TyreCompound.C4
    state.tyres = {wp: TyreState(wheel_pos=wp, compound=soft_compound) for wp in WheelPosition}
    for tyre in state.tyres.values():
        tyre.surface_temp_c = 100.0
        tyre.core_temp_c = 100.0
    
    state.ers_mode = "Deploy"
    skills = DriverSkills(raw_pace=100, consistency=95, overtaking_skill=90)
    
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
    
    return CarEntry(car_id="MCL", state=state, aero_setup=aero, driver_skills=skills, push_level=1.0)

def run_teams_simulation(circuit_id: str = "gb-1948_silverstone_HD"):
    """Run quali simulation for all 10 sandbox teams on given circuit."""
    config = load_circuit_config(circuit_id, 2025)
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
            entry = build_car_entry(team_code, circuit_id)
        
        sim = LapSimulator(config, env)
        sim.register_car(entry)
        result = sim.run_lap()[team_code]
        
        # Store results
        results[team_code] = {
            "team_name": TEAMS_2025[team_code].nome_scuderia,
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
    args = parser.parse_args()
    
    run_teams_simulation(args.circuit)
