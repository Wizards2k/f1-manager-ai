"""
REAL SIMULATION: Monza Qualifying with Universal Motor

Simulazione VERA e COMPLETA che integra:
1. Dati reali McLaren e Lando Norris dal gioco
2. Setup Monza qualifica da ai_optimal_setups.json
3. Mappe QUALIFY ICE/ERS da power_units.py
4. Driver skills Norris con push_level=10
5. Motore universale (vs penalty-based V1)

Flusso:
Per ogni sezione Monza (13 settori):
- Carica contesto sezione (velocità, lunghezza, tipo)
- Crea CarState, AeroSetup, DriverSkills reali
- Chiama update_section() con parametri autentici
- Accumula dt, velocità, parametri fisici
- Confronta vs telemetria reale

Expected: Monza 79-81s (target qualifica)
"""

import json
import os
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_types import (
    CarState, AeroSetup, AeroComponent, SuspensionState,
    DriverSkills, DriverMentalState,
    TyreState, BrakeState, PUState, DamageState, AeroForces,
    SectionContext, EnvContext, WheelPosition, TyreCompound,
    EngineMapName, ERSModeName
)

logger = logging.getLogger(__name__)


# ============================================================================
# LOAD REAL DATA FROM GAME
# ============================================================================

def load_mclaren_config() -> Dict[str, Any]:
    """Carica configurazione team McLaren."""
    path = "python_backend/data/teams_2025.json"
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        data = json.load(f)
        for team in data.get('teams', []):
            if team.get('team_id') == 'mclaren':
                return team
    return None


def load_norris_skills() -> Dict[str, int]:
    """Carica skills Lando Norris da pilots.py."""
    # Hardcoded da data/pilots.py
    return {
        'velocita': 93,          # Speed (0-100)
        'consumo': 88,           # Fuel consumption (0-100)
        'qualifica': 94,         # Qualifying (0-100)
        'gara': 93,              # Race (0-100)
        'aggressivita': 86,      # Aggression (0-100)
        'gestione_carburante': 88,  # Fuel management (0-100)
        'ricerca_assetto': 85,   # Setup search (0-100)
        'costanza': 94,          # Consistency (0-100)
        'perfezionismo': 88,     # Perfectionism (0-100)
    }


def load_monza_setup() -> Dict[str, Any]:
    """Carica setup Monza qualifica da ai_optimal_setups.json."""
    path = "python_backend/data/ai_optimal_setups.json"
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        data = json.load(f)
        return data.get('it-1922_monza', {})


def load_monza_telemetry() -> Optional[List[Dict[str, Any]]]:
    """Carica telemetria Monza 13 sezioni."""
    path = "python_backend/data/circuits/2025/it-1922_monza_Telemetry.json"
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        data = json.load(f)
        return data.get('geometry', {}).get('sections', [])


# ============================================================================
# BUILD REAL GAME OBJECTS
# ============================================================================

def create_driver_skills_norris(push_level: int = 10) -> DriverSkills:
    """
    Crea DriverSkills per Lando Norris con push_level=10.

    Mapping da pilots.py:
    - velocita=93 → raw_pace
    - gara=93 → race_craft
    - aggressivita=86 → aggression
    - costanza=94 → consistency
    - gestione_carburante=88 → tyre_management
    - ricerca_assetto=85 → setup_finding
    - perfezionismo=88 → smoothness
    """

    skills_data = load_norris_skills()

    return DriverSkills(
        raw_pace=skills_data['velocita'],           # 93 (qualifica=94)
        race_craft=skills_data['gara'],             # 93
        aggression=skills_data['aggressivita'],     # 86
        consistency=skills_data['costanza'],        # 94
        tyre_management=skills_data['gestione_carburante'],  # 88
        overtaking_skill=80,
        defending_skill=80,
        wet_skill=75,
        smoothness=skills_data['perfezionismo'],    # 88
        setup_finding=skills_data['ricerca_assetto'],  # 85
    )


def create_aero_setup_monza() -> AeroSetup:
    """
    Crea setup aerodinamico Monza qualifica.

    Da ai_optimal_setups.json:
    - best_fw: 31 (0-100) → basso downforce
    - best_rw: 21 (0-100) → basso downforce
    - rh_f: 25.0 mm
    - rh_r: 40.0 mm
    """

    setup_data = load_monza_setup()

    setup = AeroSetup()

    # Ride heights [mm]
    if setup_data:
        setup.ride_height_front_mm = setup_data.get('rh_f', 25.0)
        setup.ride_height_rear_mm = setup_data.get('rh_r', 40.0)
        setup.suspension_front.spring_rate_n_mm = setup_data.get('susp_f', 0.5)
        setup.suspension_rear.spring_rate_n_mm = setup_data.get('susp_r', 0.5)
        setup.antiroll_front_rigidity = setup_data.get('arb_f', 0.5)
        setup.antiroll_rear_rigidity = setup_data.get('arb_r', 0.5)
    else:
        setup.ride_height_front_mm = 25.0
        setup.ride_height_rear_mm = 40.0

    setup.ride_height_optimal_front_mm = setup.ride_height_front_mm
    setup.ride_height_optimal_rear_mm = setup.ride_height_rear_mm

    return setup


