"""
Engine Penalty System – Step 6 integration for update_section().

Computes ICE+ERS power-based penalties/bonuses based on:
- Engine CV delta vs Mercedes reference (1008 CV)
- Engine map penalties (QUALIFY = 0 reference)
- Circuit-specific coefficients
- Applied only on straight sections

Reference: 20 CV = -0.2s bonus on medium-speed circuits
"""
from __future__ import annotations

from .data_types import (
    CircuitConfig,
    EngineMapName,
    SectionContext,
    SectionKind,
    clamp,
)

# Import engine map penalty flag
try:
    from utils.game_logic import ENABLE_ENGINE_MAP_PENALTIES
except ImportError:
    ENABLE_ENGINE_MAP_PENALTIES = True


# Section kinds where engine penalties apply (straights only)
STRAIGHT_KINDS = {
    SectionKind.STRAIGHT,
    SectionKind.MEDIUM_STRAIGHT,
    SectionKind.ULTRA_FAST_CORNER,  # High-speed corners benefit from power
}

# Default engine map penalties (QUALIFY = 0 reference)
DEFAULT_ENGINE_MAP_PENALTIES = {
    EngineMapName.QUALIFY: 0.0,      # Reference zero penalty
    EngineMapName.RACE: 0.18,        # ~+0.18s/lap
    EngineMapName.PRACTICE: 0.35,    # ~+0.35s/lap
    EngineMapName.SAFETY_CAR: 0.55,  # heavy derate
}


def compute_engine_penalty(
    team_cv: float,
    engine_map: EngineMapName,
    section: SectionContext,
    config: CircuitConfig,
) -> float:
    """
    Compute engine penalty/bonus for the current section.
    
    Args:
        team_cv: Team engine CV (from power_units.py)
        engine_map: Current engine map
        section: Current circuit section
        config: Circuit configuration
        
    Returns:
        Engine penalty in seconds (negative = bonus)
    """
    # Apply only on straight sections
    if section.kind not in STRAIGHT_KINDS:
        return 0.0
    
    # CV delta vs Mercedes reference
    cv_delta = team_cv - config.engine_reference_cv
    
    # Base engine penalty from CV delta (20 CV = -0.2s)
    cv_penalty = cv_delta * config.engine_penalty_coeff
    
    # Map penalty (QUALY = 0 reference)
    map_penalty = 0.0
    if ENABLE_ENGINE_MAP_PENALTIES:
        map_penalties = config.engine_map_penalties or DEFAULT_ENGINE_MAP_PENALTIES
        map_penalty = map_penalties.get(engine_map, 0.0)
    
    # Total engine penalty
    total_penalty = cv_penalty + map_penalty
    
    # No clamping for now - let penalties flow through
    return total_penalty


def get_engine_cv_for_team(team_code: str) -> float:
    """
    Get engine CV for a team from power_units.py data.
    
    Args:
        team_code: FIA team code (e.g., "RBR", "MER")
        
    Returns:
        Engine CV rating
    """
    # Hard-coded CV values based on power_units.py data to avoid import issues
    TEAM_ENGINE_CV = {
        "RBR": 1015.0,   # Honda RBPT HRC
        "RB": 995.0,     # Honda RBPT HRC  
        "MCL": 1008.0,   # Mercedes-AMG HPP
        "MER": 1018.0,   # Mercedes-AMG HPP
        "AST": 995.0,    # Mercedes-AMG HPP
        "WIL": 987.0,    # Mercedes-AMG HPP
        "FER": 1007.0,   # Ferrari 066/11
        "SAU": 987.0,    # Ferrari 066/11
        "HAAS": 982.0,   # Ferrari 066/11
        "ALP": 960.0,    # Renault E-Tech RE25
    }
    
    return TEAM_ENGINE_CV.get(team_code.upper(), 1008.0)  # Fallback to Mercedes reference


# ---------------------------------------------------------------------------
# ERS Energy Bonus
# ---------------------------------------------------------------------------

# Calibration: 4 MJ/lap across ~8 straights → 0.5 MJ/straight → 0.0625s/straight
# → ~0.5s/lap bonus for full ERS deployment (historical F1 reference)
ERS_BONUS_COEFF_S_PER_MJ = 0.125   # seconds gained per MJ deployed on a straight
ERS_BONUS_MAX_PER_SECTION_S = 0.12  # safety clamp per section


def compute_ers_bonus(
    deploy_mj: float,
    mguh_direct_mj: float,
    section: SectionContext,
    ers_thermal_eta: float = 1.0,
) -> float:
    """
    Compute ERS time bonus for the current section.

    Energy deployed (battery + MGU-H direct) on straight sections translates
    into a lap time improvement. Thermal clipping is already encoded in
    deploy_mj via power_unit.generate_output(), but eta is passed explicitly
    for diagnostic logging.

    Args:
        deploy_mj: Battery energy deployed this section (MJ)
        mguh_direct_mj: MGU-H direct-to-wheels energy this section (MJ)
        section: Current circuit section
        ers_thermal_eta: Thermal derating factor (1.0 = no clipping)

    Returns:
        ERS bonus in seconds (negative = faster, 0.0 on non-straight sections)
    """
    if section.kind not in STRAIGHT_KINDS:
        return 0.0

    total_energy_mj = max(deploy_mj + mguh_direct_mj, 0.0)
    if total_energy_mj <= 1e-6:
        return 0.0

    raw_bonus = total_energy_mj * ERS_BONUS_COEFF_S_PER_MJ
    # Clamp to avoid unrealistic single-section gains
    bonus = clamp(raw_bonus, 0.0, ERS_BONUS_MAX_PER_SECTION_S)
    # Return negative (time gain)
    return -bonus


def validate_engine_coefficient(
    circuit_coeff: float,
    expected_cv_delta: float = 20.0,
    expected_penalty_s: float = 0.2
) -> bool:
    """
    Validate that circuit coefficient produces expected penalty.
    
    Args:
        circuit_coeff: Circuit engine penalty coefficient
        expected_cv_delta: CV delta to test (default 20 CV)
        expected_penalty_s: Expected penalty (default 0.2s)
        
    Returns:
        True if coefficient is correct
    """
    actual_penalty = expected_cv_delta * circuit_coeff
    tolerance = 0.01  # 10ms tolerance
    
    return abs(actual_penalty - expected_penalty_s) <= tolerance
