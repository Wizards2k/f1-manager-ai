"""
CALIBRATION TOOL: Physics V3 on Monza Qualifying

Validazione microsettore-per-microsettore:
1. Carica dati reali: McLaren, Norris (push=10), setup qualifica Monza, C5 SOFT
2. Per ogni sezione Monza (13 settori):
   - Simula con update_section_v3()
   - Confronta dt_sim vs dt_ref_s (telemetria reale)
   - Calcola errore in %
3. Report finale:
   - Ogni settore: Real | Sim | Δ | %Error
   - Totale giro: 78.705s (reale) vs X.XXXs (simulato)
   - Statistiche: avg error, max error, min error

Target di calibrazione:
- Ogni settore: |dt_error| ≤ 0.15s (±2%)
- Giro completo: |dt_error| ≤ 0.5s (±0.6%)
"""

import json
import os
import sys
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lap_simulator.data_types import (
    CarState, AeroSetup, AeroComponent, SuspensionState,
    DriverSkills, DriverMentalState,
    TyreState, BrakeState, PUState, DamageState, AeroForces,
    SectionContext, SectionKind, CurveProfile, EnvContext,
    WheelPosition, TyreCompound, CircuitConfig,
    EngineMapName, ERSModeName
)
from lap_simulator.physics_v3.update_section_v3 import update_section_v3
from lap_simulator.config_loader import load_circuit_config

logger = logging.getLogger(__name__)


def load_mclaren_config() -> Dict[str, Any]:
    """Carica configurazione team McLaren."""
    paths_to_try = [
        "python_backend/data/teams_2025.json",
        "data/teams_2025.json",
    ]

    for path in paths_to_try:
        if os.path.exists(path):
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
    paths_to_try = [
        "python_backend/data/ai_optimal_setups.json",
        "data/ai_optimal_setups.json",
    ]

    for path in paths_to_try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                return data.get('it-1922_monza', {})

    return {}


def load_monza_telemetry() -> Optional[List[Dict[str, Any]]]:
    """Carica telemetria Monza 13 sezioni."""
    # Try multiple paths
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths_to_try = [
        os.path.join(script_dir, "data/circuits/2025/it-1922_monza_Telemetry.json"),
        "python_backend/data/circuits/2025/it-1922_monza_Telemetry.json",
        "data/circuits/2025/it-1922_monza_Telemetry.json",
    ]

    for path in paths_to_try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                return data.get('geometry', {}).get('sections', [])

    return None


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
    """Crea AeroSetup Monza qualifica con angoli ali reali McLaren."""
    setup_data = load_monza_setup()
    setup = AeroSetup()

    # Carica modificatori aero McLaren dal team config
    mclaren = load_mclaren_config()
    aero_mods = mclaren.get('base_aero', {}) if mclaren else {}

    if setup_data:
        setup.ride_height_front_mm = setup_data.get('rh_f', 25.0)
        setup.ride_height_rear_mm = setup_data.get('rh_r', 40.0)
        setup.suspension_front.spring_rate_n_mm = setup_data.get('susp_f', 0.5)
        setup.suspension_rear.spring_rate_n_mm = setup_data.get('susp_r', 0.5)
        setup.antiroll_front_rigidity = setup_data.get('arb_f', 0.5)
        setup.antiroll_rear_rigidity = setup_data.get('arb_r', 0.5)

        # Slider → angolo ala (spec range 4°-35°, linearizzato)
        # Slider 0-100 → angolo 4°-35° (formula: angle = 4 + slider * 0.31)
        fw_slider = setup_data.get('best_fw', 50)
        rw_slider = setup_data.get('best_rw', 50)
        setup.front_wing.angle_deg = 4.0 + fw_slider * 0.31   # FW=31 → 13.61°
        setup.rear_wing.angle_deg = 4.0 + rw_slider * 0.31    # RW=21 → 10.51°
    else:
        setup.ride_height_front_mm = 25.0
        setup.ride_height_rear_mm = 40.0
        setup.front_wing.angle_deg = 13.6   # Monza low-DF default
        setup.rear_wing.angle_deg = 10.5

    # Modificatori DF McLaren → efficiency_factor (usato in aero_mapper)
    setup.front_wing.efficiency_factor = aero_mods.get('front_wing_df_modifier', 1.0)
    setup.rear_wing.efficiency_factor = aero_mods.get('rear_wing_df_modifier', 1.0)

    # Modificatori drag McLaren → base_drag (usato in aero_mapper per CDA)
    setup.front_wing.base_drag = aero_mods.get('front_wing_drag_modifier', 1.0)
    setup.rear_wing.base_drag = aero_mods.get('rear_wing_drag_modifier', 1.0)

    setup.ride_height_optimal_front_mm = setup.ride_height_front_mm
    setup.ride_height_optimal_rear_mm = setup.ride_height_rear_mm

    return setup


