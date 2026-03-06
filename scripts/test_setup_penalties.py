#!/usr/bin/env python3
"""
Test Setup Penalties - Script per testare l'impatto di setup errati progressivi

Genera una tabella con i tempi McLaren per vari setup errati e lo scostamento dal tempo di riferimento.
"""
import json
import sys
from pathlib import Path

# Add python_backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_backend"))

from lap_simulator.config_loader import load_circuit_config
from lap_simulator.lap_simulator import LapSimulator, CarEntry
from lap_simulator.data_types import EnvContext, CarState, AeroSetup, DriverSkills
from utils.adapter import racecar_to_car_entry

# Load ideal setup from setup_ranges for Suzuka
from lap_simulator.setup_penalty_v2 import build_ideal_setup

IDEAL_SETUP_OBJ = build_ideal_setup("jp-1962_suzuka")
DEFAULT_SETUP = IDEAL_SETUP_OBJ.ideal_sliders

# Ensure all sliders are present (add missing ones with default 50)
for slider_name in ['front_wing', 'rear_wing', 'beam_wing', 'ride_height_front', 'ride_height_rear', 
                     'suspension_front', 'suspension_rear', 'antiroll_front', 'antiroll_rear', 
                     'brake_balance', 'brake_duct']:
    if slider_name not in DEFAULT_SETUP:
        DEFAULT_SETUP[slider_name] = 50

def create_mclaren_car_entry(setup_override=None):
    """Crea una CarEntry McLaren con setup personalizzato."""
    from lap_simulator.data_types import CarState, AeroSetup, DriverSkills, TyreCompound, WheelPosition, TyreState, EngineMapName
    
    # Create CarState
    car_state = CarState(car_id="4")
    
    # Setup tyres (soft compound for qualifying)
    car_state.tyres = {
        wp: TyreState(wheel_pos=wp, compound=TyreCompound.C4) 
        for wp in WheelPosition
    }
    
    # Create AeroSetup
    aero_setup = AeroSetup()
    
    # Create DriverSkills (Lando Norris - high quali skill)
    driver_skills = DriverSkills(
        raw_pace=85,
        race_craft=75,
        aggression=65,
        consistency=85,
        tyre_management=80,
        overtaking_skill=75,
        defending_skill=35,
        wet_skill=60,
        smoothness=60,
        setup_finding=85,
    )
    
    # Create CarEntry with setup data
    setup_sliders = setup_override or DEFAULT_SETUP
    
    return CarEntry(
        car_id="4",
        state=car_state,
        aero_setup=aero_setup,
        driver_skills=driver_skills,
        push_level=1.0,  # Maximum push for qualifying
        delta_aero=0.0,
        delta_grip=0.0,
        apply_baseline_delta=True,
        setup_sliders=setup_sliders,
        ideal_setup_sliders=DEFAULT_SETUP,
    )

def run_simulation_with_setup(setup_name, setup_override):
    """Esegue una simulazione con un setup specifico."""
    config = load_circuit_config("jp-1962_suzuka")
    env = EnvContext(air_temp_c=25.0, track_temp_c=35.0)
    
    entry = create_mclaren_car_entry(setup_override)
    
    # Debug: print setup values being used
    print(f"  📋 Setup '{setup_name}': {setup_override}")
    
    sim = LapSimulator(config, env)
    sim.register_car(entry)
    results = sim.run_lap()
    
    lap_time = results["4"].lap_time_s
    
    # Debug: check if setup penalties are being applied
    if results["4"].section_results:
        first_section = results["4"].section_results[0]
        if first_section.setup_penalty_s != 0:
            print(f"  ⚠️  Setup penalty detected: {first_section.setup_penalty_s:.6f}s")
        else:
            print(f"  ℹ️  No setup penalty applied (expected - placeholder logic)")
    
    return lap_time

