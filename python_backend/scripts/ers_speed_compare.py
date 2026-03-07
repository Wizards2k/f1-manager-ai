#!/usr/bin/env python3
"""Quick comparison of lap pace with ERS enabled vs disabled.

This script runs the LapSimulator twice on the same circuit setup:
1. Baseline – the circuit config is used as-is (ERS enabled)
2. ERS Off – the selected engine map is cloned with zero ERS output

For each run it reports lap time, total deploy/harvest usage and the
per-section effective speed delta to highlight the impact of ERS.

Usage:
    PYTHONPATH=python_backend python3 python_backend/scripts/ers_speed_compare.py \
        --circuit it-1922_monza --map RACE
"""
from __future__ import annotations

import argparse
import copy
from statistics import mean

from lap_simulator.config_loader import load_circuit_config
from lap_simulator.data_types import (
    AeroComponent,
    AeroSetup,
    CarState,
    DriverSkills,
    EngineMapName,
    EnvContext,
    SuspensionState,
    TyreCompound,
)
from lap_simulator.lap_simulator import CarEntry, LapSimulator


FABRIC_TYRE_COMPOUND = TyreCompound.C4
DEFAULT_FUEL_KG = 80.0
CAR_ID = "test_car"


def build_aero_setup() -> AeroSetup:
    """Return a baseline aero setup similar to integration tests."""
    return AeroSetup(
        front_wing=AeroComponent(
            name="front_wing",
            base_downforce=30.0,
            base_drag=8.0,
            angle_deg=14.0,
            angle_ref_deg=15.0,
            drs_drag_reduction=0.15,
        ),
        rear_wing=AeroComponent(
            name="rear_wing",
            base_downforce=28.0,
            base_drag=10.0,
            angle_deg=12.0,
            angle_ref_deg=15.0,
            drs_drag_reduction=0.20,
        ),
        beam_wing=AeroComponent(
            name="beam_wing",
            base_downforce=5.0,
            base_drag=2.5,
            angle_deg=8.0,
            angle_ref_deg=10.0,
        ),
        front_floor=AeroComponent(
            name="front_floor",
            base_downforce=12.0,
            base_drag=2.0,
        ),
        rear_floor=AeroComponent(
            name="rear_floor",
            base_downforce=12.0,
            base_drag=2.0,
        ),
        sidepods=AeroComponent(
            name="sidepods",
            base_downforce=4.0,
            base_drag=3.0,
            cooling_contribution=45.0,
        ),
        engine_cover=AeroComponent(
            name="engine_cover",
            base_downforce=2.0,
            base_drag=1.0,
            cooling_contribution=18.0,
        ),
        b_wing=AeroComponent(name="b_wing", base_downforce=3.0, base_drag=1.5),
        suspension_front=SuspensionState(rigidity=0.55, efficiency=0.80),
        suspension_rear=SuspensionState(rigidity=0.55, efficiency=0.80),
        ride_height_front_mm=35.0,
        ride_height_rear_mm=48.0,
        ride_height_optimal_front_mm=35.0,
        ride_height_optimal_rear_mm=48.0,
    )


def build_driver_skills() -> DriverSkills:
    return DriverSkills(
        raw_pace=85,
        race_craft=80,
        aggression=55,
        consistency=82,
        tyre_management=75,
        overtaking_skill=70,
        defending_skill=65,
        wet_skill=70,
        smoothness=72,
        setup_finding=68,
    )


def build_car_state() -> CarState:
    state = CarState(car_id=CAR_ID)
    state.pu.fuel_kg = DEFAULT_FUEL_KG
    state.pu.active_map = EngineMapName.RACE
    for tyre in state.tyres.values():
        tyre.compound = FABRIC_TYRE_COMPOUND
        tyre.surface_temp_c = 95.0
        tyre.core_temp_c = 85.0
    return state


