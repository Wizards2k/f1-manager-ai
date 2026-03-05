#!/usr/bin/env python3
"""
Integration test for Brake Penalty System.

Tests brake penalties in real circuit scenarios with different setups.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "python_backend"))

from python_backend.lap_simulator.lap_simulator import LapSimulator, CarEntry
from python_backend.lap_simulator.data_types import (
    CarState, EnvContext, AeroSetup, DriverSkills, 
    TyreCompound, TyreState, WheelPosition
)
from python_backend.lap_simulator.config_loader import load_circuit_config

def test_brake_penalty_integration():
    """Test brake penalty system integration with real circuits."""
    
    circuits = ["az-2016_baku", "it-1922_monza", "mc-1929_monaco"]
    
    print("="*80)
    print("BRAKE PENALTY INTEGRATION TEST")
    print("="*80)
    
    for circuit_id in circuits:
        config = load_circuit_config(circuit_id)
        env = EnvContext(air_temp_c=25.0, track_temp_c=35.0)
        
        print(f"\n🏁 {config.circuit_name.upper()}")
        print(f"   Brake sections: {len([s for s in config.sections if s.braking_energy_mj >= 0.05])}")
        print(f"   Critical sections: {len(config.brake_critical_sections or [])}")
        
        # Test 1: Optimal brake setup (no penalty)
        state_optimal = CarState(car_id="optimal")
        state_optimal.brakes.duct_opening = 0.4  # Within most ranges
        state_optimal.brakes.temp_front_c = 800  # Cool
        state_optimal.brakes.temp_rear_c = 700   # Cool
        
        # Test 2: Suboptimal brake setup (duct too closed)
        state_bad_duct = CarState(car_id="bad_duct")
        state_bad_duct.brakes.duct_opening = 0.1  # Too closed
        state_bad_duct.brakes.temp_front_c = 800
        state_bad_duct.brakes.temp_rear_c = 700
        
        # Test 3: Hot brakes (fade penalty)
        state_hot = CarState(car_id="hot")
        state_hot.brakes.duct_opening = 0.4  # Optimal
        state_hot.brakes.temp_front_c = 920  # Hot front
        state_hot.brakes.temp_rear_c = 760   # Warm rear
        
        # Test 4: Worst case (bad duct + hot brakes)
        state_worst = CarState(car_id="worst")
        state_worst.brakes.duct_opening = 0.05  # Very closed
        state_worst.brakes.temp_front_c = 950  # Very hot
        state_worst.brakes.temp_rear_c = 800   # Hot
        
        # Common setup
        for state in [state_optimal, state_bad_duct, state_hot, state_worst]:
            state.pu.fuel_kg = 2.5
            soft_compound = TyreCompound.C3
            state.tyres = {wp: TyreState(wheel_pos=wp, compound=soft_compound) for wp in WheelPosition}
            for tyre in state.tyres.values():
                tyre.surface_temp_c = 100.0
                tyre.core_temp_c = 100.0
            state.ers_mode = "Deploy"
        
        skills = DriverSkills(
            raw_pace=100, race_craft=95, consistency=95, aggression=80,
            tyre_management=85, overtaking_skill=90, defending_skill=85,
            wet_skill=80, smoothness=85, setup_finding=80
        )
        
        aero = AeroSetup()
        
        # Test each setup
        for state, setup_name in [
            (state_optimal, "Optimal Setup"),
            (state_bad_duct, "Bad Duct (0.1)"),
            (state_hot, "Hot Brakes"),
            (state_worst, "Worst Case")
        ]:
            entry = CarEntry(
                car_id=state.car_id,
                state=state,
                aero_setup=aero,
                driver_skills=skills,
                push_level=1.0,
                apply_baseline_delta=False
            )
            
            sim = LapSimulator(config, env)
            sim.register_car(entry)
            result = sim.run_lap()[state.car_id]
            
            # Calculate brake penalties
            total_brake_penalty = sum(sr.brake_penalty_s for sr in result.section_results)
            brake_sections = [sr for sr in result.section_results if sr.brake_penalty_s > 0]
            
            print(f"   {setup_name:15}: {result.lap_time_s:7.3f}s | Brake Penalty: +{total_brake_penalty:6.3f}s ({len(brake_sections)} sections)")
            
            if brake_sections:
                max_penalty = max(sr.brake_penalty_s for sr in brake_sections)
                print(f"                   Max section penalty: +{max_penalty:.3f}s")
    
    print(f"\n🎉 Brake penalty integration test completed!")

if __name__ == "__main__":
    test_brake_penalty_integration()
