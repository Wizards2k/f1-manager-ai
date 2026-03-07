#!/usr/bin/env python3
"""
Test simulazione sessione di pratica usando componenti reali del gioco
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any

# Add python_backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python_backend"))

# Import game components
from utils.session_bridge import SessionBridge
from models.models import RaceCar, Team, Pilota, Nazionalita, TireCompound

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

def main():
    """Esegue test sessione pratica usando componenti reali del gioco"""
    print("🏁 Test Sessione Pratica (Componenti Gioco Reali)")
    print("=" * 60)
    
    circuit_id = "jp-1962_suzuka"
    print(f"Circuito: {circuit_id}")
    print(f"Sessione: FP1 (Practice 1)")
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
    
    # Create SessionBridge
    session_bridge = SessionBridge()
    
    print("a) 📊 Registrazione Team e Driver:")
    
    # Create race cars list
    race_cars = []
    
    # Register teams and drivers
    for team_code, config in teams_config.items():
        team, driver = create_test_team_and_driver(team_code, config["name"], config["driver"], config["skill"])
        
        # Create race car
        race_car = RaceCar(
            pilot=driver,
            team=team,
            initial_compound=TireCompound.MEDIUM
        )
        
        race_cars.append(race_car)
        
        print(f"  ✅ {team_code:3s} | {config['name']:15s} | {config['driver']:20s} | Skill: {config['skill']:2d}")
    
    # Initialize session
    session_bridge.init_session(
        circuit_id=circuit_id,
        race_cars=race_cars,
        session_type="FP1"
    )
    
    print(f"\nb) 🏃‍♂️ Esecuzione Sessione Pratica:")
    
    # Run session for 60 seconds (simulated)
    import time
    start_time = time.time()
    
    while time.time() - start_time < 60:  # 60 seconds of session time
        # Tick the session
        session_bridge.tick()
        
        # Small delay to avoid overwhelming
        time.sleep(0.1)
    
    # Get session results
    session_summary = session_bridge.get_session_summary()
    leaderboard = session_bridge.get_leaderboard()
    
    # Analyze results
    print(f"\nc) 📈 Analisi Risultati:")
    
    # Extract lap times from leaderboard
    lap_times = []
    team_results = {}
    
    for entry in leaderboard:
        if 'best_lap_time' in entry and entry['best_lap_time'] > 0:
            lap_times.append(entry['best_lap_time'])
            team_results[entry['car_id']] = entry
    
    # Extract penalties from session summary
    all_penalties = {}
    setup_improvements = {}
    
    if 'runs_completed' in session_summary:
        for run in session_summary['runs_completed']:
            car_id = run.get('car_id', '')
            
            # Extract penalties from lap result if available
            if 'lap_result' in run:
                penalties = extract_penalties_from_lap_result(run['lap_result'])
                
                for penalty_type, value in penalties.items():
                    if penalty_type not in all_penalties:
                        all_penalties[penalty_type] = []
                    all_penalties[penalty_type].append(value)
            
            # Setup improvement
            if 'setup_adjustment' in run:
                setup_improvements[car_id] = run['setup_adjustment']
    
    # Lap times analysis
    if lap_times:
        fastest = min(lap_times)
        slowest = max(lap_times)
        spread = slowest - fastest
        
        print(f"   📊 Tempi Lap:")
        print(f"      Più veloce: {fastest:.3f}s")
        print(f"      Più lento: {slowest:.3f}s")
        print(f"      Spread: {spread:.3f}s ({spread/fastest*100:.1f}%)")
    
    # Penalties analysis
    print(f"   ⚖️  Penalty Applicati:")
    for penalty_type, values in all_penalties.items():
        if values:
            total = sum(values)
            avg = sum(values) / len(values)
            max_val = max(values)
            teams_with_penalty = len([v for v in values if v > 0])
            
            print(f"      {penalty_type.capitalize():8s}: {teams_with_penalty:2d} team | "
                  f"Tot: {total:6.3f}s | Media: {avg:6.3f}s | Max: {max_val:6.3f}s")
    
    # Setup improvements
    print(f"   🔧 Miglioramenti Setup:")
    improved_teams = sum(1 for imp in setup_improvements.values() if imp > 0)
    total_teams = len(setup_improvements)
    
    for car_id, improvement in setup_improvements.items():
        team_code = car_id.split('_')[0] if '_' in car_id else car_id
        if improvement > 0:
            print(f"      {team_code:3s}: -{improvement:.3f}s ✅")
        else:
            print(f"      {team_code:3s}: {improvement:+.3f}s ⚪")
    
    print(f"      Team migliorati: {improved_teams}/{total_teams}")
    
    # Test summary
    print(f"\n📋 Riepilogo Test:")
    
    # a) Different lap times
    time_spread_ok = spread > 0.5  # At least 0.5s spread
    print(f"  a) Tempi diversi tra team: {'✅ PASS' if time_spread_ok else '❌ FAIL'} ({spread:.3f}s)")
    
    # b) Penalties applied
    penalty_types_found = len(all_penalties)
    penalty_ok = penalty_types_found >= 4  # At least 4 penalty types
    print(f"  b) Penalty applicati: {'✅ PASS' if penalty_ok else '❌ FAIL'} ({penalty_types_found} tipi)")
    
    # c) Setup improvements
    setup_ok = improved_teams >= 2  # At least 2 teams improved
    print(f"  c) Miglioramento setup: {'✅ PASS' if setup_ok else '❌ FAIL'} ({improved_teams}/{total_teams} team)")
    
    # Overall
    overall_pass = time_spread_ok and penalty_ok and setup_ok
    print(f"\n🎯 Test Globale: {'✅ PASS' if overall_pass else '❌ FAIL'}")
    
    # Save detailed results
    output_file = Path("reports/game_practice_session_results.json")
    output_file.parent.mkdir(exist_ok=True)
    
    detailed_results = {
        "circuit": circuit_id,
        "session_type": "FP1",
        "timestamp": str(Path(__file__).resolve()),
        "session_summary": session_summary,
        "leaderboard": leaderboard,
        "analysis": {
            "lap_times": {
                "fastest": fastest if lap_times else 0,
                "slowest": slowest if lap_times else 0,
                "spread": spread if lap_times else 0,
                "count": len(lap_times)
            },
            "penalties": all_penalties,
            "setup_improvements": setup_improvements
        },
        "test_summary": {
            "time_spread_ok": time_spread_ok,
            "penalty_ok": penalty_ok,
            "setup_ok": setup_ok,
            "overall_pass": overall_pass
        }
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(detailed_results, f, indent=2, default=str)
    
    print(f"📄 Risultati dettagliati salvati in: {output_file}")

if __name__ == "__main__":
    main()
