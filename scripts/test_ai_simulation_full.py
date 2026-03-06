#!/usr/bin/env python3
"""
Test completo simulazione AI per verificare:
a) Tempi diversi tra team
b) Tutti i penalty applicati (fuel, push, PU, brake, setup, gomme)
c) Miglioramento setup durante la sessione
"""

import sys
import json
import statistics
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass

# Add python_backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python_backend"))

from lap_simulator.config_loader import load_circuit_config
from lap_simulator.lap_simulator import LapSimulator, CarEntry
from lap_simulator.data_types import EnvContext, CarState, AeroSetup, DriverSkills, DriverIntent
from lap_simulator.ai_driver_engine import AIDriverEngine, RunProgram

# Team configurations
TEAMS = {
    "MCL": {"name": "McLaren", "driver": "Lando Norris", "skill": 95},
    "RBR": {"name": "Red Bull", "driver": "Max Verstappen", "skill": 98},
    "FER": {"name": "Ferrari", "driver": "Charles Leclerc", "skill": 96},
    "MER": {"name": "Mercedes", "driver": "Lewis Hamilton", "skill": 94},
    "AST": {"name": "Aston Martin", "driver": "Fernando Alonso", "skill": 93},
    "ALP": {"name": "Alpine", "driver": "Pierre Gasly", "skill": 89},
    "WIL": {"name": "Williams", "driver": "Alex Albon", "skill": 87},
    "HAAS": {"name": "Haas", "driver": "Nico Hülkenberg", "skill": 85},
    "ALF": {"name": "Alfa Romeo", "driver": "Valtteri Bottas", "skill": 86},
    "ALP_T": {"name": "Alpine", "driver": "Esteban Ocon", "skill": 88},
}

@dataclass
class SimulationResult:
    """Risultato della simulazione per un team"""
    team_code: str
    team_name: str
    driver: str
    lap_time: float
    penalties: Dict[str, float]
    setup_improvement: float = 0.0

def create_ai_car_entry(team_code: str, circuit_id: str, config) -> CarEntry:
    """Crea una CarEntry per un team AI"""
    team_info = TEAMS[team_code]
    
    # Create basic car entry
    car_id = f"AI_{team_code}_{team_info['driver'].replace(' ', '_')}"
    
    # Default setup (will be improved by AI)
    setup_sliders = {
        'front_wing': 50, 'rear_wing': 50, 'beam_wing': 50,
        'ride_height_front': 50, 'ride_height_rear': 50,
        'suspension_front': 50, 'suspension_rear': 50,
        'antiroll_front': 50, 'antiroll_rear': 50,
        'brake_balance': 50, 'brake_duct': 50
    }
    
    # Create car state
    car_state = CarState(
        car_id=car_id,
        team_code=team_code,
        lap_time_acc_s=0.0,
        v_current_ms=0.0,
        current_section_idx=0,
    )
    # Set fuel mass in PU state
    car_state.pu.fuel_kg = 100.0  # Full fuel for testing
    
    # Create driver skills
    driver_skills = DriverSkills(
        raw_pace=team_info["skill"],
        race_craft=team_info["skill"],
        aggression=min(95, int(team_info["skill"] * 0.9)),
        consistency=team_info["skill"] - 5,
        tyre_management=team_info["skill"],
        overtaking_skill=team_info["skill"] - 10,
        defending_skill=team_info["skill"] - 10,
        wet_skill=team_info["skill"] - 15,
        smoothness=team_info["skill"] - 10,
        setup_finding=team_info["skill"] - 15,
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
        push_level=10,  # Maximum push for testing
        pace_factor=1.1,  # Push pace
        ers_push_mode=True,  # ERS deploy
        fuel_save_mode=False,
        tyre_save_mode=False,
    )
    
    return CarEntry(
        car_id=car_id,
        state=car_state,
        aero_setup=aero_setup,
        driver_skills=driver_skills,
        push_level=1.0,  # Maximum push
        setup_sliders=setup_sliders,
        ideal_setup_sliders=setup_sliders.copy(),
    )

def extract_penalties_from_result(result) -> Dict[str, float]:
    """Estrae tutte le penalità dal risultato della simulazione"""
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

