"""
Adapter – bidirectional mapping between game models (RaceCar) and
LapSimulator models (CarEntry, LapResult).

Fase C: Race Engine Integration
"""
from __future__ import annotations

import logging
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models import RaceCar, TireCompound as GameTireCompound

from lap_simulator.data_types import (
    AeroSetup,
    CarState as SimCarState,
    DriverSkills,
    EngineMapName,
    TyreCompound,
    TyreState,
    WheelPosition,
)
from lap_simulator.lap_simulator import CarEntry, LapResult
from services.setup_engine_service import SetupEngineService

try:
    import config
except ImportError:  # pragma: no cover - optional during tests
    config = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Compound mapping: game ↔ simulator
# ---------------------------------------------------------------------------

# Game uses SOFT/MEDIUM/HARD; simulator uses C1-C6.
# Default event mapping (configurable per event later).
_GAME_TO_SIM_COMPOUND = {
    "soft": TyreCompound.C4,
    "medium": TyreCompound.C3,
    "hard": TyreCompound.C2,
    "intermediate": TyreCompound.INTERMEDIATE,
    "wet": TyreCompound.WET,
}

_SIM_TO_GAME_COMPOUND = {
    TyreCompound.C1: "hard",
    TyreCompound.C2: "hard",
    TyreCompound.C3: "medium",
    TyreCompound.C4: "soft",
    TyreCompound.C5: "soft",
    TyreCompound.C6: "soft",
    TyreCompound.INTERMEDIATE: "intermediate",
    TyreCompound.WET: "wet",
}


def game_compound_to_sim(game_compound) -> TyreCompound:
    """Convert game TireCompound to simulator TyreCompound."""
    val = game_compound.value if hasattr(game_compound, "value") else str(game_compound)
    return _GAME_TO_SIM_COMPOUND.get(val.lower(), TyreCompound.C3)


def sim_compound_to_game(sim_compound: TyreCompound) -> str:
    """Convert simulator TyreCompound to game compound string."""
    return _SIM_TO_GAME_COMPOUND.get(sim_compound, "medium")


# ---------------------------------------------------------------------------
# Pilot skills → DriverSkills
# ---------------------------------------------------------------------------

def pilot_to_driver_skills(pilot) -> DriverSkills:
    """
    Map game Pilota attributes to LapSimulator DriverSkills.

    Pilota has: velocita, sorpasso, aggressivita, consumo_gomme,
    qualifica, costanza, gara, ricerca_assetto, gestione_carburante,
    stile_sottosterzo, stile_sovrasterzo (all 1-100).
    """
    return DriverSkills(
        raw_pace=getattr(pilot, "velocita", 70),
        race_craft=getattr(pilot, "gara", 70),
        aggression=getattr(pilot, "aggressivita", 50),
        consistency=getattr(pilot, "costanza", 70),
        tyre_management=getattr(pilot, "consumo_gomme", 70),
        overtaking_skill=getattr(pilot, "sorpasso", 60),
        defending_skill=max(50, 100 - getattr(pilot, "aggressivita", 50)),
        wet_skill=60,
        smoothness=getattr(pilot, "stile_sottosterzo", 60),
        setup_finding=getattr(pilot, "ricerca_assetto", 60),
    )
def _default_setup_value(field: str, fallback: int = 50) -> int:
    """Lazy import DEFAULT_SETUP_CONFIG to avoid circular imports."""
    try:
        from models import DEFAULT_SETUP_CONFIG  # type: ignore
        return int(DEFAULT_SETUP_CONFIG.get(field, fallback))
    except Exception:  # pragma: no cover - keep simulation running on import errors
        return fallback


