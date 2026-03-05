#!/usr/bin/env python3
"""
Realistic test for Brake Penalty System.
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

def test_realistic_brake_penalty():
    """Test brake penalty with realistic scenarios."""
    
    config = load_circuit_config("az-2016_baku")
    env = EnvContext(air_temp_c=25.0, track_temp_c=35.0)
    
    print("="*80)
    print("REALISTIC BRAKE PENALTY TEST")
    print("="*80)
    
    # Realistic scenarios based on actual F1 setups
    scenarios = [
        ("Optimal Setup", 0.4, 800, 700),      # Perfect duct opening, cool brakes
        ("Slightly Closed", 0.25, 820, 720),   # Slightly conservative duct
        ("Aggressive Setup", 0.55, 850, 740),  # More open duct (drag penalty)
        ("Warm Brakes", 0.35, 870, 760),       # Warm but not critical
        ("Critical Temp", 0.3, 910, 780),       # Approaching fade threshold
    ]
    
    for scenario_name, duct_opening, front_temp, rear_temp in scenarios:
        # Setup car state
        state = CarState(car_id="test")
        state.brakes.duct_opening = duct_opening
        state.brakes.temp_front_c = front_temp
        state.brakes.temp_rear_c = rear_temp
        state.pu.fuel_kg = 2.5
        
        # Setup tyres
        soft_compound = TyreCompound.C3
        state.tyres = {wp: TyreState(wheel_pos=wp, compound=soft_compound) for wp in WheelPosition}
        for tyre in state.tyres.values():
            tyre.surface_temp_c = 100.0
            tyre.core_temp_c = 100.0
        
        state.ers_mode = "Deploy"
        
        # Setup driver and aero
        skills = DriverSkills(
            raw_pace=100, race_craft=95, consistency=95, aggression=80,
            tyre_management=85, overtaking_skill=90, defending_skill=85,
            wet_skill=80, smoothness=85, setup_finding=80
        )
        
        aero = AeroSetup()
        
        # Create car entry and simulate
        entry = CarEntry(
            car_id="test",
            state=state,
            aero_setup=aero,
            driver_skills=skills,
            push_level=1.0,
            apply_baseline_delta=False
        )
        
        sim = LapSimulator(config, env)
        sim.register_car(entry)
        result = sim.run_lap()["test"]
        
        # Calculate brake penalties
        brake_penalties = [sr.brake_penalty_s for sr in result.section_results if sr.brake_penalty_s > 0]
        total_brake_penalty = sum(brake_penalties)
        
        # Show details for top penalty sections
        penalty_sections = []
        for i, sr in enumerate(result.section_results):
            if sr.brake_penalty_s > 0:
                section = config.sections[i]
                penalty_sections.append((section.name, sr.brake_penalty_s))
        
        top_sections = sorted(penalty_sections, key=lambda x: x[1], reverse=True)[:3]
        
        print(f"\n📊 {scenario_name:20}: {result.lap_time_s:7.3f}s | Brake Penalty: +{total_brake_penalty:6.3f}s ({len(brake_penalties)} sections)")
        print(f"                         Duct: {duct_opening:.2f} | Front: {front_temp}°C | Rear: {rear_temp}°C")
        
        if top_sections:
            print(f"                         Top penalties:")
            for section_name, penalty in top_sections:
                print(f"                           - {section_name:12}: +{penalty:.3f}s")
    
    print(f"\n🎯 Target: Brake penalties should be under 1.0s for optimal setups")
    print(f"🎯 Target: Bad setups should have 1-3s penalty")
    print(f"🎯 Target: Critical issues should have 3-6s penalty")
    print(f"\n🎉 Realistic brake penalty test completed!")

if __name__ == "__main__":
    test_realistic_brake_penalty()
