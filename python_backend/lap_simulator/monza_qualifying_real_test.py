"""
REAL MONZA QUALIFYING SIMULATION

Simulazione VERA e COMPLETA che:
1. Carica dati McLaren, Norris (push=10), setup Monza qualifica
2. Per ogni sezione Monza (13 settori):
   - Crea SectionContext dal telemetry reale
   - Chiama update_section() del motore del gioco
   - Accumula tempi, velocità, parametri fisici
   - Confronta vs telemetria reale settore per settore

Expected: Monza 79-81s (target qualifica)
"""

import json
import os
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lap_simulator.data_types import (
    CarState, AeroSetup, AeroComponent, SuspensionState,
    DriverSkills, DriverMentalState,
    TyreState, BrakeState, PUState, DamageState, AeroForces,
    SectionContext, SectionKind, CurveProfile, EnvContext,
    WheelPosition, TyreCompound, CircuitConfig,
    EngineMapName, ERSModeName
)
from lap_simulator.update_section import update_section

logger = logging.getLogger(__name__)


def load_mclaren_config() -> Dict[str, Any]:
    """Carica configurazione team McLaren."""
    path = "data/teams_2025.json"
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        data = json.load(f)
        for team in data.get('teams', []):
            if team.get('team_id') == 'mclaren':
                return team
    return None


def load_norris_skills() -> Dict[str, int]:
    """Carica skills Lando Norris."""
    return {
        'velocita': 93,
        'consumo': 88,
        'qualifica': 94,
        'gara': 93,
        'aggressivita': 86,
        'gestione_carburante': 88,
        'ricerca_assetto': 85,
        'costanza': 94,
        'perfezionismo': 88,
    }


def load_monza_setup() -> Dict[str, Any]:
    """Carica setup Monza qualifica."""
    path = "data/ai_optimal_setups.json"
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        data = json.load(f)
        return data.get('it-1922_monza', {})


def load_monza_telemetry() -> Optional[List[Dict[str, Any]]]:
    """Carica telemetria Monza 13 sezioni."""
    path = "data/circuits/2025/it-1922_monza_Telemetry.json"
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        data = json.load(f)
        return data.get('geometry', {}).get('sections', [])


def create_driver_skills_norris() -> DriverSkills:
    """Crea DriverSkills Lando Norris."""
    skills_data = load_norris_skills()
    return DriverSkills(
        raw_pace=skills_data['velocita'],
        race_craft=skills_data['gara'],
        aggression=skills_data['aggressivita'],
        consistency=skills_data['costanza'],
        tyre_management=skills_data['gestione_carburante'],
        overtaking_skill=80,
        defending_skill=80,
        wet_skill=75,
        smoothness=skills_data['perfezionismo'],
        setup_finding=skills_data['ricerca_assetto'],
    )


def create_aero_setup_monza() -> AeroSetup:
    """Crea AeroSetup Monza qualifica."""
    setup_data = load_monza_setup()
    setup = AeroSetup()

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

    for position in WheelPosition:
        car_state.tyres[position] = TyreState(
            wheel_pos=position,
            compound=TyreCompound.C3,
            surface_temp_c=25.0,
            core_temp_c=25.0,
            wear_pct=0.0,
        )

    car_state.brakes.temp_front_c = 200.0
    car_state.brakes.temp_rear_c = 200.0

    car_state.pu.active_map = EngineMapName.QUALIFY
    car_state.pu.ers_mode = ERSModeName.QUALIFY
    car_state.pu.fuel_kg = 5.0

    return car_state


def create_section_context_from_telemetry(
    section_data: Dict[str, Any],
    idx: int
) -> SectionContext:
    """Crea SectionContext dalla telemetria."""

    section_id = section_data.get('section_id', f'S{idx}')
    name = section_data.get('name', f'Section {idx}')
    kind_str = section_data.get('kind', 'STRAIGHT')

    # Mappiamo il tipo a SectionKind
    try:
        kind = SectionKind[kind_str.upper()]
    except KeyError:
        kind = SectionKind.STRAIGHT

    length_m = section_data.get('length_m', 100.0)
    v_entry_kph = section_data.get('v_entry_kph', 200.0)
    v_exit_kph = section_data.get('v_exit_kph', 200.0)
    v_min_kph = section_data.get('v_min_kph', v_entry_kph)
    v_max_kph = section_data.get('v_max_kph', v_exit_kph)
    v_avg_kph = section_data.get('v_avg_kph', (v_entry_kph + v_exit_kph) / 2)
    dt_ref = section_data.get('dt_ref_s', 0.0)
    radius_m = section_data.get('radius_m', 0.0) or 0.0

    return SectionContext(
        section_id=section_id,
        name=name,
        kind=kind,
        length_m=length_m,
        v_base_kph=v_avg_kph,
        v_entry_kph=v_entry_kph,
        v_exit_kph=v_exit_kph,
        v_min_kph=v_min_kph,
        v_max_kph=v_max_kph,
        dt_ref_s=dt_ref,
        curve_profile=CurveProfile(radius_m=radius_m if radius_m > 0 else None),
    )