def _compute_brake_duct_opening(car, circuit_id: Optional[str] = None) -> float:
    """Map the saved setup slider to the physical duct opening (0-1 range)."""
    setup = getattr(car, "player_config", {}).get("setup", {})
    slider_value = setup.get("brake_duct")
    if slider_value is None:
        slider_value = _default_setup_value("brake_duct", 50)

    try:
        slider = max(0, min(100, int(slider_value)))
    except (TypeError, ValueError):
        slider = 50

    circuit_code = circuit_id or (getattr(config, "current_circuit", None) if config else None)

    min_open = 0.25
    max_open = 0.7
    try:
        _, mapping = SetupEngineService.get_circuit_mapping(circuit_code)
        cfg = mapping.get("brake_duct") if isinstance(mapping, dict) else None
        if isinstance(cfg, dict):
            min_open = float(cfg.get("min_open", min_open))
            max_open = float(cfg.get("max_open", max_open))
    except Exception:  # pragma: no cover - mapping fallback
        pass

    opening = min_open + (max_open - min_open) * (slider / 100.0)
    return max(0.0, min(1.0, opening))


# ---------------------------------------------------------------------------
# RaceCar → CarEntry
# ---------------------------------------------------------------------------

def _build_aero_setup(auto, base: Optional[AeroSetup] = None) -> AeroSetup:
    setup = base or AeroSetup()
    if not auto:
        return setup

    pkg = getattr(auto, "aero_package", None)

    def _apply(surface_obj, aero_surface):
        if not aero_surface or surface_obj is None:
            return
        surface_obj.base_downforce = getattr(aero_surface, "df_coeff", surface_obj.base_downforce)
        surface_obj.base_drag = getattr(aero_surface, "drag_coeff", surface_obj.base_drag)
        angle = getattr(aero_surface, "angolo_inclinazione", None)
        if angle is not None:
            surface_obj.angle_deg = angle

    if pkg:
        _apply(setup.front_wing, getattr(pkg, "ala_anteriore", None))
        _apply(setup.rear_wing, getattr(pkg, "ala_posteriore", None))
        _apply(setup.front_floor, getattr(pkg, "fondo_anteriore", None))
        _apply(setup.rear_floor, getattr(pkg, "fondo_posteriore", None))
        _apply(setup.sidepods, getattr(pkg, "sidepods", None))
        _apply(setup.engine_cover, getattr(pkg, "cofano_motore", None))
        _apply(setup.beam_wing, getattr(pkg, "beam_wing", None))
        _apply(setup.b_wing, getattr(pkg, "b_wing", None))

    suspension = getattr(auto, "suspension", None)
    if suspension:
        setup.suspension_front.rigidity = suspension.stiffness_front / 200.0
        setup.suspension_rear.rigidity = suspension.stiffness_rear / 200.0
        setup.suspension_front.efficiency = suspension.antiroll_front / 200.0
        setup.suspension_rear.efficiency = suspension.antiroll_rear / 200.0
        setup.antiroll_front_rigidity = suspension.antiroll_front / 200.0
        setup.antiroll_rear_rigidity = suspension.antiroll_rear / 200.0

    ride_height = getattr(auto, "ride_height", None)
    if ride_height:
        setup.ride_height_front_mm = ride_height.front_mm
        setup.ride_height_rear_mm = ride_height.rear_mm
        setup.ride_height_optimal_front_mm = ride_height.front_mm
        setup.ride_height_optimal_rear_mm = ride_height.rear_mm

    return setup


def _resolve_engine_map(car) -> EngineMapName:
    # Game stores ICE mode as string (Save/Standard/Push) → map to EngineMapName
    mapping = {
        "save": EngineMapName.ECONOMY,
        "standard": EngineMapName.STANDARD,
        "push": EngineMapName.RICH,
        "qualy": EngineMapName.QUALY,
    }
    ice_mode = getattr(car, "ice_mode", "standard")
    return mapping.get(str(ice_mode).lower(), EngineMapName.STANDARD)