def main():
    print("🏁 Test Setup Penalties - Suzuka Qualifying")
    print("=" * 60)
    
    print("🔍 Verifica passaggio parametri setup:")
    print("-" * 40)
    
    # Test 1: Setup di riferimento
    print("1️⃣ Setup di riferimento (ideale):")
    reference_time = run_simulation_with_setup("Reference", DEFAULT_SETUP)
    print(f"   ⚡ Tempo: {reference_time:.3f}s")
    print()
    
    # Test 2: Setup con downforce massima
    print("2️⃣ Setup con downforce massima:")
    max_df_setup = {'front_wing': 100, 'rear_wing': 100, 'beam_wing': 100}
    max_df_time = run_simulation_with_setup("Max Downforce", max_df_setup)
    gap = max_df_time - reference_time
    print(f"   ⚡ Tempo: {max_df_time:.3f}s (gap: {gap:+.3f}s)")
    print()
    
    # Test 3: Setup con downforce minima
    print("3️⃣ Setup con downforce minima:")
    min_df_setup = {'front_wing': 0, 'rear_wing': 0, 'beam_wing': 0}
    min_df_time = run_simulation_with_setup("Min Downforce", min_df_setup)
    gap = min_df_time - reference_time
    print(f"   ⚡ Tempo: {min_df_time:.3f}s (gap: {gap:+.3f}s)")
    print()
    
    # Test 4: Setup Monaco (alto carico)
    print("4️⃣ Setup Monaco (alto carico):")
    monaco_setup = {'front_wing': 100, 'rear_wing': 100, 'beam_wing': 100, 'ride_height_front': 0, 'ride_height_rear': 0}
    monaco_time = run_simulation_with_setup("Monaco Setup", monaco_setup)
    gap = monaco_time - reference_time
    print(f"   ⚡ Tempo: {monaco_time:.3f}s (gap: {gap:+.3f}s)")
    print()
    
    # Test 5: Setup Monza (basso carico)
    print("5️⃣ Setup Monza (basso carico):")
    monza_setup = {'front_wing': 0, 'rear_wing': 0, 'beam_wing': 0, 'ride_height_front': 100, 'ride_height_rear': 100}
    monza_time = run_simulation_with_setup("Monza Setup", monza_setup)
    gap = monza_time - reference_time
    print(f"   ⚡ Tempo: {monza_time:.3f}s (gap: {gap:+.3f}s)")
    print()
    
    # Test 6: Setup con DF > target (dentro finestra) - dovrebbe avere BONUS
    print("6️⃣ Setup con DF > target (dentro finestra):")
    bonus_setup = {'front_wing': 65, 'rear_wing': 65, 'beam_wing': 60}  # Dentro range, ma DF > target
    bonus_time = run_simulation_with_setup("DF Bonus Setup", bonus_setup)
    gap = bonus_time - reference_time
    print(f"   ⚡ Tempo: {bonus_time:.3f}s (gap: {gap:+.3f}s)")
    print()
    
    print("=" * 60)
    print("📊 Riepilogo Test Parametri Setup:")
    print(f"   • Tempo riferimento: {reference_time:.3f}s")
    print(f"   • Max Downforce: {max_df_time:.3f}s ({max_df_time - reference_time:+.3f}s)")
    print(f"   • Min Downforce: {min_df_time:.3f}s ({min_df_time - reference_time:+.3f}s)")
    print(f"   • Monaco Setup: {monza_time:.3f}s ({monaco_time - reference_time:+.3f}s)")
    print(f"   • Monza Setup: {monza_time:.3f}s ({monza_time - reference_time:+.3f}s)")
    print()
    
    # Verifica finale
    all_times = [reference_time, max_df_time, min_df_time, monaco_time, monza_time]
    if len(set(all_times)) == 1:
        print("⚠️  ATTENZIONE: Tutti i tempi sono identici!")
        print("   Questo indica che le penalità setup non sono ancora applicate.")
        print("   L'infrastruttura è pronta, ma manca la logica di calcolo effettiva.")
    else:
        print("✅ Le penalità setup sono state applicate!")
        print("   I tempi variano in base ai setup utilizzati.")
    
    return reference_time
    
    # Test setup errati progressivi
    test_cases = [
        # Downforce extremes
        ("Max Downforce", {'front_wing': 100, 'rear_wing': 100, 'beam_wing': 100}),
        ("Min Downforce", {'front_wing': 0, 'rear_wing': 0, 'beam_wing': 0}),
        
        # Ride height extremes
        ("Max Ride Height", {'ride_height_front': 100, 'ride_height_rear': 100}),
        ("Min Ride Height", {'ride_height_front': 0, 'ride_height_rear': 0}),
        
        # Suspension extremes
        ("Max Stiffness", {'suspension_front': 100, 'suspension_rear': 100, 'antiroll_front': 100, 'antiroll_rear': 100}),
        ("Min Stiffness", {'suspension_front': 0, 'suspension_rear': 0, 'antiroll_front': 0, 'antiroll_rear': 0}),
        
        # Brake extremes
        ("Front Brake Bias", {'brake_balance': 100}),
        ("Rear Brake Bias", {'brake_balance': 0}),
        ("Closed Brake Duct", {'brake_duct': 0}),
        ("Open Brake Duct", {'brake_duct': 100}),
        
        # Combined extremes
        ("Monaco Setup", {'front_wing': 100, 'rear_wing': 100, 'beam_wing': 100, 'ride_height_front': 0, 'ride_height_rear': 0}),
        ("Monza Setup", {'front_wing': 0, 'rear_wing': 0, 'beam_wing': 0, 'ride_height_front': 100, 'ride_height_rear': 100}),
        
        # Random bad setups
        ("Bad Setup 1", {'front_wing': 20, 'rear_wing': 80, 'ride_height_front': 30, 'ride_height_rear': 70}),
        ("Bad Setup 2", {'front_wing': 80, 'rear_wing': 20, 'suspension_front': 20, 'suspension_rear': 80}),
        ("Bad Setup 3", {'front_wing': 10, 'rear_wing': 10, 'beam_wing': 90, 'antiroll_front': 90, 'antiroll_rear': 10}),
    ]
    
    print(f"{'Setup Test':<20} {'Lap Time':<10} {'Gap (s)':<10} {'Gap (%)':<10}")
    print("-" * 55)
    
    results = []
    
    for setup_name, setup_override in test_cases:
        # Combina con setup di default
        full_setup = DEFAULT_SETUP.copy()
        full_setup.update(setup_override)
        
        lap_time = run_simulation_with_setup(setup_name, full_setup)
        gap_s = lap_time - reference_time
        gap_pct = (gap_s / reference_time) * 100
        
        # Color coding per gap
        if abs(gap_pct) < 0.1:
            gap_str = f"{gap_pct:+.2f}%"
        elif gap_pct > 0:
            gap_str = f"🔴 {gap_pct:+.2f}%"
        else:
            gap_str = f"🟢 {gap_pct:+.2f}%"
        
        print(f"{setup_name:<20} {lap_time:<10.3f} {gap_s:+.3f}s   {gap_str}")
        
        results.append({
            'setup': setup_name,
            'lap_time': lap_time,
            'gap_s': gap_s,
            'gap_pct': gap_pct,
            'setup_values': full_setup
        })
    
    # Salva risultati
    results_file = Path("reports/setup_penalty_test_results.json")
    results_file.parent.mkdir(exist_ok=True)
    
    with open(results_file, 'w') as f:
        json.dump({
            'reference_time': reference_time,
            'circuit': 'jp-1962_suzuka',
            'car': 'McLaren',
            'results': results
        }, f, indent=2)
    
    print(f"\n📊 Risultati salvati in: {results_file}")
    
    # Statistiche
    positive_gaps = [r for r in results if r['gap_pct'] > 0.1]
    negative_gaps = [r for r in results if r['gap_pct'] < -0.1]
    
    print(f"\n📈 Statistiche:")
    print(f"  • Setup testati: {len(results)}")
    print(f"  • Penalità (più lento): {len(positive_gaps)}")
    print(f"  • Bonus (più veloce): {len(negative_gaps)}")
    
    if positive_gaps:
        worst = max(positive_gaps, key=lambda x: x['gap_pct'])
        print(f"  • Peggior setup: {worst['setup']} (+{worst['gap_pct']:.2f}%)")
    
    if negative_gaps:
        best = min(negative_gaps, key=lambda x: x['gap_pct'])
        print(f"  • Miglior setup: {best['setup']} ({best['gap_pct']:.2f}%)")

if __name__ == "__main__":
    main()
