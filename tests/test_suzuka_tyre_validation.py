#!/usr/bin/env python3
"""Script di validazione per tyre penalties su Suzuka."""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "python_backend"))

from python_backend.lap_simulator.lap_simulator import LapSimulator, LapResult, CarEntry
from python_backend.lap_simulator.data_types import (
    CircuitConfig, EnvContext, 
    CarState, TyreCompound, WheelPosition
)
from python_backend.lap_simulator.config_loader import load_circuit_config
from python_backend.lap_simulator.data_types import AeroSetup


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
    
    # Create basic setup (neutral)
    mclaren_offset = 0.0  # Reference team
    
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
            # Create car entry with default setup
            car_entry = CarEntry(
                car_id="mclaren_test",
                team_name="mclaren",
                driver_name="Test Driver",
                setup=None,  # Will use default setup
                fuel_kg=10.0,  # Reference fuel
                push_level=1.0,
                tyre_compound=TyreCompound(compound),
                tyre_wear_pct=wear,
                tyre_surface_temp_c=90.0,
                tyre_core_temp_c=80.0
            )
            
            # Create simulator
            sim = LapSimulator(config, env, enable_battles=False)
            
            # Run lap
            result: LapResult = sim.run_lap(car_entry)
            
            lap_time = result.total_time_s
            
            # Store reference time (C3 at 5% wear should be ~87s)
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