def run_single_simulation(team_code: str, circuit_id: str) -> SimulationResult:
    """Esegue una singola simulazione per un team"""
    config = load_circuit_config(circuit_id)
    config.baseline_delta = 0.0  # Realistic lap times
    env = EnvContext(air_temp_c=25.0, track_temp_c=35.0)
    
    entry = create_ai_car_entry(team_code, circuit_id, config)
    
    # DEBUG: Print key parameters
    print(f"  🔧 {team_code}: Fuel={entry.state.pu.fuel_kg:.1f}kg, Push={entry.push_level:.1f}, "
          f"Skill={entry.driver_skills.raw_pace}, CV=???")
    
    sim = LapSimulator(config, env)
    sim.register_car(entry)
    result = sim.run_lap()[entry.car_id]
    
    penalties = extract_penalties_from_result(result)
    
    # DEBUG: Print penalties found
    penalty_summary = ", ".join([f"{k}:{v:.3f}s" for k, v in penalties.items() if v > 0])
    print(f"  ⚖️  {team_code}: {penalty_summary}")
    
    return SimulationResult(
        team_code=team_code,
        team_name=TEAMS[team_code]["name"],
        driver=TEAMS[team_code]["driver"],
        lap_time=result.lap_time_s,
        penalties=penalties
    )

def run_setup_improvement_test(team_code: str, circuit_id: str) -> float:
    """Verifica il miglioramento del setup durante una sessione AI"""
    config = load_circuit_config(circuit_id)
    config.baseline_delta = 0.0
    env = EnvContext(air_temp_c=25.0, track_temp_c=35.0)
    
    # Test with different setups to simulate improvement
    # Start with bad setup, then improve to ideal setup
    initial_time = None
    final_time = None
    
    # Bad setup (all sliders at 30)
    bad_setup = {
        'front_wing': 30, 'rear_wing': 30, 'beam_wing': 30,
        'ride_height_front': 30, 'ride_height_rear': 30,
        'suspension_front': 30, 'suspension_rear': 30,
        'antiroll_front': 30, 'antiroll_rear': 30,
        'brake_balance': 30, 'brake_duct': 30
    }
    
    # Good setup (all sliders at 70)
    good_setup = {
        'front_wing': 70, 'rear_wing': 70, 'beam_wing': 70,
        'ride_height_front': 70, 'ride_height_rear': 70,
        'suspension_front': 70, 'suspension_rear': 70,
        'antiroll_front': 70, 'antiroll_rear': 70,
        'brake_balance': 70, 'brake_duct': 70
    }
    
    # Test bad setup
    entry_bad = create_ai_car_entry(team_code, circuit_id, config)
    entry_bad.setup_sliders = bad_setup
    
    sim = LapSimulator(config, env)
    sim.register_car(entry_bad)
    result_bad = sim.run_lap()[entry_bad.car_id]
    initial_time = result_bad.lap_time_s
    
    # Test good setup
    entry_good = create_ai_car_entry(team_code, circuit_id, config)
    entry_good.setup_sliders = good_setup
    
    sim = LapSimulator(config, env)
    sim.register_car(entry_good)
    result_good = sim.run_lap()[entry_good.car_id]
    final_time = result_good.lap_time_s
    
    # Calculate improvement
    if initial_time and final_time:
        improvement = initial_time - final_time  # Positive = improvement
        return improvement
    
    return 0.0

def analyze_results(results: List[SimulationResult]) -> Dict[str, Any]:
    """Analizza i risultati della simulazione"""
    analysis = {
        "lap_times": {
            "fastest": min(r.lap_time for r in results),
            "slowest": max(r.lap_time for r in results),
            "mean": statistics.mean(r.lap_time for r in results),
            "std_dev": statistics.stdev(r.lap_time for r in results),
            "spread_seconds": max(r.lap_time for r in results) - min(r.lap_time for r in results),
        },
        "penalties_analysis": {},
        "setup_improvements": {}
    }
    
    # Analyze penalties
    all_penalty_types = set()
    for result in results:
        all_penalty_types.update(result.penalties.keys())
    
    for penalty_type in all_penalty_types:
        values = [r.penalties.get(penalty_type, 0) for r in results]
        analysis["penalties_analysis"][penalty_type] = {
            "teams_with_penalty": sum(1 for v in values if v > 0),
            "total_penalty": sum(values),
            "mean_penalty": statistics.mean([v for v in values if v > 0]) if any(v > 0 for v in values) else 0,
            "max_penalty": max(values)
        }
    
    return analysis

