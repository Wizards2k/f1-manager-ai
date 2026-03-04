#!/usr/bin/env python3
"""Script di validazione per tyre penalties su Suzuka - versione semplificata."""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "python_backend"))

from python_backend.lap_simulator.config_loader import load_circuit_config
from python_backend.lap_simulator.update_section import update_section
from python_backend.lap_simulator.data_types import (
    CircuitConfig, EnvContext, CarState, PUState, TyreState, 
    TyreCompound, WheelPosition, SectionContext, AeroSetup, DriverSkills
)


def main():
    # Load circuit config
    circuit_id = "jp-1962_suzuka"
    config = load_circuit_config(circuit_id, 2025)
    
    # Setup base conditions
    env = EnvContext(
        air_temp_c=25.0,
        track_temp_c=35.0,
        wind_speed_kph=5.0,
        wind_direction_deg=0.0,
        air_density_kg_m3=1.2,
        track_rubber_level=1.0
    )
    
    print(f"Validazione tyre penalties - {circuit_id}")
    print(f"Reference compound: {config.tyre_reference_compound}")
    print(f"Fuel reference: {config.fuel_reference_kg}kg")
    print("=" * 80)
    
    # Test compounds and wear levels
    compounds = ["C1", "C2", "C3", "C4", "C5", "C6"]
    wear_levels = [0, 10, 30, 50, 70, 90]
    
    print(f"{'Compound':<10} {'Wear':<6} {'Lap Time':<10} {'Delta vs Ref'}")
    print("-" * 50)
    
    reference_time = None
    
    for compound in compounds:
        for wear in wear_levels:
            # Create car state
            car_state = CarState(
                car_id="test_car",
                lap_time_acc_s=0.0,
                current_section_idx=0,
                lap_number=1,
                pu=PUState(
                    fuel_kg=10.0,  # Reference fuel
                    ers_energy_mj=4.0,
                    active_map="STANDARD"
                ),
                tyres={
                    pos: TyreState(
                        wheel_pos=pos,
                        compound=TyreCompound(compound),
                        wear_pct=wear,
                        surface_temp_c=90.0,
                        core_temp_c=80.0,
                        lap_age=0
                    ) for pos in WheelPosition
                }
            )
            
            # Create driver skills (neutral)
            driver_skills = DriverSkills(
                raw_pace=70,
                race_craft=70,
                aggression=50,
                consistency=70,
                tyre_management=70,
                overtaking_skill=60,
                defending_skill=60,
                wet_skill=60,
                smoothness=60,
                setup_finding=60
            )
            
            # Create neutral aero setup
            aero_setup = AeroSetup()
            
            # Debug: print compound delta for first iteration
            if compound == "C1" and wear == 0:
                print(f"\nDEBUG C1: compound_delta = {config.tyre_compound_deltas.get('C1', 0.0)}")
                print(f"DEBUG C3: compound_delta = {config.tyre_compound_deltas.get('C3', 0.0)}")
            
            # Simulate lap
            total_time = 0.0
            for section in config.sections:
                result = update_section(
                    car_state,
                    aero_setup,
                    driver_skills,
                    section,
                    env,
                    config,
                    push_level=1.0,
                    delta_aero=0.0,
                    delta_grip=0.0,
                    apply_baseline_delta=False  # Disable baseline for validation
                )
                
                total_time += result.dt_s
            
            lap_time = total_time
            
            # Store reference time (C3 at 0% wear should be ~87s)
            if compound == config.tyre_reference_compound and wear == 0:
                reference_time = lap_time
            
            # Calculate delta
            delta = ""
            if reference_time:
                delta_s = lap_time - reference_time
                if delta_s > 0:
                    delta = f"+{delta_s:.3f}s"
                else:
                    delta = f"{delta_s:.3f}s"
            
            print(f"{compound:<10} {wear:<6}% {lap_time:<10.3f} {delta}")
    
    print("=" * 80)
    if reference_time:
        print(f"Reference time ({config.tyre_reference_compound}, 0% wear): {reference_time:.3f}s")
        print(f"Target telemetry time: ~86.983s")
        print(f"Difference: {reference_time - 86.983:.3f}s")


if __name__ == "__main__":
    main()