def clone_config_with_ers_disabled(config, map_name: EngineMapName) -> object:
    """Deep-copy the circuit config and zero ERS capability for the map."""
    clone = copy.deepcopy(config)
    map_params = clone.pu_maps.get(map_name)
    if map_params:
        map_params.ers_output_kw = 0.0
        map_params.mguh_power_kw = 0.0
        map_params.mguh_direct_ratio = 0.0
    clone.ers_budget.setdefault("maps", {})
    clone.ers_budget["maps"].setdefault(map_name.value, {})
    clone.ers_budget["maps"][map_name.value].update({
        "deploy_mj_per_lap": 0.0,
        "mguh_direct_mj_per_lap": 0.0,
        "bucket_primary_pct": 1.0,
        "bucket_secondary_pct": 0.0,
        "bucket_exit_pct": 0.0,
        "defense_reserve_mj": 0.0,
        "target_soc_end_lap": 0.0,
    })
    return clone


def run_single_lap(config, env) -> tuple:
    aero = build_aero_setup()
    driver = build_driver_skills()
    car_state = build_car_state()
    entry = CarEntry(
        car_id=CAR_ID,
        state=car_state,
        aero_setup=aero,
        driver_skills=driver,
        push_level=1.0,
    )
    sim = LapSimulator(config, env)
    sim.register_car(entry)
    results = sim.run_lap()
    lap = results[CAR_ID]
    pu_state = entry.state.pu
    return lap, pu_state


def summarize_speeds(sections, lap_with, lap_without):
    rows = []
    for section, sr_on, sr_off in zip(sections, lap_with.section_results, lap_without.section_results):
        rows.append({
            "section": section.name or section.section_id,
            "kind": section.kind.value,
            "speed_on": sr_on.v_effective_kph,
            "speed_off": sr_off.v_effective_kph,
            "delta": sr_on.v_effective_kph - sr_off.v_effective_kph,
        })
    return rows


def format_rows(rows):
    lines = ["Section                       Kind        ERS ON   ERS OFF   Δ v_eff"]
    for row in rows:
        lines.append(
            f"{row['section'][:27]:<27}  {row['kind']:<10}  "
            f"{row['speed_on']:7.1f}  {row['speed_off']:7.1f}  {row['delta']:7.1f}"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Compare lap pace with/without ERS deploy")
    parser.add_argument("--circuit", default="it-1922_monza", help="Circuit telemetry ID (default: it-1922_monza)")
    parser.add_argument("--map", default="RACE", help="Engine map to evaluate (default: RACE)")
    args = parser.parse_args()

    map_name = EngineMapName[args.map.upper()]
    config = load_circuit_config(args.circuit)
    env = EnvContext(air_temp_c=25.0, track_temp_c=35.0)

    lap_on, pu_on = run_single_lap(config, env)
    config_off = clone_config_with_ers_disabled(config, map_name)
    lap_off, pu_off = run_single_lap(config_off, env)

    print("== ERS Comparison ==")
    print(f"Circuit: {config.circuit_name or config.circuit_id}")
    print(f"Map: {map_name.value}")
    print()
    print("Lap times:")
    print(f"  ERS ON : {lap_on.lap_time_s:7.3f} s")
    print(f"  ERS OFF: {lap_off.lap_time_s:7.3f} s")
    print(f"  Delta  : {lap_on.lap_time_s - lap_off.lap_time_s:+7.3f} s")
    print()
    avg_on = mean(sr.v_effective_kph for sr in lap_on.section_results)
    avg_off = mean(sr.v_effective_kph for sr in lap_off.section_results)
    top_on = max(sr.v_exit_kph for sr in lap_on.section_results)
    top_off = max(sr.v_exit_kph for sr in lap_off.section_results)
    print("Speed summary:")
    print(f"  Avg v_eff   : {avg_on:6.2f} kph (ERS ON) | {avg_off:6.2f} kph (ERS OFF) | Δ {avg_on - avg_off:+5.2f} kph")
    print(f"  Peak v_exit : {top_on:6.2f} kph (ERS ON) | {top_off:6.2f} kph (ERS OFF) | Δ {top_on - top_off:+5.2f} kph")
    print()
    print("Energy usage per lap:")
    print(f"  Deploy used : {pu_on.lap_deploy_mj:4.2f} MJ (ERS ON) | {pu_off.lap_deploy_mj:4.2f} MJ (ERS OFF)")
    print(f"  MGU-H direct: {pu_on.lap_mguh_direct_mj:4.2f} MJ (ERS ON) | {pu_off.lap_mguh_direct_mj:4.2f} MJ (ERS OFF)")
    print()
    rows = summarize_speeds(config.sections, lap_on, lap_off)
    print(format_rows(rows))


if __name__ == "__main__":
    main()
