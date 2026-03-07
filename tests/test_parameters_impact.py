#!/usr/bin/env python3
"""
Test per verificare l'impatto di fuel e push sui tempi di lap
"""

import sys
from pathlib import Path

# Add python_backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python_backend"))

from lap_simulator.config_loader import load_circuit_config
from lap_simulator.lap_simulator import LapSimulator, CarEntry
from lap_simulator.data_types import EnvContext, CarState, AeroSetup, DriverSkills, DriverIntent

def create_test_car_entry(fuel_kg: float, push_level: float, driver_skill: int) -> CarEntry:
    """Crea una CarEntry con parametri specifici"""
    
    # Setup default
    setup_sliders = {
        'front_wing': 50, 'rear_wing': 50, 'beam_wing': 50,
        'ride_height_front': 50, 'ride_height_rear': 50,
        'suspension_front': 50, 'suspension_rear': 50,
        'antiroll_front': 50, 'antiroll_rear': 50,
        'brake_balance': 50, 'brake_duct': 50
    }
    
    # Create car state
    car_state = CarState(
        car_id="TEST_CAR",
        team_code="TEST",
        lap_time_acc_s=0.0,
        v_current_ms=0.0,
        current_section_idx=0,
    )
    car_state.pu.fuel_kg = fuel_kg
    
    # Create driver skills
    driver_skills = DriverSkills(
        raw_pace=driver_skill,
        race_craft=driver_skill,
        aggression=min(95, int(driver_skill * 0.9)),
        consistency=driver_skill - 5,
        tyre_management=driver_skill,
        overtaking_skill=driver_skill - 10,
        defending_skill=driver_skill - 10,
        wet_skill=driver_skill - 15,
        smoothness=driver_skill - 10,
        setup_finding=driver_skill - 15,
    )
    
    # Create aero setup
    aero_setup = AeroSetup(
        ride_height_front_mm=45.0,
        ride_height_rear_mm=55.0,
        antiroll_front_rigidity=0.6,
        antiroll_rear_rigidity=0.65,
    )
    
    # Create driver intent
    driver_intent = DriverIntent(
        push_level=int(push_level),
        pace_factor=0.8 + (push_level / 10) * 0.3,  # 0.8 to 1.1
        ers_push_mode=push_level > 8,
        fuel_save_mode=False,
        tyre_save_mode=False,
    )
    
    return CarEntry(
        car_id="TEST_CAR",
        state=car_state,
        aero_setup=aero_setup,
        driver_skills=driver_skills,
        push_level=push_level,  # Keep as integer 1-10
        setup_sliders=setup_sliders,
        ideal_setup_sliders=setup_sliders.copy(),
    )

def extract_penalties(result) -> dict:
    """Estrae le penalità dal risultato"""
    penalties = {}
    
    for section_result in result.section_results:
        # Fuel penalty
        if hasattr(section_result, 'fuel_penalty_s') and section_result.fuel_penalty_s > 0:
            penalties['fuel'] = penalties.get('fuel', 0) + section_result.fuel_penalty_s
        
        # Push penalty
        if hasattr(section_result, 'push_penalty_s') and section_result.push_penalty_s > 0:
            penalties['push'] = penalties.get('push', 0) + section_result.push_penalty_s
        
        # Engine penalty
        if hasattr(section_result, 'engine_penalty_s') and section_result.engine_penalty_s > 0:
            penalties['engine'] = penalties.get('engine', 0) + section_result.engine_penalty_s
        
        # Brake penalty
        if hasattr(section_result, 'brake_penalty_s') and section_result.brake_penalty_s > 0:
            penalties['brake'] = penalties.get('brake', 0) + section_result.brake_penalty_s
        
        # Setup penalty
        if hasattr(section_result, 'setup_penalty_s') and section_result.setup_penalty_s > 0:
            penalties['setup'] = penalties.get('setup', 0) + section_result.setup_penalty_s
        
        # Tyre penalty
        if hasattr(section_result, 'tyre_penalty_s') and section_result.tyre_penalty_s > 0:
            penalties['tyre'] = penalties.get('tyre', 0) + section_result.tyre_penalty_s
    
    return penalties

