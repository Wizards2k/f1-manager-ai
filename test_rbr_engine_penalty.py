#!/usr/bin/env python3
"""
Test per verificare le penalità motore con RBR (motore Honda 1015 CV).
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "python_backend"))

from python_backend.lap_simulator.lap_simulator import LapSimulator, CarEntry
from python_backend.lap_simulator.data_types import (
    CarState, EnvContext, AeroSetup, DriverSkills, 
    EngineMapName, TyreCompound, TyreState, WheelPosition
)
from python_backend.lap_simulator.config_loader import load_circuit_config
from python_backend.lap_simulator.engine_penalty import get_engine_cv_for_team

def test_rbr_engine_penalty():
    """Test RBR con motore Honda e diverse mappe."""
    
    print("="*80)
    print("TEST SISTEMA PENALITÀ MOTORE - RBR HONDA")
    print("="*80)
    
    config = load_circuit_config("az-2016_baku")
    env = EnvContext(air_temp_c=25.0, track_temp_c=35.0)
    
    # Test diverse mappe motore
    maps_to_test = [
        (EngineMapName.QUALY, "QUALY (0.0s)"),
        (EngineMapName.STANDARD, "STANDARD (0.25s)"),
        (EngineMapName.RICH, "RICH (0.12s)"),
        (EngineMapName.ECONOMY, "ECONOMY (0.40s)")
    ]
    
    for engine_map, map_desc in maps_to_test:
        # Creare RBR con motore Honda
        state = CarState(car_id="RBR", team_code="RBR")
        state.pu.active_map = engine_map
        state.pu.fuel_kg = 2.5
        
        # Gomme soft
        soft_compound = TyreCompound.C3
        state.tyres = {wp: TyreState(wheel_pos=wp, compound=soft_compound) for wp in WheelPosition}
        for tyre in state.tyres.values():
            tyre.surface_temp_c = 100.0
            tyre.core_temp_c = 100.0
        
        state.ers_mode = "Deploy"
        
        # Driver skills standard
        skills = DriverSkills(
            raw_pace=100, race_craft=95, consistency=95, aggression=80,
            tyre_management=85, overtaking_skill=90, defending_skill=85,
            wet_skill=80, smoothness=85, setup_finding=80
        )
        
        # Aero setup standard
        aero = AeroSetup()
        
        # Creare CarEntry
        entry = CarEntry(
            car_id="RBR",
            state=state,
            aero_setup=aero,
            driver_skills=skills,
            push_level=1.0,
            apply_baseline_delta=False
        )
        
        # Simulare
        sim = LapSimulator(config, env)
        sim.register_car(entry)
        result = sim.run_lap()["RBR"]
        
        # Analizzare risultati
        print(f"\n🏁 RBR - Baku - {map_desc}")
        print(f"   CV motore: {get_engine_cv_for_team('RBR')} (vs Mercedes 1008)")
        print(f"   Delta CV: +{get_engine_cv_for_team('RBR') - 1008} CV")
        print(f"   Coefficiente penalità: {config.engine_penalty_coeff}")
        print(f"   Mappa motore: {engine_map.value}")
        
        # Mostra penalità motore per sezione
        total_engine_penalty = 0.0
        straight_sections = 0
        
        for i, section_result in enumerate(result.section_results):
            if section_result.engine_penalty_s > 0:
                total_engine_penalty += section_result.engine_penalty_s
                straight_sections += 1
                print(f"   Sezione {i+1} ({config.sections[i].kind.value}): +{section_result.engine_penalty_s:.3f}s")
        
        print(f"   Totale penalità motore: +{total_engine_penalty:.3f}s su {straight_sections} sezioni")
        
        # Calcolo atteso
        cv_delta = get_engine_cv_for_team('RBR') - 1008  # +7 CV
        cv_penalty = cv_delta * config.engine_penalty_coeff  # 7 * 0.01 = 0.07s per rettilineo
        map_penalty = {"QUALY": 0.0, "STANDARD": 0.25, "RICH": 0.12, "ECONOMY": 0.40}[engine_map.value]
        expected_per_straight = cv_penalty + map_penalty
        expected_total = expected_per_straight * straight_sections
        
        print(f"   Atteso per rettilineo: +{expected_per_straight:.3f}s (CV: +{cv_penalty:.3f}s + Mappa: +{map_penalty:.3f}s)")
        print(f"   Atteso totale: +{expected_total:.3f}s")
        print(f"   Differenza: {abs(total_engine_penalty - expected_total):.3f}s")

if __name__ == "__main__":
    test_rbr_engine_penalty()
