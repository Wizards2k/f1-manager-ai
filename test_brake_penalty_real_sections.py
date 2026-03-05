#!/usr/bin/env python3
"""
Focused test for Brake Penalty System on actual braking sections.
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
from python_backend.lap_simulator.brake_penalty import compute_brake_penalty

def test_brake_penalty_real_sections():
    """Test brake penalty on actual high-energy braking sections."""
    
    config = load_circuit_config("az-2016_baku")
    env = EnvContext(air_temp_c=25.0, track_temp_c=35.0)
    
    print("="*80)
    print("BRAKE PENALTY - REAL SECTIONS TEST")
    print("="*80)
    
    # Find sections with high braking energy
    high_brake_sections = [s for s in config.sections if s.braking_energy_mj >= 0.5]
    
    print(f"\n🏁 BAKU - High Energy Braking Sections")
    print(f"   Found {len(high_brake_sections)} sections with braking_energy_mj >= 0.5")
    
    # Test scenarios
    scenarios = [
        ("Optimal", 0.4, 800, 700),    # Good duct opening, cool temps
        ("Bad Duct", 0.1, 800, 700),   # Bad duct opening, cool temps  
        ("Hot Brakes", 0.4, 920, 760), # Good duct, hot temps
        ("Worst Case", 0.05, 950, 800) # Bad duct, very hot temps
    ]
    
    for scenario_name, duct_opening, front_temp, rear_temp in scenarios:
        print(f"\n   📊 {scenario_name} Scenario:")
        
        total_penalty = 0.0
        section_count = 0
        
        for section in high_brake_sections[:5]:  # Test first 5 high-energy sections
            # Create car state for this scenario
            car_state = CarState(car_id="test")
            car_state.brakes.duct_opening = duct_opening
            car_state.brakes.temp_front_c = front_temp
            car_state.brakes.temp_rear_c = rear_temp
            
            # Calculate penalty for this section
            penalty = compute_brake_penalty(car_state, section, config)
            
            if penalty > 0:
                total_penalty += penalty
                section_count += 1
                print(f"      {section.name:12}: +{penalty:.3f}s (energy: {section.braking_energy_mj:.2f} MJ)")
        
        print(f"      Total: +{total_penalty:.3f}s over {section_count} sections")
    
    # Test with full lap simulation
    print(f"\n🔄 Full Lap Simulation Test:")
    
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
        
        print(f"   {scenario_name:12}: {result.lap_time_s:7.3f}s | Brake Penalty: +{total_brake_penalty:6.3f}s ({len(brake_penalties)} sections)")
    
    print(f"\n🎉 Brake penalty test completed!")

if __name__ == "__main__":
    test_brake_penalty_real_sections()