def _build_sim_state(car_id: str, car) -> SimCarState:
    state = SimCarState(car_id=car_id)
    state.brakes.duct_opening = _compute_brake_duct_opening(car)

    # Tyres
    game_compound = getattr(car, "current_tire", None)
    sim_compound = game_compound_to_sim(game_compound) if game_compound else TyreCompound.C3
    state.tyres = {
        wp: TyreState(wheel_pos=wp, compound=sim_compound) for wp in WheelPosition
    }
    temps = getattr(car, "tire_temps", {}) or {}
    wear = getattr(car, "tire_wear", None)
    for wp, tyre in state.tyres.items():
        key = wp.name.lower()
        if key in temps:
            tyre.surface_temp_c = temps[key]
        if wear is not None:
            tyre.wear_pct = max(0.0, min(1.0, wear)) * 100.0

    # Power Unit
    team = getattr(car, "team", None)
    power_unit = getattr(team, "power_unit", None)
    map_name = _resolve_engine_map(car)
    if power_unit:
        fuel_pct = max(1, min(100, getattr(car, "fuel_percent", 100)))
        fuel_load = power_unit.fuel_capacity_kg * (fuel_pct / 100.0)
        pu_state = power_unit.create_state(fuel_kg=fuel_load, map_name=map_name)
        state.pu = pu_state
    state.ers_mode = getattr(car, "ers_mode", state.ers_mode)

    return state


def racecar_to_car_entry(
    car,
    aero_setup: Optional[AeroSetup] = None,
) -> CarEntry:
    """
    Create a LapSimulator CarEntry from a game RaceCar.

    Args:
        car: RaceCar instance from game models.
        aero_setup: Optional AeroSetup (from SetupEngineService or AI seed).
                     If None, uses default.
    """
    car_id = str(car.driver_number)
    skills = pilot_to_driver_skills(car.pilot)
    auto = getattr(car.team, "auto", None)
    setup = aero_setup or _build_aero_setup(auto)
    if setup is aero_setup and auto:
        # Ensure base aero values exist even if external setup provided
        setup = _build_aero_setup(auto, base=setup)

    # Map push level: game pace_level 1-10 → sim push_level 0.90-1.10
    pace = getattr(car, "pace_level", 5)
    push_level = 0.90 + (pace - 1) * (0.20 / 9)  # 1→0.90, 5→0.989, 10→1.10

    state = _build_sim_state(car_id, car)

    # Calculate team penalties (AI + player use same logic)
    delta_aero = 0.0
    delta_grip = 0.0
    import logging
    logger = logging.getLogger(__name__)
    
    is_ai = not getattr(car, 'is_player_controlled', False)
    logger.info("DEBUG adapter: car_id=%s is_ai=%s", car_id, is_ai)

    try:
        from utils.team_performance import compute_team_penalties
        from lap_simulator.config_loader import load_circuit_config

        # Get circuit config
        circuit_config = None
        try:
            import config
            current_circuit = getattr(config, 'current_circuit', None)
            if current_circuit:
                circuit_config = load_circuit_config(current_circuit)
            else:
                logger.warning("No current_circuit found in config")
        except Exception as e:
            logger.warning("Failed to load circuit config: %s", e)

        # Determine team code
        team_code = None
        team_name = getattr(car.team, 'nome_scuderia', 'Unknown') if car.team else 'Unknown'
        sigla = getattr(car.team, 'sigla_scuderia', None) if car.team else None
        if sigla:
            team_code = sigla.upper()

        driver_team_map = {
            1: 'RBR',   # Max Verstappen
            22: 'RBR',  # Yuki Tsunoda  
            63: 'MER',  # George Russell
            12: 'MER',  # Andrea Kimi Antonelli
            4: 'MCL',   # Lando Norris
            81: 'MCL',  # Oscar Piastri
            14: 'AST',  # Fernando Alonso
            18: 'AST',  # Lance Stroll
            10: 'ALP',  # Pierre Gasly
            43: 'ALP',  # Franco Colapinto
            23: 'WIL',  # Alexander Albon
            55: 'WIL',  # Carlos Sainz
            30: 'RB',   # Liam Lawson
            6: 'RB',    # Isack Hadjar
            27: 'SAU',  # Nico Hülkenberg
            5: 'SAU',   # Gabriel Bortoleto
            31: 'HAAS', # Esteban Ocon
            87: 'HAAS', # Oliver Bearman
        }
        if not team_code:
            team_code = driver_team_map.get(int(car_id))

        logger.info(
            "DEBUG adapter: car_id=%s team_name=%s team_code=%s is_ai=%s",
            car_id,
            team_name,
            team_code,
            is_ai,
        )

        if team_code:
            delta_aero, delta_grip = compute_team_penalties(team_code, circuit_config)
            logger.info(
                "DEBUG adapter: computed penalties car_id=%s delta_aero=%.4f delta_grip=%.4f",
                car_id,
                delta_aero,
                delta_grip,
            )
        else:
            logger.warning("DEBUG adapter: unable to resolve team_code for %s", car_id)
    except Exception as exc:
        logger.error("Failed to compute team penalties for %s: %s", car_id, exc, exc_info=True)

    return CarEntry(
        car_id=car_id,
        state=state,
        aero_setup=setup,
        driver_skills=skills,
        push_level=push_level,
        delta_aero=delta_aero,
        delta_grip=delta_grip,
        apply_baseline_delta=True,
    )


