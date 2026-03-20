# ---------------------------------------------------------------------------
# Adapter – bidirectional mapping between game models (RaceCar) and simulator
# ---------------------------------------------------------------------------
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.models import RaceCar

logger = logging.getLogger(__name__)

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
# ERS mode normalization helpers
# ---------------------------------------------------------------------------

ERS_MODE_CANONICAL = {
    "RECHARGE": "RECHARGE",
    "HARVEST": "HARVEST",
    "SAFETY_CAR": "SAFETY_CAR",
    "STANDARD": "STANDARD",
    "NEUTRAL": "NEUTRAL",
    "OVERTAKE": "OVERTAKE",
    "ATTACK": "ATTACK",
    "QUALIFY": "QUALIFY",
    "DEFENCE": "DEFENCE",
    "DEFENSE": "DEFENCE",
    "DEPLOY": "DEPLOY",
}


def normalize_ers_mode(mode: Optional[str]) -> Optional[str]:
    if not mode:
        return None
    return ERS_MODE_CANONICAL.get(str(mode).strip().upper())



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
    # Also support uppercase values from enum .value
    "SOFT": TyreCompound.C4,
    "MEDIUM": TyreCompound.C3,
    "HARD": TyreCompound.C2,
    "INTERMEDIATE": TyreCompound.INTERMEDIATE,
    "WET": TyreCompound.WET,
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
    result = _GAME_TO_SIM_COMPOUND.get(val, TyreCompound.C3)
    if result == TyreCompound.C3 and val not in ["medium", "Medium", "MEDIUM"]:
        import logging
        logging.getLogger(__name__).warning(f"Unknown compound {val}, defaulting to C3")
    return result


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
        "save": EngineMapName.SAFETY_CAR,
        "standard": EngineMapName.RACE,
        "push": EngineMapName.RACE,
        "qualy": EngineMapName.QUALIFY,
    }
    ice_mode = getattr(car, "ice_mode", "standard")
    return mapping.get(str(ice_mode).lower(), EngineMapName.RACE)


