#!/usr/bin/env python3
import argparse
import sys
import json
from pathlib import Path
from typing import Optional

sys.path.append(str(Path(__file__).resolve().parent.parent / "python_backend"))

from lap_simulator.lap_simulator import LapSimulator, CarEntry
from lap_simulator.data_types import (
    CarState, EnvContext, AeroSetup, DriverSkills, TyreCompound, TyreState, WheelPosition
)
from lap_simulator.config_loader import load_circuit_config

def get_baseline_entry(circuit_id: str) -> CarEntry:
    state = CarState(car_id="BASE")
    state.pu.fuel_kg = 2.5
    soft_compound = TyreCompound.C4 if circuit_id == "it-1922_monza" else TyreCompound.C5
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
    
    return CarEntry(car_id="BASE", state=state, aero_setup=aero, driver_skills=skills, push_level=1.0)

def run_single(circuit_id: str, detailed: bool = True, sector_idx: Optional[int] = None):
    config = load_circuit_config(circuit_id, 2025)
    ref_time = sum(s.dt_ref_s for s in config.sections)
    
    env = EnvContext(air_temp_c=25.0, track_temp_c=35.0)
    sim = LapSimulator(config, env)
    sim.register_car(get_baseline_entry(circuit_id))
    
    result = sim.run_lap()["BASE"]
    
    if detailed:
        print(f"\n{'='*80}")
        print(f"CIRCUIT: {config.circuit_name} ({circuit_id})")
        print(f"SIMULATED: {result.lap_time_s:.3f}s | REFERENCE: {ref_time:.3f}s | DELTA: {result.lap_time_s - ref_time:+.3f}s")
        print(f"{'='*80}")
        print(f"{'ID':>2} | {'TYPE':<15} | {'LEN(m)':>7} | {'DT_SIM':>7} | {'DT_REF':>7} | {'DELTA':>7} | {'%':>7} | {'V_EFF':>7} | {'V_EXIT':>7}")
        print("-" * 88)
        
        tot_len = 0.0
        tot_sim = 0.0
        tot_ref = 0.0
        
        for i, sec_res in enumerate(result.section_results):
            sec = config.sections[i]
            dt = sec_res.dt_s
            ref_dt = sec.dt_ref_s
            delta = dt - ref_dt
            pct = (delta / ref_dt * 100) if ref_dt > 0 else 0.0
            
            tot_len += sec.length_m
            tot_sim += dt
            tot_ref += ref_dt
            
            print(f"{i:02d} | {sec.kind.name[:15]:<15} | {sec.length_m:7.1f} | {dt:7.3f} | {ref_dt:7.3f} | {delta:+7.3f} | {pct:+6.1f}% | {sec_res.v_effective_kph:7.1f} | {sec_res.v_exit_kph:7.1f}")
        
        tot_delta = tot_sim - tot_ref
        tot_pct = (tot_delta / tot_ref * 100) if tot_ref > 0 else 0.0
        
        print("-" * 88)
        print(f"   | {'TOTAL':<15} | {tot_len:7.1f} | {tot_sim:7.3f} | {tot_ref:7.3f} | {tot_delta:+7.3f} | {tot_pct:+6.1f}% |         |        ")
        print("-" * 88)

        print(f"\n{'='*100}")
        print("PER-SECTOR TELEMETRY vs SIMULATION")
        print("='*100")
        header = "ID | TYPE | LEN | DT_REF | DT_SIM | Δt | % | V_ENTRY_REF | V_ENTRY_SIM | V_MIN_REF | V_EFFECTIVE_SIM | V_EXIT_REF | V_EXIT_SIM | V_MAX_REF | V_MAX_SIM"
        print(header)
        print("-" * len(header))
        for i, sec_res in enumerate(result.section_results):
            sec = config.sections[i]
            dt = sec_res.dt_s
            ref_dt = sec.dt_ref_s
            delta = dt - ref_dt
            pct = (delta / ref_dt * 100) if ref_dt > 0 else 0.0
            v_entry_ref = sec.v_entry_kph
            v_entry_sim = sec_res.v_entry_kph
            v_min_ref = sec.v_min_kph
            v_max_ref = sec.v_max_kph
            v_exit_ref = sec.v_exit_kph
            v_exit_sim = sec_res.v_exit_kph
            v_effective_sim = sec_res.v_effective_kph
            v_max_sim = sec_res.v_max_kph

            print(f"{i:02d} | {sec.kind.name[:15]:<15} | {sec.length_m:5.1f} | {ref_dt:6.3f} | {dt:6.3f} | {delta:+5.3f} | {pct:+4.1f}% | {v_entry_ref:7.1f} | {v_entry_sim:7.1f} | {v_min_ref:7.1f} | {v_effective_sim:7.1f} | {v_exit_ref:7.1f} | {v_exit_sim:7.1f} | {v_max_ref:7.1f} | {v_max_sim:7.1f}")
        print("-" * len(header))
        if sector_idx is not None:
            sec = config.sections[sector_idx]
            sec_res = result.section_results[sector_idx]
            dt = sec_res.dt_s
            ref_dt = sec.dt_ref_s
            v_entry_ref = sec.v_entry_kph
            v_entry_sim = sec_res.v_entry_kph
            v_exit_ref = sec.v_exit_kph
            v_exit_sim = sec_res.v_exit_kph
            v_eff = sec_res.v_effective_kph
            delta = dt - ref_dt
            pct = (delta / ref_dt * 100) if ref_dt > 0 else 0.0
            print(f"\nDUMP SECTOR {sector_idx} | {sec.name} - {sec.kind.name}")
            print(" PARAMETRO         | TELEMETRY | SIMULAZIONE | DELTA")
            print("-------------------+-----------+-------------+---------")
            print(f" Tempo (s)         | {ref_dt:8.3f} | {dt:11.3f} | {delta:+6.3f}")
            print(f" V_entry (km/h)    | {v_entry_ref:8.1f} | {v_entry_sim:11.1f} | {v_entry_sim - v_entry_ref:+6.1f}")
            print(f" V_exit (km/h)     | {v_exit_ref:8.1f} | {v_exit_sim:11.1f} | {v_exit_sim - v_exit_ref:+6.1f}")
            print(f" V_effective (km/h)| {'N/A':>8} | {v_eff:11.1f} | {'N/A':>6}")
            print(f" Delta %           | {'N/A':>8} | {'N/A':>11} | {pct:+5.1f}%")
        else:
            delta = result.lap_time_s - ref_time
            print(f"{circuit_id:<25} | SIM: {result.lap_time_s:7.3f}s | REF: {ref_time:7.3f}s | DELTA: {delta:+7.3f}s")

def run_batch():
    manifest_path = Path("python_backend/data/circuits/2025/manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    print(f"\n{'='*70}")
    print(f"{'CIRCUIT ID':<25} | {'SIM (s)':>11} | {'REF (s)':>11} | {'DELTA (s)':>10}")
    print(f"{'='*70}")
    for cid in sorted(manifest.keys()):
        try:
            run_single(cid, detailed=False)
        except Exception as e:
            print(f"{cid:<25} | ERROR: {e}")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified Physics Validator")
    parser.add_argument("--circuit", help="Circuit ID to run detailed analysis on (e.g. mc-1929_monaco)")
    parser.add_argument("--sector", type=int, help="Run detailed output for a single sector index")
    parser.add_argument("--batch", action="store_true", help="Run all circuits in single-line summary mode")
    args = parser.parse_args()
    
    if args.batch:
        run_batch()
    elif args.circuit:
        run_single(args.circuit, detailed=True, sector_idx=args.sector)
    else:
        parser.print_help()
