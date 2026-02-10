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
    TyreCompound,
)
from lap_simulator.lap_simulator import CarEntry, LapResult

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


# ---------------------------------------------------------------------------
# RaceCar → CarEntry
# ---------------------------------------------------------------------------

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
    setup = aero_setup or AeroSetup()

    # Map push level: game pace_level 1-10 → sim push_level 0.90-1.10
    pace = getattr(car, "pace_level", 5)
    push_level = 0.90 + (pace - 1) * (0.20 / 9)  # 1→0.90, 5→0.989, 10→1.10

    state = SimCarState(car_id=car_id)

    # Set fuel from game fuel_percent
    fuel_pct = getattr(car, "fuel_percent", 100)
    fuel_max_kg = 110.0  # F1 max fuel
    state.pu.fuel_kg = fuel_max_kg * (fuel_pct / 100.0)

    return CarEntry(
        car_id=car_id,
        state=state,
        aero_setup=setup,
        driver_skills=skills,
        push_level=push_level,
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
        "pit_work": GameCarState.BOX,
        "pit_queue": GameCarState.BOX,
    }
    car.state = mapping.get(phase_name, GameCarState.BOX)
