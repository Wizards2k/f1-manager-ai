"""Shared helpers for applying team-level performance penalties."""

from __future__ import annotations

from typing import Dict, Tuple

from data.teams import TEAMS
from lap_simulator.data_types import CircuitConfig
from models.auto_models import Auto


# Build mapping from team code to team object
from data.teams import TEAM_METADATA, TEAMS
TEAM_BY_CODE = {team.sigla_scuderia: team for team in TEAMS}

# Expected quali gaps vs McLaren baseline (percentage)
EXPECTED_TEAM_GAPS: Dict[str, float] = {
    "MCL": 0.0,
    "RBR": 0.8,
    "FER": 1.2,
    "MER": 1.8,
    "AST": 2.5,
    "ALP": 3.2,
    "HAAS": 4.1,
    "WIL": 4.8,
    "SAU": 5.5,
    "RB": 6.8,
}


def _total_df(auto: Auto) -> float:
    pkg = getattr(auto, "aero_package", None)
    if pkg is None:
        return 1.0
    return (
        (pkg.ala_anteriore.df_coeff)
        + (pkg.ala_posteriore.df_coeff)
        + (pkg.fondo_anteriore.df_coeff)
        + (pkg.fondo_posteriore.df_coeff)
    ) * 1000.0


def _total_grip(auto: Auto) -> float:
    return getattr(auto, "grip_base", 1.0) or 1.0


_base_auto = TEAM_BY_CODE.get("MCL").auto if TEAM_BY_CODE.get("MCL") else None
BASELINE_DF = _total_df(_base_auto) if _base_auto else 1.0
BASELINE_GRIP = _total_grip(_base_auto) if _base_auto else 1.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _penalty_shares(delta_aero: float, delta_grip: float) -> Tuple[float, float]:
    total = abs(delta_aero) + abs(delta_grip)
    if total < 1e-4:
        return 0.6, 0.4
    return abs(delta_aero) / total, abs(delta_grip) / total


def compute_team_penalties(
    team_code: str,
    circuit_config: CircuitConfig | None,
    target_gap_pct: float | None = None,
) -> Tuple[float, float]:
    """Return (delta_aero, delta_grip) penalties for a given team."""
    import logging
    logger = logging.getLogger(__name__)

    team = TEAM_BY_CODE.get(team_code.upper()) if team_code else None

    if team is None or team.auto is None:
        logger.warning("compute_team_penalties: no team or auto for %s", team_code)
        return 0.0, 0.0

    car = team.auto
    car_df = _total_df(car)
    car_grip = _total_grip(car)

    physical_delta_aero = _clamp((BASELINE_DF - car_df) / BASELINE_DF, -0.03, 0.03)
    physical_delta_grip = _clamp((BASELINE_GRIP - car_grip) / BASELINE_GRIP, -0.05, 0.05)

    target_penalty = (target_gap_pct if target_gap_pct is not None else EXPECTED_TEAM_GAPS.get(team_code.upper(), 0.0)) / 100.0
    
    if target_penalty == 0.0:
        return 0.0, 0.0

    aero_share, grip_share = _penalty_shares(physical_delta_aero, physical_delta_grip)

    k_aero = circuit_config.k_aero_penalty if circuit_config else 0.03
    k_grip = circuit_config.k_grip_penalty if circuit_config else 0.02

    max_delta = 4.0
    delta_aero = _clamp((target_penalty * aero_share) / (k_aero or 1.0), -max_delta, max_delta)
    delta_grip = _clamp((target_penalty * grip_share) / (k_grip or 1.0), -max_delta, max_delta)

    return delta_aero, delta_grip