@dataclass
class SectorResult:
    """Risultato simulazione settore."""
    sector_name: str
    sector_id: str

    dt_real_s: float
    dt_sim_s: float

    v_entry_real_kph: float
    v_exit_real_kph: float
    v_exit_sim_kph: float

    def error_pct(self) -> float:
        if self.dt_real_s > 0:
            return (self.dt_sim_s - self.dt_real_s) / self.dt_real_s * 100
        return 0.0

    def summary(self) -> str:
        return (
            f"{self.sector_name:<20} "
            f"Real: {self.dt_real_s:6.3f}s  "
            f"Sim: {self.dt_sim_s:6.3f}s  "
            f"Δ: {self.dt_sim_s - self.dt_real_s:+6.3f}s ({self.error_pct():+6.1f}%)"
        )


def main():
    print("="*130)
    print("REAL MONZA QUALIFYING SIMULATION — McLaren/Norris/Universal Motor")
    print("="*130)
    print()

    # Load telemetry
    print("[LOADING DATA]")
    telemetry_sections = load_monza_telemetry()
    if not telemetry_sections:
        print("❌ Telemetria non trovata")
        return

    print(f"✓ Telemetria: {len(telemetry_sections)} sezioni")
    print()

    # Create simulation objects
    print("[CREATING REAL OBJECTS]")
    driver_skills = create_driver_skills_norris()
    print(f"✓ Lando Norris (raw_pace={driver_skills.raw_pace}, consistency={driver_skills.consistency})")

    aero_setup = create_aero_setup_monza()
    print(f"✓ AeroSetup Monza (RH_F={aero_setup.ride_height_front_mm:.0f}mm, RH_R={aero_setup.ride_height_rear_mm:.0f}mm)")

    car_state = create_car_state_initial()
    print(f"✓ CarState (fuel={car_state.pu.fuel_kg}kg, map={car_state.pu.active_map.value})")

    env = EnvContext(
        air_temp_c=28.0,
        track_temp_c=42.0,
        air_density_kg_m3=1.225,
        wind_speed_kph=2.0,
    )
    print(f"✓ Environment (air={env.air_temp_c}°C, track={env.track_temp_c}°C)")
    print()

    # Create circuit config
    circuit_config = CircuitConfig(
        circuit_id="it-1922_monza",
        circuit_name="Monza",
        circuit_length_m=5793.0,
    )
    print(f"✓ CircuitConfig (Monza, {circuit_config.circuit_length_m:.0f}m)")
    print()

    print("[RUNNING SIMULATION]")
    print("-"*130)

    results = []
    total_dt_real = 0.0
    total_dt_sim = 0.0

    for idx, section_data in enumerate(telemetry_sections[:13]):
        # Create section context
        section = create_section_context_from_telemetry(section_data, idx)

        # Call update_section
        try:
            section_result = update_section(
                car_state=car_state,
                aero_setup=aero_setup,
                driver_skills=driver_skills,
                section=section,
                env=env,
                config=circuit_config,
                push_level=10,
                is_qualifying=True,
                circuit_id="it-1922_monza",
                driver_id="NORRIS",
                lap_number=1,
                airflow_penalty=0.0,
                traffic_v_max_kph=0.0,
            )

            dt_sim = section_result.dt_s
            v_exit_sim = section_result.v_exit_kph

        except Exception as e:
            print(f"⚠ Error simulating {section.name}: {e}")
            dt_sim = 0.0
            v_exit_sim = 0.0

        # Extract real data
        dt_real = section_data.get('dt_ref_s', 0.0)
        v_entry_real = section_data.get('v_entry_kph', 0.0)
        v_exit_real = section_data.get('v_exit_kph', 0.0)

        # Store result
        result = SectorResult(
            sector_name=section.name,
            sector_id=section.section_id,
            dt_real_s=dt_real,
            dt_sim_s=dt_sim,
            v_entry_real_kph=v_entry_real,
            v_exit_real_kph=v_exit_real,
            v_exit_sim_kph=v_exit_sim,
        )
        results.append(result)

        total_dt_real += dt_real
        total_dt_sim += dt_sim

        print(result.summary())

    print("-"*130)
    print()

    print("[LAP TIME SUMMARY]")
    print("="*130)
    print(f"Real telemetry:  {total_dt_real:7.3f} s")
    print(f"Simulated:       {total_dt_sim:7.3f} s")
    print(f"Difference:      {total_dt_sim - total_dt_real:+7.3f} s ({(total_dt_sim - total_dt_real) / total_dt_real * 100:+6.2f}%)")
    print()

    if 79 <= total_dt_sim <= 81:
        print("✓✓✓ TARGET ACHIEVED (79-81s range for Monza qualifying)")
    else:
        print(f"Status: {total_dt_sim:.1f}s (target: 79-81s)")

    print()
    print("✓ Simulation completed")


if __name__ == "__main__":
    main()