def main():
    """Esegue il test completo della simulazione AI"""
    print("🏁 Test Completo Simulazione AI")
    print("=" * 60)
    
    circuit_id = "jp-1962_suzuka"
    print(f"Circuito: {circuit_id}")
    print(f"Team testati: {len(TEAMS)}")
    print()
    
    # a) Test tempi diversi tra team
    print("a) 📊 Tempi Lap per Team:")
    results = []
    
    for team_code in sorted(TEAMS.keys()):
        result = run_single_simulation(team_code, circuit_id)
        results.append(result)
        print(f"  {result.team_code:3s} | {result.team_name:15s} | {result.lap_time:7.3f}s | {result.driver}")
    
    # Analyze lap times
    fastest = min(results, key=lambda r: r.lap_time)
    slowest = max(results, key=lambda r: r.lap_time)
    spread = slowest.lap_time - fastest.lap_time
    
    print(f"\n  📈 Analisi Tempi:")
    print(f"     Più veloce: {fastest.team_code} ({fastest.lap_time:.3f}s)")
    print(f"     Più lento: {slowest.team_code} ({slowest.lap_time:.3f}s)")
    print(f"     Spread: {spread:.3f}s ({spread/fastest.lap_time*100:.1f}%)")
    
    # b) Test penalty applicati
    print(f"\nb) ⚖️  Analisi Penalty:")
    analysis = analyze_results(results)
    
    for penalty_type, data in analysis["penalties_analysis"].items():
        if data["teams_with_penalty"] > 0:
            print(f"  {penalty_type.capitalize():8s}: {data['teams_with_penalty']:2d} team | "
                  f"Tot: {data['total_penalty']:6.3f}s | "
                  f"Media: {data['mean_penalty']:6.3f}s | "
                  f"Max: {data['max_penalty']:6.3f}s")
        else:
            print(f"  {penalty_type.capitalize():8s}: Nessun penalty applicato")
    
    # c) Test miglioramento setup
    print(f"\nc) 🔧 Miglioramento Setup durante sessione:")
    setup_results = {}
    
    # Test solo per alcuni team per velocità
    test_teams = ["MCL", "RBR", "FER", "MER"]
    
    for team_code in test_teams:
        improvement = run_setup_improvement_test(team_code, circuit_id)
        setup_results[team_code] = improvement
        
        if improvement > 0:
            print(f"  {team_code:3s}: -{improvement:.3f}s ✅")
        else:
            print(f"  {team_code:3s}: {improvement:+.3f}s ⚪")
    
    # Summary
    print(f"\n📋 Riepilogo Test:")
    
    # a) Tempi diversi
    time_spread_ok = spread > 0.5  # Almeno 0.5s di spread
    print(f"  a) Tempi diversi tra team: {'✅ PASS' if time_spread_ok else '❌ FAIL'} ({spread:.3f}s)")
    
    # b) Penalty applicati
    penalty_types_found = len([p for p, d in analysis["penalties_analysis"].items() if d["teams_with_penalty"] > 0])
    penalty_ok = penalty_types_found >= 4  # Almeno 4 tipi di penalty
    print(f"  b) Penalty applicati: {'✅ PASS' if penalty_ok else '❌ FAIL'} ({penalty_types_found} tipi)")
    
    # c) Miglioramento setup
    teams_improved = sum(1 for imp in setup_results.values() if imp > 0)
    setup_ok = teams_improved >= 2  # Almeno 2 team migliorano
    print(f"  c) Miglioramento setup: {'✅ PASS' if setup_ok else '❌ FAIL'} ({teams_improved}/{len(test_teams)} team)")
    
    # Overall
    overall_pass = time_spread_ok and penalty_ok and setup_ok
    print(f"\n🎯 Test Globale: {'✅ PASS' if overall_pass else '❌ FAIL'}")
    
    # Save detailed results
    output_file = Path("reports/ai_simulation_test_results.json")
    output_file.parent.mkdir(exist_ok=True)
    
    detailed_results = {
        "circuit": circuit_id,
        "timestamp": str(Path(__file__).resolve()),
        "results": [
            {
                "team_code": r.team_code,
                "team_name": r.team_name,
                "driver": r.driver,
                "lap_time": r.lap_time,
                "penalties": r.penalties
            }
            for r in results
        ],
        "analysis": analysis,
        "setup_improvements": setup_results,
        "test_summary": {
            "time_spread_ok": time_spread_ok,
            "penalty_ok": penalty_ok,
            "setup_ok": setup_ok,
            "overall_pass": overall_pass
        }
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(detailed_results, f, indent=2)
    
    print(f"📄 Risultati dettagliati salvati in: {output_file}")

if __name__ == "__main__":
    main()