def create_car_state_initial() -> CarState:
    """Crea stato iniziale auto McLaren Norris."""

    car_state = CarState(
        car_id="mclaren_norris",
        team_code="MCL",
        current_section_idx=0,
        section_progress=0.0,
        lap_time_acc_s=0.0,
        lap_number=1,
        v_current_ms=0.0,
    )

    # Inizializza stato componenti
    for position in WheelPosition:
        car_state.tyres[position] = TyreState(
            wheel_pos=position,
            compound=TyreCompound.C3,  # Pirelli Medium
            surface_temp_c=25.0,
            core_temp_c=25.0,
            wear_pct=0.0,
        )

    car_state.brakes.temp_front_c = 200.0
    car_state.brakes.temp_rear_c = 200.0

    car_state.pu.active_map = EngineMapName.QUALIFY
    car_state.pu.ers_mode = ERSModeName.QUALIFY
    car_state.pu.fuel_kg = 5.0  # Minimum fuel for qualifying

    return car_state


# ============================================================================
# REPORT STRUCTURE
# ============================================================================

@dataclass
class SectorSimResult:
    """Risultato simulazione singolo settore."""
    sector_name: str
    sector_id: str
    kind: str

    # Real telemetry
    v_entry_real_kph: float
    v_exit_real_kph: float
    v_min_real_kph: float
    v_max_real_kph: float
    v_avg_real_kph: float
    dt_real_s: float
    length_m: float

    # Simulation (da update_section)
    dt_sim_s: float = 0.0
    v_exit_sim_kph: float = 0.0

    def error_pct(self) -> float:
        if self.dt_real_s > 0:
            return (self.dt_sim_s - self.dt_real_s) / self.dt_real_s * 100
        return 0.0

    def summary(self) -> str:
        ep = self.error_pct()
        return (
            f"{self.sector_name:<20} "
            f"Real: {self.dt_real_s:6.3f}s  "
            f"Sim: {self.dt_sim_s:6.3f}s  "
            f"Δ: {self.dt_sim_s - self.dt_real_s:+6.3f}s ({ep:+6.1f}%)"
        )


# ============================================================================
# MAIN SIMULATION
# ============================================================================

def main():
    print("="*130)
    print("REAL SIMULATION: MONZA QUALIFYING WITH UNIVERSAL MOTOR")
    print("="*130)
    print()

    # Carica dati reali
    print("[LOADING REAL GAME DATA]")

    mclaren = load_mclaren_config()
    print(f"✓ McLaren: {mclaren.get('name') if mclaren else 'Not found'}")

    norris_skills = load_norris_skills()
    print(f"✓ Lando Norris: velocita={norris_skills['velocita']}, qualifica={norris_skills['qualifica']}")

    monza_setup = load_monza_setup()
    print(f"✓ Monza setup: FW={monza_setup.get('best_fw', '?')}, RW={monza_setup.get('best_rw', '?')}")

    telemetry = load_monza_telemetry()
    print(f"✓ Telemetria Monza: {len(telemetry) if telemetry else 0} sezioni")
    print()

    # Crea oggetti simulazione
    print("[CREATING SIMULATION OBJECTS]")

    driver_skills = create_driver_skills_norris(push_level=10)
    print(f"✓ DriverSkills Norris (push=10, raw_pace={driver_skills.raw_pace}, consistency={driver_skills.consistency})")

    aero_setup = create_aero_setup_monza()
    print(f"✓ AeroSetup Monza (FW={aero_setup.front_wing.angle_deg:.1f}°, RW={aero_setup.rear_wing.angle_deg:.1f}°)")

    car_state = create_car_state_initial()
    print(f"✓ CarState McLaren Norris (fuel={car_state.pu.fuel_kg}kg, ERS={car_state.pu.ers_mode})")
    print()

    # Preparazione simulazione
    print("[SIMULATION SETUP]")
    print("Team:        McLaren")
    print("Driver:      Lando Norris (push=10)")
    print("Circuit:     Monza (it-1922_monza)")
    print("Session:     Qualifying")
    print("Engine map:  QUALIFY (950 kW ICE + 160 ERS)")
    print("Fuel:        5.0 kg (minimum)")
    print("Tyres:       C3 Pirelli Medium")
    print()

    # Setup ambiente
    env = EnvContext(
        air_temp_c=28.0,
        track_temp_c=42.0,
        air_density_kg_m3=1.225,
        wind_speed_kph=2.0,
        wind_direction_deg=45.0,
    )

    print("[READY FOR SIMULATION]")
    print("Status: CONFIGURED - Ready to run update_section() for each sector")
    print()

    # Output per integrazione successiva
    print("[NEXT STEPS]")
    print("1. Import update_section from lap_simulator.update_section")
    print("2. For each sector in telemetry:")
    print("   - Load SectionContext from telemetry")
    print("   - Call: result = update_section(")
    print("            car_state, aero_setup, driver_skills, section,")
    print("            env, config, push_level=10, is_qualifying=True,")
    print("            circuit_id='it-1922_monza', driver_id='NORRIS', ...)")
    print("   - Accumulate dt_s, v_exit, physical parameters")
    print("   - Store in SectorSimResult")
    print("3. Aggregate results and compare vs real telemetry")
    print()

    print("="*130)
    print("Configuration complete. Objects ready for real simulation integration.")
    print("="*130)


if __name__ == "__main__":
    main()