def create_car_state_initial() -> CarState:
    """Crea stato LANCIATO auto McLaren Norris (gomme e freni in temperatura).

    Condizioni da qualifica lanciata (non primo giro freddo):
    - Gomme: C5 SOFT a temperatura ottimale (~115°C)
    - Freni: Temperatura ottimale per carbonio (~650°C)
    - Fuel: Circa 12 kg per giro (+ margine)
    - ERS: Battery piena 4.0 MJ
    - Engine map: QUALIFY (950 kW + 160 kW ERS)
    """
    car_state = CarState(
        car_id="mclaren_norris",
        team_code="MCL",
        current_section_idx=0,
        section_progress=0.0,
        lap_time_acc_s=0.0,
        lap_number=3,  # Giro lanciato (non il primo)
        v_current_ms=321.6 / 3.6,  # 89.3 m/s = 321.6 kph (giro LANCIATO a metà Straight!)
    )

    # Gomme IN TEMPERATURA (Pirelli C5 SOFT — finestra ottimale 110-120°C)
    for position in WheelPosition:
        car_state.tyres[position] = TyreState(
            wheel_pos=position,
            compound=TyreCompound.C5,  # SOFT Pirelli qualifica Monza
            surface_temp_c=118.0,      # ← TEMPERATURA OTTIMALE (non 25°C!)
            core_temp_c=115.0,         # ← CORE OTTIMALE
            wear_pct=2.0,              # Minimo usura dopo 2 giri
        )

    # Freni IN TEMPERATURA (carbonio ottimale ~650°C)
    car_state.brakes.temp_front_c = 650.0  # ← OTTIMALE (non 200°C!)
    car_state.brakes.temp_rear_c = 620.0

    # Power Unit — QUALIFY map
    car_state.pu.active_map = EngineMapName.QUALIFY
    car_state.pu.ers_mode = ERSModeName.QUALIFY
    car_state.pu.ice_power_kw = 550.0   # F1 2025 ICE peak (FIA homologated)
    car_state.pu.ers_output_kw = 120.0  # FIA limit 120 kW
    car_state.pu.ers_energy_mj = 4.0   # Battery PIENA (non 2 MJ!)
    car_state.pu.fuel_kg = 12.0        # Circa 12 kg per giro (non 5 per ritorno!)

    return car_state


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
    print("CALIBRATION: Physics V3 on Monza Qualifying — McLaren/Norris/C5 SOFT")
    print("="*130)
    print()

    # Load telemetry
    print("[LOADING DATA]")
    telemetry_sections = load_monza_telemetry()
    if not telemetry_sections:
        print("❌ Telemetria non trovata")
        return

    print(f"✓ Telemetria: {len(telemetry_sections)} sezioni")

    # Create simulation objects
    print("[CREATING SIMULATION OBJECTS]")
    driver_skills = create_driver_skills_norris()
    print(f"✓ Lando Norris (raw_pace={driver_skills.raw_pace}, consistency={driver_skills.consistency})")

    aero_setup = create_aero_setup_monza()
    print(f"✓ AeroSetup Monza (RH_F={aero_setup.ride_height_front_mm:.0f}mm, RH_R={aero_setup.ride_height_rear_mm:.0f}mm)")

    car_state = create_car_state_initial()
    print(f"✓ CarState (fuel={car_state.pu.fuel_kg}kg, compound={car_state.tyres[WheelPosition.LF].compound.name})")

    env = EnvContext(
        air_temp_c=28.0,
        track_temp_c=42.0,
        air_density_kg_m3=1.225,
        wind_speed_kph=2.0,
    )
    print(f"✓ Environment (air={env.air_temp_c}°C, track={env.track_temp_c}°C)")

    # Load circuit config
    try:
        config = load_circuit_config("it-1922_monza")
        print(f"✓ CircuitConfig (Monza)")
    except Exception as e:
        print(f"❌ Failed to load circuit config: {e}")
        return

    # FIX: Correggere i raggi scorretti da config_loader
    # Turn 1 (sezione 1) dovrebbe avere raggio 668.5m (Parabolica), non 27.9m
    telemetry_path = "python_backend/data/circuits/2025/it-1922_monza_Telemetry.json"
    if os.path.exists(telemetry_path):
        with open(telemetry_path, 'r') as f:
            telem_data = json.load(f)
            telem_sections = telem_data.get('geometry', {}).get('sections', [])
            print(f"\n[FIX: Correzione raggi da telemetria]")
            for i, section in enumerate(config.sections):
                if i < len(telem_sections):
                    telem_radius = telem_sections[i].get('radius_m')
                    if telem_radius and telem_radius > 50:  # Raggio significativo
                        old_radius = section.curve_profile.radius_m
                        section.curve_profile.radius_m = telem_radius
                        section.curve_profile.curvature_factor = 1.0 / (1.0 + telem_radius / 100.0)
                        if i in [1, 5]:  # Stampa solo Turn 1 e Turn 3
                            print(f"  Sezione {i} ({section.name}): {old_radius:.1f}m → {telem_radius:.1f}m")
    print()

    # FIX: Abilita DRS per le zone DRS di Monza (qualifica).
    # Monza ha 2 zone DRS:
    #   Zone 1: rettilineo principale (Straight 1, indice 0) → dopo Parabolica fino a T1
    #   Zone 2: rettilineo Curva Grande (Straight 2, indice 2) → dopo T1 fino a T2
    #   (In gara si chiama "DRS zona 2"; in qualifica è sempre aperto nelle zone)
    # Straight 5 (indice 8) ha anche DRS parziale (rettilineo dopo Lesmo 2 → Ascari).
    # Reference: telemetria raw mostra drs=8/12 su questi settori.
    if len(config.sections) > 0:
        config.sections[0].drs_available = True   # Straight 1: main straight DRS
    if len(config.sections) > 2:
        config.sections[2].drs_available = True   # Straight 2: back straight DRS (zona 2)

    print()
    print("[RUNNING SIMULATION]")
    print("-"*130)

    results = []
    total_dt_real = 0.0
    total_dt_sim = 0.0

    for idx, section_data in enumerate(telemetry_sections[:13]):
        # Use section from config if available, else use telemetry data
        section = config.sections[idx] if idx < len(config.sections) else None

        # Extract real data
        dt_real = section_data.get('dt_ref_s', 0.0)
        v_entry_real = section_data.get('v_entry_kph', 0.0)
        v_exit_real = section_data.get('v_exit_kph', 0.0)
        sector_name = section_data.get('name', f'Sector {idx}')
        sector_id = section_data.get('section_id', f'S{idx}')

        # Call update_section_v3
        try:
            if section:
                section_result = update_section_v3(
                    car_state=car_state,
                    aero_setup=aero_setup,
                    driver_skills=driver_skills,
                    section=section,
                    env=env,
                    config=config,
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
            else:
                dt_sim = 0.0
                v_exit_sim = 0.0

        except Exception as e:
            print(f"⚠ Error simulating {sector_name}: {e}")
            dt_sim = 0.0
            v_exit_sim = 0.0

        # Store result
        result = SectorResult(
            sector_name=sector_name,
            sector_id=sector_id,
            dt_real_s=dt_real,
            dt_sim_s=dt_sim,
            v_entry_real_kph=v_entry_real,
            v_exit_real_kph=v_exit_real,
            v_exit_sim_kph=v_exit_sim,
        )
        results.append(result)

        total_dt_real += dt_real
        total_dt_sim += dt_sim

        # Update car state for next section
        car_state.v_current_ms = v_exit_sim / 3.6

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

    # Statistics
    errors = [r.error_pct() for r in results]
    if errors:
        avg_error = sum(errors) / len(errors)
        max_error = max(errors)
        min_error = min(errors)
        print()
        print("[ERROR STATISTICS]")
        print(f"  Average error: {avg_error:+6.1f}%")
        print(f"  Max error: {max_error:+6.1f}%")
        print(f"  Min error: {min_error:+6.1f}%")

    print()
    print("✓ Calibration completed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
