"""Helper utilities for lap time performance calculations."""
from __future__ import annotations

import random

from typing import Dict, Optional, Tuple

import config
from models import CarState, RaceCar
from utils.position import circuit_length

# Base constants
DEFAULT_BASE_LAP_TIME = 80.0  # seconds, fallback when no circuit profile
MIN_LAP_TIME = 60.0   # prevent unrealistic negative laps

CAR_WEIGHT = 0.60
TIRE_WEIGHT = 0.30
PILOT_WEIGHT = 0.10

PILOT_SKILL_COEFF = 0.05  # seconds per skill point
OUT_LAP_FACTOR = 1.05
IN_LAP_FACTOR = 1.08

RANDOM_JITTER = 0.05  # +/- seconds per sector


def compute_pilot_skill_score(pilot) -> float:
    return (
        0.4 * pilot.velocita
        + 0.3 * pilot.gara
        + 0.2 * pilot.qualifica
        + 0.1 * pilot.gestione_carburante
    )


def compute_pilot_bonus_seconds(pilot) -> float:
    return compute_pilot_skill_score(pilot) * PILOT_SKILL_COEFF


def compute_car_bonus_seconds(team) -> float:
    return team.bonus_prestazione


def compute_tire_delta_seconds(car: RaceCar) -> float:
    if car.current_gomma:
        return car.current_gomma.impatto_su_laptime()
    return 0.0


def _current_base_lap_time() -> float:
    profile = None
    try:
        profile = config.get_current_circuit_profile()
    except Exception:
        profile = None
    if profile:
        return profile.get('base_lap_seconds', DEFAULT_BASE_LAP_TIME) or DEFAULT_BASE_LAP_TIME
    return DEFAULT_BASE_LAP_TIME


def compute_projected_lap_time(car: RaceCar) -> Tuple[float, Dict[str, float]]:
    """Return lap time and debug info (in seconds) after applying contributions."""
    car_bonus = CAR_WEIGHT * compute_car_bonus_seconds(car.team)
    pilot_bonus = PILOT_WEIGHT * compute_pilot_bonus_seconds(car.pilot)
    tire_delta = TIRE_WEIGHT * compute_tire_delta_seconds(car)

    base_lap = _current_base_lap_time()
    lap_time = base_lap - car_bonus - pilot_bonus + tire_delta
    clamped = max(lap_time, MIN_LAP_TIME)
    debug = {
        "base_lap": base_lap,
        "car_bonus": car_bonus,
        "pilot_bonus": pilot_bonus,
        "tire_delta": tire_delta,
        "raw_lap": lap_time,
        "final_lap": clamped,
    }
    return clamped, debug


def sector_ratio(sector_distance: float) -> float:
    total_length = circuit_length()
    if not total_length:
        return 1 / 3  # fallback
    return sector_distance / total_length


def project_sector_time(
    car: RaceCar,
    sector_distance: float,
    lap_type: CarState,
    debug: Optional[Dict[str, float]] = None,
) -> float:
    lap_time, lap_debug = compute_projected_lap_time(car)
    if debug is not None:
        debug.update(lap_debug)
    ratio = sector_ratio(sector_distance)
    sector_time = lap_time * ratio

    if lap_type == CarState.OUT_LAP:
        sector_time *= OUT_LAP_FACTOR
    elif lap_type == CarState.IN_LAP:
        sector_time *= IN_LAP_FACTOR

    jitter = random.uniform(-RANDOM_JITTER, RANDOM_JITTER)
    return max(0.5, sector_time + jitter)
