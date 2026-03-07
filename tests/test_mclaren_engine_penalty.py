#!/usr/bin/env python3
"""
Test specifico per verificare il sistema di penalità motore con McLaren.
Mostra come il motore Mercedes con mappa QUALY genera il tempo di riferimento.
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

def test_mclaren_engine_penalty():
    """Test McLaren con motore Mercedes e mappa QUALIFY su diversi circuiti."""
    
    circuits = ["az-2016_baku", "it-1922_monza", "mc-1929_monaco"]
    
    print("="*80)
    print("TEST SISTEMA PENALITÀ MOTORE - McLAREN MERCEDES")
    print("="*80)
    
    for circuit_id in circuits:
        config = load_circuit_config(circuit_id)
        env = EnvContext(air_temp_c=25.0, track_temp_c=35.0)
        
        # Creare McLaren con motore Mercedes
        state = CarState(car_id="MCL", team_code="MCL")
        state.pu.active_map = EngineMapName.QUALIFY
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
            car_id="MCL",
            state=state,
            aero_setup=aero,
            driver_skills=skills,
            push_level=1.0,
            apply_baseline_delta=False  # Importante: nessun delta di base
        )
        
        # Simulare
        sim = LapSimulator(config, env)
        sim.register_car(entry)
        result = sim.run_lap()["MCL"]
        
        # Analizzare risultati
        print(f"\n🏁 {config.circuit_name.upper()}")
        print(f"   Tempo giro: {result.lap_time_s:.3f}s")
        print(f"   CV motore: {get_engine_cv_for_team('MCL')} (Mercedes reference)")
        print(f"   Coefficiente penalità: {config.engine_penalty_coeff}")
        print(f"   Mappa motore: {state.pu.active_map.value}")
        
        # Mostra penalità motore per sezione
        total_engine_penalty = 0.0
        straight_sections = 0
        
        for i, section_result in enumerate(result.section_results):
            if section_result.engine_penalty_s > 0:
                total_engine_penalty += section_result.engine_penalty_s
                straight_sections += 1
                print(f"   Sezione {i+1} ({config.sections[i].kind.value}): +{section_result.engine_penalty_s:.3f}s")
        
        print(f"   Totale penalità motore: +{total_engine_penalty:.3f}s su {straight_sections} sezioni")
        print(f"   Tempo telemetria: {sum(s.dt_ref_s for s in config.sections):.3f}s")
        print(f"   Delta totale: {result.lap_time_s - sum(s.dt_ref_s for s in config.sections):.3f}s")

if __name__ == "__main__":
    test_mclaren_engine_penalty()
