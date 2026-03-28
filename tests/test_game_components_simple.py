#!/usr/bin/env python3
"""
Test semplice per verificare che i componenti del gioco funzionino
e che i penalty vengano applicati correttamente
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any

# Add python_backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python_backend"))

# Import game components
from utils.session_bridge import SessionBridge
from utils.adapter import racecar_to_car_entry
from models.models import RaceCar, Team, Pilota, Nazionalita, TireCompound
from lap_simulator.lap_simulator import LapSimulator
from lap_simulator.config_loader import load_circuit_config
from lap_simulator.data_types import EnvContext, CarState, AeroSetup, DriverSkills, DriverIntent, EngineMapName
from lap_simulator.lap_simulator import CarEntry

def create_test_team_and_driver(team_code: str, team_name: str, driver_name: str, skill: int) -> tuple:
    """Crea team e driver per il test"""
    
    # Create team
    team = Team(
        nome_scuderia=team_name,
        sigla_scuderia=team_code,
        nazionalita=Nazionalita.REGNO_UNITO,
        colore_team="#FF0000",
        simulator_quality=75
    )
    
    # Create driver (Pilota)
    driver = Pilota(
        nome=driver_name.split()[0],
        cognome=driver_name.split()[-1] if len(driver_name.split()) > 1 else "",
        nazionalita=Nazionalita.REGNO_UNITO,
        eta=28,
        numero_di_gara=1,
        velocita=skill,
        qualifica=skill,
        gara=skill - 2,
        aggressivita=min(95, int(skill * 0.9)),
        costanza=skill - 5,
        consumo_gomme=skill,
        ricerca_assetto=skill - 3,
        perfezionismo=85
    )
    
    return team, driver

def extract_penalties_from_lap_result(lap_result) -> Dict[str, float]:
    """Estrae le penalità dal risultato della simulazione"""
    penalties = {}
    
    if hasattr(lap_result, 'section_results'):
        for section_result in lap_result.section_results:
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

def test_racecar_to_car_entry_prefers_ers_mode_for_active_map():
    team, driver = create_test_team_and_driver("FER", "Ferrari", "Charles Leclerc", 96)
    race_car = RaceCar(pilot=driver, team=team, initial_compound=TireCompound.MEDIUM)
    race_car.ice_mode = "standard"
    race_car.ers_mode = "QUALIFY"
    race_car.player_config["ice_mode"] = race_car.ice_mode
    race_car.player_config["ers_mode"] = race_car.ers_mode

    car_entry = racecar_to_car_entry(race_car)

    assert car_entry.state.pu.active_map == EngineMapName.QUALIFY
    assert car_entry.state.ers_mode == "QUALIFY"

def run_simulation_with_game_components(team_code: str, team_name: str, driver_name: str, skill: int, run_type: str = "setup_validation") -> Dict[str, Any]:
    """Esegue simulazione usando componenti del gioco con mescole diverse"""
    
    # Create team and driver
    team, driver = create_test_team_and_driver(team_code, team_name, driver_name, skill)
    
    # Assign compound based on run type
    compound_map = {
        "setup_validation": TireCompound.MEDIUM,    # Reliable setup testing
        "tyre_degradation": TireCompound.SOFT,     # Max degradation test
        "quali_simulation": TireCompound.SOFT,     # Max performance
        "race_trim": TireCompound.HARD,            # Race simulation
        "baseline": TireCompound.MEDIUM             # Default
    }
    
    compound = compound_map.get(run_type, TireCompound.MEDIUM)
    
    # Create race car
    race_car = RaceCar(
        pilot=driver,
        team=team,
        initial_compound=compound
    )
    
    # Use adapter to convert to CarEntry
    car_entry = racecar_to_car_entry(race_car)
    
    # Override driver skills with game values
    car_entry.driver_skills = DriverSkills(
        raw_pace=driver.velocita,
        race_craft=driver.gara,
        aggression=driver.aggressivita,
        consistency=driver.costanza,
        tyre_management=driver.consumo_gomme,
        overtaking_skill=driver.sorpasso,
        defending_skill=driver.sorpasso,
        wet_skill=driver.velocita - 10,
        smoothness=driver.velocita - 10,
        setup_finding=driver.ricerca_assetto,
    )
    
    # Set push level based on driver skill (higher skill = higher push)
    car_entry.push_level = min(10, max(1, int(driver.velocita / 10)))  # 85->8, 98->9
    
    # Set fuel
    car_entry.state.pu.fuel_kg = 100.0
    
    print(f"  🔧 {team_code}: Fuel={car_entry.state.pu.fuel_kg:.1f}kg, Push={car_entry.push_level}, "
          f"Skill={driver.velocita}, Compound={compound.value}, Setup={len(car_entry.setup_sliders or {})} sliders")
    
    # Run simulation
    circuit_id = "jp-1962_suzuka"
    config = load_circuit_config(circuit_id)
    config.baseline_delta = 0.0
    env = EnvContext(air_temp_c=25.0, track_temp_c=35.0)
    
    sim = LapSimulator(config, env)
    sim.register_car(car_entry)
    result = sim.run_lap()[car_entry.car_id]
    
    penalties = extract_penalties_from_lap_result(result)
    penalty_summary = ", ".join([f"{k}:{v:.3f}s" for k, v in penalties.items() if v > 0])
    
    print(f"  ⚖️  {team_code}: {penalty_summary}")
    
    return {
        "team_code": team_code,
        "team_name": team_name,
        "driver": driver_name,
        "skill": skill,
        "run_type": run_type,
        "compound": compound.value,
        "lap_time": result.lap_time_s,
        "penalties": penalties,
        "push_level": car_entry.push_level,
        "setup_sliders": car_entry.setup_sliders
    }

def main():
    """Test componenti gioco con programma pratica completo e mescole diverse"""
    print("🏁 Test Sessione Pratica Completa (Componenti Gioco + Mescole Diverse)")
    print("=" * 70)
    
    circuit_id = "jp-1962_suzuka"
    print(f"Circuito: {circuit_id}")
    print(f"Sessione: FP1 - Programma Pratica Completo")
    print()
    
    # Team configurations
    teams_config = {
        "MCL": {"name": "McLaren", "driver": "Lando Norris", "skill": 95},
        "RBR": {"name": "Red Bull", "driver": "Max Verstappen", "skill": 98},
        "FER": {"name": "Ferrari", "driver": "Charles Leclerc", "skill": 96},
        "MER": {"name": "Mercedes", "driver": "Lewis Hamilton", "skill": 94},
        "AST": {"name": "Aston Martin", "driver": "Fernando Alonso", "skill": 93},
        "ALP": {"name": "Alpine", "driver": "Pierre Gasly", "skill": 89},
        "WIL": {"name": "Williams", "driver": "Alex Albon", "skill": 87},
        "HAAS": {"name": "Haas", "driver": "Nico Hülkenberg", "skill": 85},
    }
    
    # Practice session program (FP1)
    practice_program = [
        {"run": 1, "type": "setup_validation", "description": "Setup Validation - Medium"},
        {"run": 2, "type": "tyre_degradation", "description": "Tyre Degradation - Soft"},
        {"run": 3, "type": "quali_simulation", "description": "Qualification Sim - Soft"},
    ]
    
    print("a) 🏃‍♂️ Esecuzione Programma Pratica FP1:")
    
    all_results = []
    
    for run_info in practice_program:
        print(f"\n   Run {run_info['run']}: {run_info['description']}")
        print("   " + "-" * 50)
        
        run_results = []
        
        for team_code, config in teams_config.items():
            result = run_simulation_with_game_components(
                team_code, config["name"], config["driver"], config["skill"], run_info["type"]
            )
            result["run_number"] = run_info["run"]
            run_results.append(result)
            all_results.append(result)
            
            # Format output
            compound_symbol = {"soft": "🔴", "medium": "🟡", "hard": "⚪"}.get(result["compound"], "⚫")
            print(f"  {team_code:3s} | {config['name']:15s} | {result['lap_time']:7.3f}s | "
                  f"{compound_symbol} {result['compound']:6s} | {config['driver']}")
        
        # Analyze run results
        run_times = [r['lap_time'] for r in run_results]
        fastest_run = min(run_times)
        slowest_run = max(run_times)
        spread_run = slowest_run - fastest_run
        
        print(f"   📊 Run {run_info['run']} Summary: Spread {spread_run:.3f}s ({spread_run/fastest_run*100:.1f}%)")
    
    # Overall analysis
    print(f"\nb) 📈 Analisi Completa Sessione:")
    
    # Group results by compound
    compound_groups = {}
    for result in all_results:
        compound = result["compound"]
        if compound not in compound_groups:
            compound_groups[compound] = []
        compound_groups[compound].append(result)
    
    print(f"   🏁 Analisi per Mescola:")
    for compound, compound_results in compound_groups.items():
        compound_times = [r['lap_time'] for r in compound_results]
        avg_time = sum(compound_times) / len(compound_times)
        best_time = min(compound_times)
        
        compound_symbol = {"soft": "🔴", "medium": "🟡", "hard": "⚪"}.get(compound, "⚫")
        print(f"      {compound_symbol} {compound.upper():6s}: Avg {avg_time:.3f}s | Best {best_time:.3f}s | "
              f"{len(compound_results)} runs")
    
    # Penalties analysis by compound
    print(f"   ⚖️  Penalty per Mescola:")
    for compound, compound_results in compound_groups.items():
        all_penalties = {}
        for result in compound_results:
            for penalty_type, value in result['penalties'].items():
                if penalty_type not in all_penalties:
                    all_penalties[penalty_type] = []
                all_penalties[penalty_type].append(value)
        
        compound_symbol = {"soft": "🔴", "medium": "🟡", "hard": "⚪"}.get(compound, "⚫")
        penalty_summary = ", ".join([f"{k}:{sum(v)/len(v):.3f}s" for k, v in all_penalties.items() if v])
        print(f"      {compound_symbol} {compound.upper():6s}: {penalty_summary}")
    
    results = all_results
    
    # Overall session analysis
    print(f"\nc) � Analisi Globale Sessione:")
    
    # Overall lap times analysis
    lap_times = [r['lap_time'] for r in results]
    fastest = min(lap_times)
    slowest = max(lap_times)
    spread = slowest - fastest
    
    print(f"   📊 Tempi Lap Totali:")
    print(f"      Più veloce: {fastest:.3f}s")
    print(f"      Più lento: {slowest:.3f}s")
    print(f"      Spread: {spread:.3f}s ({spread/fastest*100:.1f}%)")
    
    # Compound performance comparison
    print(f"   🏁 Performance Mescole:")
    for compound, compound_results in compound_groups.items():
        compound_times = [r['lap_time'] for r in compound_results]
        compound_symbol = {"soft": "🔴", "medium": "🟡", "hard": "⚪"}.get(compound, "⚫")
        print(f"      {compound_symbol} {compound.upper():6s}: {min(compound_times):.3f}s - {max(compound_times):.3f}s")
    
    # Push levels analysis
    push_levels = [r['push_level'] for r in results]
    print(f"   🚀 Push Levels: {min(push_levels)}-{max(push_levels)} (range: {max(push_levels)-min(push_levels)})")
    
    # Overall penalties analysis
    all_penalties = {}
    for result in results:
        for penalty_type, value in result['penalties'].items():
            if penalty_type not in all_penalties:
                all_penalties[penalty_type] = []
            all_penalties[penalty_type].append(value)
    
    print(f"   ⚖️  Penalty Totali:")
    for penalty_type, values in all_penalties.items():
        if values:
            total = sum(values)
            avg = sum(values) / len(values)
            max_val = max(values)
            runs_with_penalty = len([v for v in values if v > 0])
            
            print(f"      {penalty_type.capitalize():8s}: {runs_with_penalty:2d} runs | "
                  f"Tot: {total:6.3f}s | Media: {avg:6.3f}s | Max: {max_val:6.3f}s")
    
    # Test summary
    print(f"\n📋 Riepilogo Test Sessione Pratica:")
    
    # a) Different lap times
    time_spread_ok = spread > 0.5  # At least 0.5s spread with compounds
    print(f"  a) Tempi diversi tra team: {'✅ PASS' if time_spread_ok else '❌ FAIL'} ({spread:.3f}s)")
    
    # b) Penalties applied
    penalty_types_found = len(all_penalties)
    penalty_ok = penalty_types_found >= 2  # At least 2 penalty types
    print(f"  b) Penalty applicati: {'✅ PASS' if penalty_ok else '❌ FAIL'} ({penalty_types_found} tipi)")
    
    # c) Push levels different
    push_range_ok = max(push_levels) - min(push_levels) > 0
    print(f"  c) Push levels diversi: {'✅ PASS' if push_range_ok else '❌ FAIL'} (range {max(push_levels)-min(push_levels)})")
    
    # d) Multiple compounds used
    compounds_used = len(compound_groups)
    compounds_ok = compounds_used >= 2
    print(f"  d) Mescole diverse usate: {'✅ PASS' if compounds_ok else '❌ FAIL'} ({compounds_used} mescole)")
    
    # e) Setup sliders present
    setup_counts = [len(r['setup_sliders'] or {}) for r in results]
    setup_ok = max(setup_counts) > 0
    print(f"  e) Setup sliders presenti: {'✅ PASS' if setup_ok else '❌ FAIL'} ({max(setup_counts)} sliders)")
    
    # f) Practice program executed
    runs_executed = len(set(r['run_number'] for r in results))
    program_ok = runs_executed >= 3
    print(f"  f) Programma pratica eseguito: {'✅ PASS' if program_ok else '❌ FAIL'} ({runs_executed} runs)")
    
    # Overall
    overall_pass = time_spread_ok and penalty_ok and push_range_ok and compounds_ok and setup_ok and program_ok
    print(f"\n🎯 Test Sessione Pratica: {'✅ PASS' if overall_pass else '❌ FAIL'}")
    
    # Save detailed results
    output_file = Path("reports/game_components_test_results.json")
    output_file.parent.mkdir(exist_ok=True)
    
    detailed_results = {
        "circuit": circuit_id,
        "test_type": "Game Components + Practice Session with Compounds",
        "timestamp": str(Path(__file__).resolve()),
        "practice_program": practice_program,
        "results": results,
        "analysis": {
            "lap_times": {
                "fastest": fastest,
                "slowest": slowest,
                "spread": spread,
                "count": len(lap_times)
            },
            "push_levels": {
                "min": min(push_levels),
                "max": max(push_levels),
                "range": max(push_levels) - min(push_levels)
            },
            "compounds": {
                "used": list(compound_groups.keys()),
                "count": len(compound_groups),
                "performance": {c: {"min": min(r['lap_time'] for r in results), 
                                   "max": max(r['lap_time'] for r in results), 
                                   "count": len(results)} 
                              for c, results in compound_groups.items()}
            },
            "penalties": all_penalties,
            "setup_sliders": {
                "min": min(setup_counts),
                "max": max(setup_counts)
            }
        },
        "test_summary": {
            "time_spread_ok": time_spread_ok,
            "penalty_ok": penalty_ok,
            "push_range_ok": push_range_ok,
            "compounds_ok": compounds_ok,
            "setup_ok": setup_ok,
            "program_ok": program_ok,
            "overall_pass": overall_pass
        }
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(detailed_results, f, indent=2, default=str)
    
    print(f"📄 Risultati dettagliati salvati in: {output_file}")

if __name__ == "__main__":
    main()