def _build_sim_state(car_id: str, car) -> SimCarState:
    state = SimCarState(car_id=car_id)
    state.brakes.duct_opening = _compute_brake_duct_opening(car)

    # Tyres
    game_compound = getattr(car, "current_tire", None)
    sim_compound = game_compound_to_sim(game_compound) if game_compound else TyreCompound.C3
    state.tyres = {
        wp: TyreState(wheel_pos=wp, compound=sim_compound) for wp in WheelPosition
    }

    tyre_set = getattr(car, "current_tyre_set", None)
    snapshot = {}
    if tyre_set is not None:
        try:
            snapshot = tyre_set.get_runtime_snapshot()
        except Exception:
            snapshot = {}
    else:
        snapshot = getattr(car, "tyre_states", {}) or {}

    temps = getattr(car, "tire_temps", {}) or {}
    condition_pct = None
    laps_completed = None
    heat_cycles = None

    if tyre_set is not None:
        condition_pct = float(getattr(tyre_set, "condition", 100.0))
        laps_completed = getattr(tyre_set, "laps_completed", None)
        heat_cycles = getattr(tyre_set, "heat_cycles", None)
    else:
        condition_pct = getattr(car, "current_tyre_condition_pct", None)
        laps_completed = getattr(car, "current_tyre_laps_completed", None)
        heat_cycles = getattr(car, "current_tyre_heat_cycles", None)

    wear_pct_override = None
    if condition_pct is not None:
        try:
            wear_pct_override = max(0.0, min(100.0, 100.0 - float(condition_pct)))
        except (TypeError, ValueError):
            wear_pct_override = None

    for wp, tyre in state.tyres.items():
        key = wp.name.lower()
        wheel_snapshot = snapshot.get(key, {}) if isinstance(snapshot, dict) else {}
        surface_temp = wheel_snapshot.get("surface_temp")
        core_temp = wheel_snapshot.get("core_temp")
        wear_pct = wheel_snapshot.get("wear_pct")
        wheel_heat_cycles = wheel_snapshot.get("heat_cycles")
        wheel_age_laps = wheel_snapshot.get("age_laps")

        if surface_temp is not None:
            tyre.surface_temp_c = float(surface_temp)
        elif key in temps:
            tyre.surface_temp_c = temps[key]

        if core_temp is not None:
            tyre.core_temp_c = float(core_temp)

        if wear_pct is not None:
            tyre.wear_pct = max(0.0, min(100.0, float(wear_pct)))
        elif wear_pct_override is not None:
            tyre.wear_pct = wear_pct_override

        age_source = wheel_age_laps if wheel_age_laps is not None else laps_completed
        if age_source is not None:
            try:
                tyre.age_laps = max(0, int(age_source))
            except (TypeError, ValueError):
                pass

        heat_source = wheel_heat_cycles if wheel_heat_cycles is not None else heat_cycles
        if heat_source is not None:
            try:
                tyre.heat_cycles = max(0, int(heat_source))
            except (TypeError, ValueError):
                pass

    # Power Unit
    team = getattr(car, "team", None)
    power_unit = getattr(team, "power_unit", None)
    map_name = _resolve_engine_map(car)
    if power_unit:
        fuel_pct = max(1, min(100, getattr(car, "fuel_percent", 100)))
        fuel_load = power_unit.fuel_capacity_kg * (fuel_pct / 100.0)
        pu_state = power_unit.create_state(fuel_kg=fuel_load, map_name=map_name)
        state.pu = pu_state
    ers_mode = normalize_ers_mode(getattr(car, "ers_mode", None))
    if ers_mode:
        state.ers_mode = ers_mode

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

    # Prefer player-configured pace level; fallback to driver skills if missing
    pace_value = getattr(car, "pace_level", None)
    push_level = None
    if pace_value is not None:
        try:
            push_level = max(1, min(10, int(round(pace_value))))
        except (TypeError, ValueError):
            push_level = None

    if push_level is None:
        pilot = getattr(car, "pilot", None)
        if pilot and hasattr(pilot, 'velocita') and hasattr(pilot, 'qualifica'):
            avg_skill = (pilot.velocita + pilot.qualifica) / 2
            push_level = max(1, min(10, int(7 + (avg_skill - 85) / 5)))
        else:
            push_level = 7
        
    state = _build_sim_state(car_id, car)

    # Calculate team penalties (AI + player use same logic)
    delta_aero = 0.0
    delta_grip = 0.0
    
    team_code = None
    try:
        from utils.team_performance import compute_team_penalties
        from lap_simulator.config_loader import load_circuit_config

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

        team = getattr(car, "team", None)
        if team:
            team_code = getattr(team, 'team_code', None) or getattr(team, 'sigla_scuderia', None)
        if not team_code:
            driver_team_map = {
                1: 'RBR', 22: 'RBR',
                11: 'RBR',  # Perez legacy fallback
                63: 'MER', 44: 'MER', 12: 'MER',
                4: 'MCL', 81: 'MCL',
                16: 'FER', 55: 'FER',
                14: 'AST', 18: 'AST',
                23: 'WIL', 2: 'WIL',
                30: 'RB', 6: 'RB',
                27: 'SAU', 5: 'SAU', 31: 'ALP', 10: 'ALP',
                20: 'HAAS', 77: 'SAU', 24: 'SAU', 43: 'ALP', 87: 'HAAS',
            }
            team_code = driver_team_map.get(int(car_id))

        if team_code:
            team_code = team_code.upper()
            delta_aero, delta_grip = compute_team_penalties(team_code, circuit_config)
        else:
            logger.warning("Unable to resolve team_code for car %s", car_id)
    except Exception as exc:
        logger.error("Failed to compute team penalties for %s: %s", car_id, exc, exc_info=True)

    # Extract setup sliders from player_config if available
    setup_sliders = {}
    ideal_setup_sliders = {}
    try:
        player_config = getattr(car, "player_config", {})
        if player_config:
            setup_sliders = dict(player_config.get("setup", {}))
            ideal_setup_sliders = dict(player_config.get("ideal_setup", {}))
    except Exception as e:
        logger.debug("Failed to extract setup sliders for car %s: %s", car_id, e)

    if team_code:
        setattr(state, "team_code", team_code)

    return CarEntry(
        car_id=car_id,
        state=state,
        aero_setup=setup,
        driver_skills=skills,
        push_level=push_level,
        delta_aero=delta_aero,
        delta_grip=delta_grip,
        apply_baseline_delta=False,  # No artificial baseline penalty for AI testing
        setup_sliders=setup_sliders,
        ideal_setup_sliders=ideal_setup_sliders,
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
