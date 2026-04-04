"""
CALIBRATION TOOL: Physics V3 on Monaco Qualifying

Validazione microsettore-per-microsettore:
1. Carica dati reali: McLaren, Norris (push=10), setup qualifica Monaco, C3 SOFT
2. Per ogni sezione Monaco (19 settori):
   - Simula con update_section_v3()
   - Confronta dt_sim vs dt_ref_s (telemetria reale)
   - Calcola errore in %
3. Report finale con statistiche

Target di calibrazione:
- Ogni settore: |dt_error| ≤ 5%
- Giro completo: target 69.954s (Norris 2025)
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
from lap_simulator.physics_v3.update_section_v3 import update_section_v3
from lap_simulator.config_loader import load_circuit_config

logger = logging.getLogger(__name__)


def load_mclaren_config() -> Dict[str, Any]:
    for path in ["python_backend/data/teams_2025.json", "data/teams_2025.json"]:
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            for team in data.get('teams', []):
                if team.get('team_id') == 'mclaren':
                    return team
    return None


def load_monaco_setup() -> Dict[str, Any]:
    for path in ["python_backend/data/ai_optimal_setups.json", "data/ai_optimal_setups.json"]:
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            return data.get('mc-1929_monaco', {})
    return {}


def load_monaco_telemetry() -> Optional[List[Dict[str, Any]]]:
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = [
        os.path.join(script_dir, "data/circuits/2025/mc-1929_monaco_Telemetry.json"),
        "python_backend/data/circuits/2025/mc-1929_monaco_Telemetry.json",
        "data/circuits/2025/mc-1929_monaco_Telemetry.json",
    ]
    for path in paths:
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            return data.get('geometry', {}).get('sections', [])
    return None


def create_driver_skills_norris() -> DriverSkills:
    return DriverSkills(
        raw_pace=93, race_craft=93, aggression=86, consistency=94,
        tyre_management=88, overtaking_skill=80, defending_skill=80,
        wet_skill=75, smoothness=88, setup_finding=85,
    )


def create_aero_setup_monaco() -> AeroSetup:
    """Crea AeroSetup Monaco qualifica con angoli ali reali McLaren."""
    setup_data = load_monaco_setup()
    setup = AeroSetup()

    mclaren = load_mclaren_config()
    aero_mods = mclaren.get('base_aero', {}) if mclaren else {}

    fw_slider = setup_data.get('best_fw', 95)
    rw_slider = setup_data.get('best_rw', 94)

    # Slider [1-100] → angolo [4°-35°] (spec Gemini)
    setup.front_wing.angle_deg = 4.0 + (fw_slider - 1) / 99.0 * 31.0   # ~33.4°
    setup.rear_wing.angle_deg = 4.0 + (rw_slider - 1) / 99.0 * 31.0    # ~33.1°

    setup.front_wing.efficiency_factor = aero_mods.get('front_wing_df_modifier', 1.0)
    setup.front_wing.base_drag = aero_mods.get('front_wing_drag_modifier', 1.0)
    setup.rear_wing.efficiency_factor = aero_mods.get('rear_wing_df_modifier', 1.0)
    setup.rear_wing.base_drag = aero_mods.get('rear_wing_drag_modifier', 1.0)

    rh_f = setup_data.get('rh_f', 45.0)
    rh_r = setup_data.get('rh_r', 60.0)
    setup.ride_height_front_mm = rh_f
    setup.ride_height_rear_mm = rh_r
    setup.ride_height_optimal_front_mm = rh_f
    setup.ride_height_optimal_rear_mm = rh_r
    setup.antiroll_front_rigidity = setup_data.get('arb_f', 0.5)
    setup.antiroll_rear_rigidity = setup_data.get('arb_r', 0.5)

    return setup


def create_car_state_initial() -> CarState:
    """McLaren Norris — qualifica Monaco lanciata, C3 SOFT."""
    car_state = CarState(
        car_id="mclaren_norris",
        team_code="MCL",
        current_section_idx=0,
        section_progress=0.0,
        lap_time_acc_s=0.0,
        lap_number=3,
        v_current_ms=280.0 / 3.6,   # entry speed Monaco Straight 1
    )

    # C3 SOFT Monaco — finestra ~100-115°C (mescola più dura rispetto a Monza)
    for position in WheelPosition:
        car_state.tyres[position] = TyreState(
            wheel_pos=position,
            compound=TyreCompound.C3,
            surface_temp_c=112.0,
            core_temp_c=108.0,
            wear_pct=2.0,
        )

    # Freni Monaco: temperature più alte per i numerosi frenataggi
    car_state.brakes.temp_front_c = 700.0
    car_state.brakes.temp_rear_c = 660.0

    car_state.pu.active_map = EngineMapName.QUALIFY
    car_state.pu.ers_mode = ERSModeName.QUALIFY
    car_state.pu.ice_power_kw = 550.0
    car_state.pu.ers_output_kw = 120.0
    car_state.pu.ers_energy_mj = 4.0
    car_state.pu.fuel_kg = 12.0

    return car_state


@dataclass
class SectorResult:
    sector_name: str
    sector_id: str
    dt_real_s: float
    dt_sim_s: float
    v_entry_real_kph: float
    v_exit_real_kph: float
    v_exit_sim_kph: float

    def error_pct(self) -> float:
        return (self.dt_sim_s - self.dt_real_s) / self.dt_real_s * 100 if self.dt_real_s > 0 else 0.0

    def summary(self) -> str:
        return (
            f"{self.sector_name:<20} "
            f"Real: {self.dt_real_s:6.3f}s  "
            f"Sim: {self.dt_sim_s:6.3f}s  "
            f"Δ: {self.dt_sim_s - self.dt_real_s:+6.3f}s ({self.error_pct():+6.1f}%)"
        )


def main():
    print("=" * 130)
    print("CALIBRATION: Physics V3 on Monaco Qualifying — McLaren/Norris/C3 SOFT")
    print("=" * 130)
    print()

    print("[LOADING DATA]")
    telemetry_sections = load_monaco_telemetry()
    if not telemetry_sections:
        print("❌ Telemetria Monaco non trovata")
        return
    print(f"✓ Telemetria: {len(telemetry_sections)} sezioni")

    print("[CREATING SIMULATION OBJECTS]")
    driver_skills = create_driver_skills_norris()
    print(f"✓ Lando Norris (raw_pace={driver_skills.raw_pace}, consistency={driver_skills.consistency})")

    aero_setup = create_aero_setup_monaco()
    print(f"✓ AeroSetup Monaco (FW={aero_setup.front_wing.angle_deg:.1f}°, RW={aero_setup.rear_wing.angle_deg:.1f}°, "
          f"RH_F={aero_setup.ride_height_front_mm:.0f}mm, RH_R={aero_setup.ride_height_rear_mm:.0f}mm)")

    # Stampa aero params
    from lap_simulator.physics_v3.aero_mapper import map_aero_setup
    env_check = EnvContext(air_temp_c=22.0, track_temp_c=38.0, air_density_kg_m3=1.220, wind_speed_kph=3.0)
    ap = map_aero_setup(aero_setup, env_check, v_estimate_kph=150.0, fuel_kg=12.0)
    print(f"  → CLA={ap.CLA:.3f} CDA={ap.CDA:.3f} balance={ap.aero_balance:.3f} "
          f"us_pen={ap.understeer_grip_penalty:.3f} os_pen={ap.oversteer_grip_penalty:.3f}")

    car_state = create_car_state_initial()
    print(f"✓ CarState (fuel={car_state.pu.fuel_kg}kg, compound={car_state.tyres[WheelPosition.LF].compound.name})")

    env = EnvContext(
        air_temp_c=22.0,
        track_temp_c=38.0,
        air_density_kg_m3=1.220,
        wind_speed_kph=3.0,
    )
    print(f"✓ Environment (air={env.air_temp_c}°C, track={env.track_temp_c}°C)")

    try:
        config = load_circuit_config("mc-1929_monaco")
        print(f"✓ CircuitConfig (Monaco, {len(config.sections)} sezioni)")
    except Exception as e:
        print(f"❌ Failed to load circuit config: {e}")
        return

    # FIX: Correggere i raggi da telemetria.
    # I raggi nei waypoints HD Monaco sono errati (es. Turn 4 r=11m invece di 320m).
    # La telemetria per-sezione ha il raggio corretto. Sovrascriviamo:
    # 1. curve_profile.radius_m (usato dall'integratore analitico)
    # 2. radius_m di OGNI waypoint della sezione (usato dall'integratore HD)
    telem_path = "python_backend/data/circuits/2025/mc-1929_monaco_Telemetry.json"
    if os.path.exists(telem_path):
        with open(telem_path) as f:
            telem_data = json.load(f)
        telem_secs = telem_data.get('geometry', {}).get('sections', [])
        print(f"\n[FIX: Correzione raggi da telemetria → waypoints HD]")
        corrected = 0
        for i, section in enumerate(config.sections):
            if i < len(telem_secs):
                r = telem_secs[i].get('radius_m')
                if r and r > 10:
                    # Aggiorna curve_profile
                    section.curve_profile.radius_m = r
                    section.curve_profile.curvature_factor = 1.0 / (1.0 + r / 100.0)
                    # Aggiorna tutti i waypoints della sezione
                    if section.waypoints:
                        for wp in section.waypoints:
                            if wp.radius_m is not None and wp.radius_m < r * 0.5:
                                # solo se il raggio del wp è molto più piccolo → errato
                                wp.radius_m = r
                    corrected += 1
                    print(f"  {section.name}: r={r:.0f}m (v_min={section.v_min_kph:.0f} kph)")
        print(f"  → {corrected} sezioni corrette")

    # Monaco non ha zone DRS
    print()

    print("[RUNNING SIMULATION]")
    print("-" * 130)

    results = []
    total_dt_real = 0.0
    total_dt_sim = 0.0

    for idx, section_data in enumerate(telemetry_sections[:19]):
        section = config.sections[idx] if idx < len(config.sections) else None
        dt_real = section_data.get('dt_ref_s', 0.0)
        v_entry_real = section_data.get('v_entry_kph', 0.0)
        v_exit_real = section_data.get('v_exit_kph', 0.0)
        sector_name = section_data.get('name', f'Sector {idx}')
        sector_id = section_data.get('section_id', f'S{idx}')

        dt_sim = 0.0
        v_exit_sim = 0.0

        if section:
            try:
                section_result = update_section_v3(
                    car_state=car_state,
                    aero_setup=aero_setup,
                    driver_skills=driver_skills,
                    section=section,
                    env=env,
                    config=config,
                    push_level=10,
                    is_qualifying=True,
                    circuit_id="mc-1929_monaco",
                    driver_id="NORRIS",
                    lap_number=1,
                    airflow_penalty=0.0,
                    traffic_v_max_kph=0.0,
                )
                dt_sim = section_result.dt_s
                v_exit_sim = section_result.v_exit_kph
            except Exception as e:
                print(f"⚠ Error simulating {sector_name}: {e}")

        result = SectorResult(
            sector_name=sector_name, sector_id=sector_id,
            dt_real_s=dt_real, dt_sim_s=dt_sim,
            v_entry_real_kph=v_entry_real, v_exit_real_kph=v_exit_real,
            v_exit_sim_kph=v_exit_sim,
        )
        results.append(result)
        total_dt_real += dt_real
        total_dt_sim += dt_sim

        car_state.v_current_ms = v_exit_sim / 3.6

        print(result.summary())

    print("-" * 130)
    print()
    print("[LAP TIME SUMMARY]")
    print("=" * 130)
    print(f"Reference (Norris 2025):  69.954 s")
    print(f"Real telemetry:          {total_dt_real:7.3f} s")
    print(f"Simulated:               {total_dt_sim:7.3f} s")
    print(f"Difference:              {total_dt_sim - total_dt_real:+7.3f} s "
          f"({(total_dt_sim - total_dt_real) / total_dt_real * 100:+6.2f}%)")
    print()

    if 68 <= total_dt_sim <= 73:
        print("✓✓✓ TARGET ACHIEVED (68-73s range for Monaco qualifying)")
    else:
        print(f"Status: {total_dt_sim:.1f}s (target: 68-73s)")

    errors = [r.error_pct() for r in results]
    print(f"\n[ERROR STATISTICS]")
    print(f"  Average error:  {sum(errors)/len(errors):+6.1f}%")
    print(f"  Max error:      {max(errors):+6.1f}%")
    print(f"  Min error:      {min(errors):+6.1f}%")
    sectors_ok = sum(1 for e in errors if abs(e) <= 5.0)
    print(f"  Sectors ≤5%:    {sectors_ok}/{len(errors)}")
    print()
    print("✓ Calibration completed")


if __name__ == "__main__":
    main()