# ---------------------------------------------------------------------------
# LapResult → RaceCar (update in place)
# ---------------------------------------------------------------------------

def apply_lap_result_to_racecar(car, lap_result: LapResult, circuit_length_m: float = 5725.0) -> None:
    """
    Update a game RaceCar with data from a LapSimulator LapResult.

    Populates all fields that the frontend reads via socket/API.
    """
    from models import CarState as GameCarState

    # --- Lap time ---
    car.lap_times.append(lap_result.lap_time_s)
    car.total_laps += 1
    car.total_session_laps += 1

    # --- Best lap ---
    if not hasattr(car, "best_lap_time") or lap_result.lap_time_s < getattr(car, "best_lap_time", float("inf")):
        car.best_lap_time = lap_result.lap_time_s

    # --- Sector times ---
    if lap_result.sector_times_s:
        sectors = lap_result.sector_times_s
        if len(sectors) >= 3:
            car.current_lap_sectors = {
                "sector1": sectors[0],
                "sector2": sectors[1],
                "sector3": sectors[2],
            }
            car.last_sector_times = dict(car.current_lap_sectors)

            # Update best sectors
            for key, val in car.current_lap_sectors.items():
                if val is not None:
                    best = car.best_sectors.get(key)
                    if best is None or val < best:
                        car.best_sectors[key] = val

            # Best lap sectors snapshot
            if lap_result.lap_time_s <= getattr(car, "best_lap_time", float("inf")):
                car.best_lap_sectors = dict(car.current_lap_sectors)

    # --- Tyre data ---
    car.tire_wear = lap_result.avg_tyre_wear_pct / 100.0
    car.tire_age += 1

    # Map tyre temps from LapSimulator (avg surface temp → 4 corners)
    avg_temp = lap_result.avg_tyre_temp_surface_c
    if avg_temp > 0:
        # Slight variation per corner for realism
        car.tire_temps = {
            "fl": avg_temp + 1.5,
            "fr": avg_temp + 2.0,
            "rl": avg_temp - 0.5,
            "rr": avg_temp,
        }

    # --- Fuel ---
    fuel_max_kg = 110.0
    if lap_result.fuel_kg >= 0:
        car.fuel_percent = max(1.0, (lap_result.fuel_kg / fuel_max_kg) * 100.0)
        if hasattr(car, "player_config"):
            car.player_config["fuel_percent"] = int(round(car.fuel_percent))

    # --- Distance (for map position) ---
    # After completing a lap, car is at start/finish
    car.distance_traveled = 0

    # --- Stint tracking ---
    car.stint_laps_remaining = max(0, car.stint_laps_remaining - 1)


def set_racecar_phase(car, phase_name: str) -> None:
    """
    Set the game CarState on a RaceCar from a phase name.

    phase_name: 'box', 'out_lap', 'hot_lap', 'in_lap'
    """
    from models import CarState as GameCarState

    mapping = {
        "box": GameCarState.BOX,
        "in_garage": GameCarState.BOX,
        "out_lap": GameCarState.OUT_LAP,
        "pit_exit": GameCarState.OUT_LAP,
        "on_track": GameCarState.HOT_LAP,
        "hot_lap": GameCarState.HOT_LAP,
        "in_lap": GameCarState.IN_LAP,
        "pit_entry": GameCarState.IN_LAP,
        "slow_lap": GameCarState.OUT_LAP,
        "pit_work": GameCarState.BOX,
        "pit_queue": GameCarState.BOX,
    }
    car.state = mapping.get(phase_name, GameCarState.BOX)