def main():
    """Test l'impatto dei parametri"""
    print("🔧 Test Impatto Parametri (Fuel, Push, Skill)")
    print("=" * 60)
    
    circuit_id = "jp-1962_suzuka"
    config = load_circuit_config(circuit_id)
    config.baseline_delta = 0.0
    env = EnvContext(air_temp_c=25.0, track_temp_c=35.0)
    
    # Test cases
    test_cases = [
        {"fuel": 10.0, "push": 10, "skill": 98, "name": "Light Fuel, Max Push, Top Skill"},
        {"fuel": 100.0, "push": 10, "skill": 98, "name": "Heavy Fuel, Max Push, Top Skill"},
        {"fuel": 10.0, "push": 1, "skill": 98, "name": "Light Fuel, Min Push, Top Skill"},
        {"fuel": 100.0, "push": 1, "skill": 98, "name": "Heavy Fuel, Min Push, Top Skill"},
        {"fuel": 10.0, "push": 10, "skill": 85, "name": "Light Fuel, Max Push, Low Skill"},
        {"fuel": 100.0, "push": 10, "skill": 85, "name": "Heavy Fuel, Max Push, Low Skill"},
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        
        entry = create_test_car_entry(
            test_case["fuel"], 
            test_case["push"], 
            test_case["skill"]
        )
        
        sim = LapSimulator(config, env)
        sim.register_car(entry)
        result = sim.run_lap()[entry.car_id]
        
        penalties = extract_penalties(result)
        penalty_summary = ", ".join([f"{k}:{v:.3f}s" for k, v in penalties.items() if v > 0])
        
        print(f"   ⏱️  Tempo: {result.lap_time_s:.3f}s")
        print(f"   ⚖️  Penalty: {penalty_summary if penalty_summary else 'Nessuna'}")
        print(f"   📊 Fuel: {entry.state.pu.fuel_kg:.1f}kg, Push: {entry.push_level:.1f}, Skill: {entry.driver_skills.raw_pace}")
        
        results.append({
            "name": test_case["name"],
            "fuel": test_case["fuel"],
            "push": test_case["push"],
            "skill": test_case["skill"],
            "lap_time": result.lap_time_s,
            "penalties": penalties
        })
    
    # Analysis
    print(f"\n📈 Analisi Impatto:")
    
    # Fuel impact
    light_fuel_fast = next(r for r in results if r["fuel"] == 10.0 and r["push"] == 10 and r["skill"] == 98)
    heavy_fuel_fast = next(r for r in results if r["fuel"] == 100.0 and r["push"] == 10 and r["skill"] == 98)
    fuel_impact = heavy_fuel_fast["lap_time"] - light_fuel_fast["lap_time"]
    print(f"   Fuel impact (10kg vs 100kg): +{fuel_impact:.3f}s")
    
    # Push impact
    light_fuel_fast = next(r for r in results if r["fuel"] == 10.0 and r["push"] == 10 and r["skill"] == 98)
    light_fuel_slow = next(r for r in results if r["fuel"] == 10.0 and r["push"] == 1 and r["skill"] == 98)
    push_impact = light_fuel_slow["lap_time"] - light_fuel_fast["lap_time"]
    print(f"   Push impact (push 10 vs 1): +{push_impact:.3f}s")
    
    # Skill impact
    light_fuel_top = next(r for r in results if r["fuel"] == 10.0 and r["push"] == 10 and r["skill"] == 98)
    light_fuel_low = next(r for r in results if r["fuel"] == 10.0 and r["push"] == 10 and r["skill"] == 85)
    skill_impact = light_fuel_low["lap_time"] - light_fuel_top["lap_time"]
    print(f"   Skill impact (98 vs 85): +{skill_impact:.3f}s")
    
    # Check if penalties are working
    all_penalties = set()
    for result in results:
        all_penalties.update(result["penalties"].keys())
    
    print(f"\n🎯 Penalty Types Found: {', '.join(sorted(all_penalties))}")
    print(f"   Expected: fuel, push, engine, brake, setup, tyre")

if __name__ == "__main__":
    main()
